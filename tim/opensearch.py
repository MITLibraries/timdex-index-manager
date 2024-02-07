import json
import logging
import os
from typing import Iterator, Optional

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from opensearchpy.helpers import streaming_bulk

from tim import helpers
from tim.config import (
    PRIMARY_ALIAS,
    configure_index_settings,
    configure_opensearch_bulk_settings,
)
from tim.errors import (
    AliasNotFoundError,
    BulkIndexingError,
    IndexExistsError,
    IndexNotFoundError,
)

logger = logging.getLogger(__name__)

REQUEST_CONFIG = configure_opensearch_bulk_settings()

# Cluster functions


def configure_opensearch_client(url: str) -> OpenSearch:
    """Return an OpenSearch client configured with the supplied URL.

    Includes the appropriate AWS credentials configuration if the URL is not localhost.
    """
    logger.info("OpenSearch request configurations: %s", REQUEST_CONFIG)
    if url in ["localhost", "opensearch"]:
        return OpenSearch(
            hosts=[{"host": url, "port": "9200"}],
            http_auth=("admin", "admin"),
            connection_class=RequestsHttpConnection,
            max_retries=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_RETRIES"],
            retry_on_timeout=True,
            timeout=REQUEST_CONFIG["OPENSEARCH_REQUEST_TIMEOUT"],
        )

    credentials = boto3.Session().get_credentials()
    region = os.getenv("AWS_REGION", "us-east-1")
    auth = AWSV4SignerAuth(credentials, region)
    return OpenSearch(
        hosts=[{"host": url, "port": "443"}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        max_retries=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_RETRIES"],
        retry_on_timeout=True,
        timeout=REQUEST_CONFIG["OPENSEARCH_REQUEST_TIMEOUT"],
    )


def get_formatted_info(client: OpenSearch) -> str:
    """Return basic information about the cluster, formatted for display."""
    response = client.info()
    return (
        f"\nName: {response['cluster_name']}"
        f"\nUUID: {response['cluster_uuid']}"
        f"\nOpenSearch version: {response['version']['number']}"
        f"\nLucene version: {response['version']['lucene_version']}\n"
    )


def get_aliases(client: OpenSearch) -> Optional[dict[str, list[str]]]:
    """Return all aliases with their associated indexes.

    Returns None if there are no aliases in the cluster.
    """
    response = client.cat.aliases(format="json")
    logger.debug(response)
    aliases: dict[str, list[str]] = {}
    for item in response:
        aliases.setdefault(item["alias"], []).append(item["index"])
    return aliases or None


def get_formatted_aliases(client: OpenSearch) -> str:
    """Return all aliases with their associated indexes, formatted for display."""
    output = "Current state of all aliases:"
    if aliases := get_aliases(client):
        for alias, indexes in sorted(aliases.items()):
            output += f"\nAlias: {alias}"
            output += f"\n  Indexes: {', '.join(sorted(indexes))}\n"
    else:
        output += "\nNo aliases present in OpenSearch cluster.\n"
    return output


def get_indexes(client: OpenSearch) -> Optional[dict[str, dict]]:
    """Return all indexes with their summary information."""
    response = client.cat.indices(format="json")
    logger.debug(response)
    indexes = {
        index["index"]: {key: value for key, value in index.items() if key != "index"}
        for index in response
    }
    return indexes or None


def get_formatted_indexes(client: OpenSearch) -> str:
    """Return all indexes with their summary information, formatted for display."""
    output = "Current state of all indexes:"
    if indexes := get_indexes(client):
        output += "\n"
        for index, info in sorted(indexes.items()):
            index_aliases = get_index_aliases(client, index)
            output += (
                f"\nName: {index}\n"
                f"  Aliases: {', '.join(index_aliases) if index_aliases else 'None'}\n"
                f"  Status: {info['status']}\n"
                f"  Health: {info['health']}\n"
                f"  Documents: {int(info['docs.count']):,}\n"
                f"  Primary store size: {info['pri.store.size']}\n"
                f"  Total store size: {info['store.size']}\n"
                f"  UUID: {info['uuid']}\n"
                f"  Primary Shards: {int(info['pri']):,}\n"
                f"  Replica Shards: {int(info['rep']):,}\n"
            )
        return output
    return output + " No indexes present in OpenSearch cluster."


def get_all_aliased_indexes_for_source(
    client: OpenSearch, source: str
) -> Optional[dict[str, list[str]]]:
    """Return all aliased indexes for the source, grouped by alias.

    Returns a dict of the aliases with a list of the source index(es) for each. There
    *should* only be one source index per alias, but in case there is ever more than
    one, this function will return the accurate information and log an error for
    further investigation.

    Returns None if there are no aliased indexes for the source.
    """
    result = {}
    if aliases := get_aliases(client):
        logger.debug(aliases)
        for alias, indexes in aliases.items():
            source_indexes = [
                index
                for index in indexes
                if helpers.get_source_from_index(index) == source
            ]
            if len(source_indexes) > 1:
                logger.error(
                    "Alias '%s' had multiple existing indexes for source '%s': %s",
                    alias,
                    source,
                    source_indexes,
                )
            result[alias] = source_indexes
    return {k: v for k, v in result.items() if v} or None


# Index functions


def create_index(client: OpenSearch, name: str) -> str:
    """Create an index with the provided name.

    Creates the index with settings and mappings from config. Returns the index name.
    """
    mappings, settings = configure_index_settings()
    request_body = json.dumps({"settings": settings, "mappings": mappings})
    try:
        response = client.indices.create(name, body=request_body)
    except RequestError as error:
        if (
            isinstance(error.info, dict)
            and error.info.get("error", {}).get("type")
            == "resource_already_exists_exception"
        ):
            raise IndexExistsError(name) from error
        raise error
    logger.debug(response)
    return response["index"]


def delete_index(client: OpenSearch, index: str) -> None:
    """Delete the provided index."""
    try:
        response = client.indices.delete(index)
    except NotFoundError as error:
        raise IndexNotFoundError(index=index) from error
    logger.debug(response)


def get_or_create_index_from_source(
    client: OpenSearch, source: str, new: bool
) -> tuple[str, bool]:
    """Get the primary index for the provided source or create a new index.

    If new is True, always creates a new index. Otherwise, gets and returns the primary
    index if there is one and creates a new index if not.

    Note: if a new index is created, this function does *not* promote it to the primary
    alias. That needs to be handled separately.
    """
    if new is False:
        if index := get_primary_index_for_source(client, source):
            logger.debug("Primary index found for source '%s': %s", source, index)
            return index, False
        logger.debug(
            "No current primary index found for source '%s', creating a new index.",
            source,
        )
    new_index_name = helpers.generate_index_name(source)
    return create_index(client, new_index_name), True


def get_index_aliases(client: OpenSearch, index: str) -> Optional[list[str]]:
    """Return a sorted list of aliases assigned to an index.

    Returns None if the index has no aliases.
    """
    try:
        response = client.indices.get_alias(index=index)
    except NotFoundError as error:
        raise IndexNotFoundError(index) from error
    logger.debug(response)
    aliases = response[index].get("aliases")
    return sorted(aliases.keys()) or None


def get_primary_index_for_source(client: OpenSearch, source: str) -> Optional[str]:
    """Get the primary index for the provided source.

    Returns None if there is no primary index for the source.
    """
    aliases = get_all_aliased_indexes_for_source(client, source)
    return aliases.get(PRIMARY_ALIAS, [])[0] if aliases else None


def promote_index(
    client: OpenSearch, index: str, extra_aliases: Optional[list[str]] = None
) -> None:
    """Promote an index to all relevant aliases.

    Promotes an index to the primary alias (always), all aliases that contain an
    existing index for the same source (if any), and any aliases supplied in
    `extra_aliases`. If a supplied alias does not exist, it will be created.

    Promoting an index to an alias always demotes any existing index(es) for the same
    source in that alias. This action is atomic.

    Source is determined by the index name prefix.

    Raises an exception if the supplied index does not exist.
    """
    source = helpers.get_source_from_index(index)
    current_aliased_source_indexes = (
        get_all_aliased_indexes_for_source(client, source) or {}
    )
    new_aliases = list(extra_aliases) if extra_aliases else []
    all_aliases = set(
        [PRIMARY_ALIAS] + list(current_aliased_source_indexes.keys()) + new_aliases
    )

    request_body = {
        "actions": [{"add": {"index": index, "alias": alias}} for alias in all_aliases]
    }

    for alias, indexes in current_aliased_source_indexes.items():
        request_body["actions"].extend(
            [
                {"remove": {"index": existing_index, "alias": alias}}
                for existing_index in indexes
                if existing_index != index
            ]
        )

    # Sending both the alias additions and demotions in one request to OpenSearch
    # ensures the action is atomic (OpenSearch handles that).
    try:
        response = client.indices.update_aliases(body=request_body)
        logger.debug(response)
    except NotFoundError as error:
        if (
            isinstance(error.info, dict)
            and error.info.get("error", []).get("type") == "index_not_found_exception"
        ):
            raise IndexNotFoundError(index=index) from error
        raise error


def remove_alias(client: OpenSearch, index: str, alias: str) -> None:
    """Remove the provided alias from the provided index."""
    try:
        response = client.indices.delete_alias(index, alias)
        logger.debug(response)
    except NotFoundError as error:
        if (
            isinstance(error.info, dict)
            and error.info.get("error", []).get("type") == "index_not_found_exception"
        ):
            raise IndexNotFoundError(index=index) from error
        if (
            isinstance(error.info, dict)
            and error.info.get("error", []).get("type") == "aliases_not_found_exception"
        ):
            raise AliasNotFoundError(alias=alias, index=index) from error
        raise error


# Record functions


def bulk_delete(
    client: OpenSearch, index: str, records: Iterator[dict]
) -> dict[str, int]:
    """Delete records from an existing index using the streaming bulk helper.

    If an error occurs during record deletion, it will be logged and bulk deletion will
    continue until all records have been processed.

    Returns total sums of: records deleted, errors, and total records processed.
    """
    result = {"deleted": 0, "errors": 0, "total": 0}
    actions = helpers.generate_bulk_actions(index, records, "delete")
    responses = streaming_bulk(
        client,
        actions,
        max_chunk_bytes=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_CHUNK_BYTES"],
        raise_on_error=False,
    )
    for response in responses:
        logger.debug(response)
        if response[1]["delete"].get("result") == "not_found":
            logger.error(
                "Record to delete '%s' was not found in index '%s'.",
                response[1]["delete"]["_id"],
                index,
            )
            result["errors"] += 1
        elif response[1]["delete"].get("result") == "deleted":
            result["deleted"] += 1
        else:
            logger.error(
                "Something unexpected happened during deletion. Bulk delete response: "
                "%s",
                json.dumps(response),
            )
            result["errors"] += 1
        result["total"] += 1
        if result["total"] % int(os.getenv("STATUS_UPDATE_INTERVAL", "1000")) == 0:
            logger.info("Status update: %s records deleted so far!", result["total"])
    logger.info("All records deleted, refreshing index.")
    response = client.indices.refresh(
        index=index,
    )
    logger.debug(response)
    return result


def bulk_index(client: OpenSearch, index: str, records: Iterator[dict]) -> dict[str, int]:
    """Indexes records into an existing index using the streaming bulk helper.

    This action function uses the OpenSearch "index" action, which is a
    combination of create and update: if a record with the same _id exists in the
    index, it will be updated. If it does not exist, the record will be indexed as a
    new document.

    If an error occurs during record indexing, it will be logged and bulk indexing will
    continue until all records have been processed.

    Returns total sums of: records created, records updated, errors, and total records
    processed.
    """
    result = {"created": 0, "updated": 0, "errors": 0, "total": 0}
    actions = helpers.generate_bulk_actions(index, records, "index")
    responses = streaming_bulk(
        client,
        actions,
        max_chunk_bytes=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_CHUNK_BYTES"],
        raise_on_error=False,
    )
    for response in responses:
        if response[0] is False:
            error = response[1]["index"]["error"]
            record = response[1]["index"]["_id"]
            if error["type"] == "mapper_parsing_exception":
                logger.error(
                    "Error indexing record '%s'. Details: %s",
                    record,
                    json.dumps(error),
                )
                result["errors"] += 1
            else:
                raise BulkIndexingError(record, index, json.dumps(error))
        elif response[1]["index"].get("result") == "created":
            result["created"] += 1
        elif response[1]["index"].get("result") == "updated":
            result["updated"] += 1
        else:
            logger.error(
                "Something unexpected happened during ingest. Bulk index response: %s",
                json.dumps(response),
            )
            result["errors"] += 1
        result["total"] += 1
        if result["total"] % int(os.getenv("STATUS_UPDATE_INTERVAL", "1000")) == 0:
            logger.info("Status update: %s records indexed so far!", result["total"])
    logger.info("All records ingested, refreshing index.")
    response = client.indices.refresh(
        index=index,
    )
    logger.debug(response)
    return result
