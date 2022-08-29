import logging
import os
from typing import Optional

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError

from tim.config import PRIMARY_ALIAS

logger = logging.getLogger(__name__)


# Cluster functions


def configure_opensearch_client(url: str) -> OpenSearch:
    """Return an OpenSearch client configured with the supplied URL.

    Includes the appropriate AWS credentials configuration if the URL is not localhost.
    """
    if url == "localhost":
        return OpenSearch(
            hosts=[{"host": url, "port": "9200"}],
            http_auth=("admin", "admin"),
            connection_class=RequestsHttpConnection,
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
    if aliases := get_aliases(client):
        output = ""
        for alias, indexes in sorted(aliases.items()):
            output += f"\nAlias: {alias}"
            output += f"\n  Indexes: {', '.join(sorted(indexes))}\n"
        return output
    return "\nNo aliases present in OpenSearch cluster.\n"


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
    if indexes := get_indexes(client):
        output = ""
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
    return "\nNo indexes present in OpenSearch cluster.\n"


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
                index for index in indexes if index.split("-")[0] == source
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


def get_index_aliases(client: OpenSearch, index: str) -> Optional[list[str]]:
    """Return a sorted list of aliases assigned to an index.

    Returns None if the index has no aliases.
    """
    response = client.indices.get_alias(index=index)
    logger.debug(response)
    aliases = response[index].get("aliases")
    return sorted(aliases.keys()) or None


def promote_index(
    client: OpenSearch, index: str, extra_aliases: Optional[tuple[str]] = None
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
    source = index.split("-")[0]
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
        raise ValueError(f"Index '{index}' not present in Cluster.") from error
