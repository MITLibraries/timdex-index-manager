import json
import logging
import os
from collections import defaultdict, deque
from collections.abc import Iterator
from typing import Any

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
    BulkActionError,
    IndexExistsError,
    IndexNotFoundError,
    RetryFailedWithUnexpectedError,
)

logger = logging.getLogger(__name__)

REQUEST_CONFIG = configure_opensearch_bulk_settings()
TRANSPORT_ERROR_507 = 507

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

    auth_service_type = os.getenv("AUTH_SERVICE_TYPE", "es")
    valid_auth_service_types = {"aoss", "es"}

    if auth_service_type not in valid_auth_service_types:
        raise ValueError(
            f"AUTH_SERVICE_TYPE must be one of {sorted(valid_auth_service_types)}, "
            f"got {auth_service_type!r}"
        )

    auth = AWSV4SignerAuth(
        credentials,
        region,
        service=auth_service_type,
    )
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


def get_aliases(client: OpenSearch) -> dict[str, list[str]] | None:
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


def get_indexes(client: OpenSearch) -> dict[str, dict] | None:
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
            )
        return output
    return output + " No indexes present in OpenSearch cluster."


def get_all_aliased_indexes_for_source(
    client: OpenSearch, source: str
) -> dict[str, list[str]] | None:
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
        raise
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
    client: OpenSearch, source: str, *, new: bool
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


def get_index_aliases(client: OpenSearch, index: str) -> list[str] | None:
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


def get_primary_index_for_source(client: OpenSearch, source: str) -> str | None:
    """Get the primary index for the provided source.

    Returns None if there is no primary index for the source.
    """
    aliases = get_all_aliased_indexes_for_source(client, source)
    return aliases.get(PRIMARY_ALIAS, [])[0] if aliases else None


def promote_index(
    client: OpenSearch, index: str, extra_aliases: list[str] | None = None
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
    all_aliases = {PRIMARY_ALIAS, *current_aliased_source_indexes.keys(), *new_aliases}

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
        raise


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
        raise


# Record functions


def bulk_delete(
    client: OpenSearch, index: str, records: Iterator[dict]
) -> dict[str, int]:
    """Delete records from an existing index using the streaming bulk helper.

    The `streaming_bulk()` method returns a tuple with a boolean indicating whether
    the action succeeded and the API response as a dict. The "result" value in the
    API response is used to identify successful actions.
        - If result="not_found", the error message is logged
          and the method continues.
        - If an error is caused by a `TransportError` with status 507
          ("Insufficient Storage"), the method will retry the "index" action for
          the record. If the retry results in a `RetryFailedWithUnexpectedError`
          or `TimeoutError`, the exception is logged and the method continues.
        - If an error is unknown, the error message is logged
          and the method continues.

    Returns total sums of: records deleted, errors, and total records processed.
    """
    result_summary = {"deleted": 0, "errors": 0, "total": 0}
    actions = helpers.generate_bulk_actions(index, records, "delete")
    responses = streaming_bulk(
        client,
        actions,
        chunk_size=REQUEST_CONFIG["OPENSEARCH_BULK_CHUNK_SIZE"],
        max_retries=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_RETRIES"],
        initial_backoff=3,
        max_chunk_bytes=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_CHUNK_BYTES"],
        raise_on_error=False,
    )
    for _, item in responses:
        action, response = next(iter(item.items()))

        # parse item details from response
        record_id = response.get("_id")
        status = response.get("status")
        result = response.get("result")

        if result == "deleted":
            result_summary["deleted"] += 1
        elif result == "not_found":
            logger.error(
                "Record to delete '%s' was not found in index '%s'.",
                record_id,
                index,
            )
            result_summary["errors"] += 1
        elif status == TRANSPORT_ERROR_507:
            try:
                execute_single_record_action(
                    client, index, record_id=record_id, action=action
                )
                result_summary["deleted"] += 1
            except (NotFoundError, RetryFailedWithUnexpectedError, TimeoutError):
                logger.exception(f"Retries of '{action}' for {record_id} failed")
                result_summary["errors"] += 1
        else:
            logger.error(
                "Something unexpected happened during deletion. Bulk delete response: %s",
                json.dumps(response),
            )
            result_summary["errors"] += 1
        result_summary["total"] += 1

        if (
            result_summary["total"] % int(os.getenv("STATUS_UPDATE_INTERVAL", "1000"))
            == 0
        ):
            logger.info(
                "Status update: %s records deleted so far!", result_summary["total"]
            )

    return result_summary


def bulk_index(client: OpenSearch, index: str, records: Iterator[dict]) -> dict[str, int]:
    """Indexes records into an existing index using the streaming bulk helper.

    This action function uses the OpenSearch "index" action, which is a
    combination of create and update: if a record with the same `_id` exists in the
    index, it will be updated. If it does not exist, the record will be indexed as a
    new document.

    The `streaming_bulk()` method returns a tuple with a boolean indicating whether
    the action succeeded and the API response as a dict. The "result" value in the
    API response is used to identify successful actions.
        - If an error is caused by "mapper parsing", the error message
          is logged, the record is skipped, and the method continues indexing.
        - If an error is caused by a `TransportError` with status 507
          ("Insufficient Storage"), the method will retry the "index" action for
          the record. If the retry results in a `RetryFailedWithUnexpectedError`
          or `TimeoutError`, the exception propagates to the caller.
        - If an error is unknown, a `BulkActionError` is raised.

    NOTE: The update performed by the "index" action results in a full replacement of the
    document in OpenSearch. If a partial record is provided, this will result in a new
    document in OpenSearch containing only the fields provided in the partial record.

    Returns total sums of: records created, records updated, errors, and total records
    processed.
    """
    result_summary = {"created": 0, "updated": 0, "errors": 0, "total": 0}
    actions_cache: defaultdict = defaultdict(deque)
    actions = helpers.generate_bulk_actions(index, records, "index", actions_cache)
    responses = streaming_bulk(
        client,
        actions,
        chunk_size=REQUEST_CONFIG["OPENSEARCH_BULK_CHUNK_SIZE"],
        max_retries=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_RETRIES"],
        max_chunk_bytes=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_CHUNK_BYTES"],
        raise_on_error=False,
    )
    for _, item in responses:
        action, response = next(iter(item.items()))

        # parse item details from response
        record_id = response.get("_id")
        status = response.get("status")
        result = response.get("result")
        error = response.get("error")

        if result == "created":
            result_summary["created"] += 1
        elif result == "updated":
            result_summary["updated"] += 1
        elif error["type"] == "mapper_parsing_exception":
            logger.error(
                "Error indexing record '%s' with status %s. Details: %s",
                record_id,
                status,
                json.dumps(error),
            )
            result_summary["errors"] += 1
        elif status == TRANSPORT_ERROR_507:
            try:
                retry_response = execute_single_record_action(
                    client,
                    index,
                    record_id=record_id,
                    body=actions_cache[record_id][0]["_source"],
                    action=action,
                )
                result_summary[retry_response["result"]] += 1
            except RequestError as exception:
                logger.exception(
                    "Error indexing record '%s' with status %s.",
                    record_id,
                    exception.status_code,
                )
                result_summary["errors"] += 1
        else:
            raise BulkActionError(
                action=action,
                record=record_id,
                index=index,
                error=json.dumps(error),
            )
        result_summary["total"] += 1

        # remove record action from cache after processing
        helpers.pop_cache_entry(actions_cache, record_id)

        if (
            result_summary["total"] % int(os.getenv("STATUS_UPDATE_INTERVAL", "1000"))
            == 0
        ):
            logger.info(
                "Status update: %s records indexed so far!", result_summary["total"]
            )

    return result_summary


def bulk_update(
    client: OpenSearch, index: str, records: Iterator[dict]
) -> dict[str, int]:
    """Updates existing documents in the index using the streaming bulk helper.

    This method uses the OpenSearch "update" action, which updates existing documents
    and returns an error if the document does not exist. The "update" action can accept
    a full or partial record and will only update the corresponding fields in the
    document.

    The `streaming_bulk()` method returns a tuple with a boolean indicating whether
    the action succeeded and the API response as a dict. The "result" value in the
    API response is used to identify successful actions.
        - If an error is caused by "mapper parsing" or "document missing",
          the error message is logged, the record is skipped, and the method continues
          indexing.
        - If an error is caused by a `TransportError` with status 507
          ("Insufficient Storage"), the method will retry the "index" action for
          the record. If the retry results in a `RetryFailedWithUnexpectedError`
          or `TimeoutError`, the exception propagates to the caller.
        - If an error is unknown, a `BulkActionError` is raised.

    Returns total sums of: records updated, errors, and total records
    processed.
    """
    result_summary = {"updated": 0, "skipped": 0, "errors": 0, "total": 0}
    actions_cache: defaultdict = defaultdict(deque)
    actions = helpers.generate_bulk_actions(index, records, "update", actions_cache)
    responses = streaming_bulk(
        client,
        actions,
        chunk_size=REQUEST_CONFIG["OPENSEARCH_BULK_CHUNK_SIZE"],
        max_retries=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_RETRIES"],
        max_chunk_bytes=REQUEST_CONFIG["OPENSEARCH_BULK_MAX_CHUNK_BYTES"],
        raise_on_error=False,
    )
    for _, item in responses:
        action, response = next(iter(item.items()))

        # parse item details from response
        record_id = response.get("_id")
        status = response.get("status")
        result = response.get("result")
        error = response.get("error")

        if result == "updated":
            result_summary["updated"] += 1
        elif result == "noop":
            result_summary["skipped"] += 1
        elif error["type"] in [
            "mapper_parsing_exception",
            "document_missing_exception",
            "document_missing_in_index_exception",
        ]:
            logger.error(
                "Error updating record '%s' with status %s. Details: %s",
                record_id,
                status,
                json.dumps(error),
            )
            result_summary["errors"] += 1
        elif status == TRANSPORT_ERROR_507:
            try:
                retry_response = execute_single_record_action(
                    client,
                    index,
                    record_id=record_id,
                    body=actions_cache[record_id][0]["doc"],
                    action=action,
                )
                if retry_response["result"] == "updated":
                    result_summary["updated"] += 1
                elif retry_response["result"] == "noop":
                    result_summary["skipped"] += 1
            except (NotFoundError, RequestError) as exception:
                logger.exception(
                    "Error updating record '%s' with status %s.",
                    record_id,
                    exception.status_code,
                )
                result_summary["errors"] += 1
        else:
            raise BulkActionError(
                action=action,
                record=record_id,
                index=index,
                error=json.dumps(error),
            )
        result_summary["total"] += 1

        # remove record action from cache after processing
        helpers.pop_cache_entry(actions_cache, record_id)

        if (
            result_summary["total"] % int(os.getenv("STATUS_UPDATE_INTERVAL", "1000"))
            == 0
        ):
            logger.info(
                "Status update: %s records updated so far!", result_summary["total"]
            )

    return result_summary


@helpers.retry()
def execute_single_record_action(
    client: OpenSearch,
    index: str,
    record_id: str,
    action: str,
    body: dict | None = None,
) -> dict[str, Any]:
    """Execute an OpenSearch action for a single record.

    Supports index, update, and delete actions for one record. The action
    is dispatched to the corresponding OpenSearch client method based on
    `operation`.
    """
    logger.info(f"Retrying '{action}' operation for {record_id}")
    method = getattr(client, action)
    if action == "index":
        method_args = {"index": index, "id": record_id, "body": body}
    elif action == "update":
        method_args = {"index": index, "id": record_id, "body": {"doc": body}}
    elif action == "delete":
        method_args = {
            "index": index,
            "id": record_id,
        }

    return method(**method_args)
