import logging
import os
from typing import Optional

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

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


# Index functions


def get_index_aliases(client: OpenSearch, index: str) -> Optional[list[str]]:
    """Return a sorted list of aliases assigned to an index.

    Returns None if the index has no aliases.
    """
    response = client.indices.get_alias(index=index)
    logger.debug(response)
    aliases = response[index].get("aliases")
    return sorted(aliases.keys()) or None
