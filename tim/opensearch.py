import os
from operator import itemgetter

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection


def configure_opensearch_client(url: str) -> OpenSearch:
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


def get_info(client: OpenSearch) -> str:
    response = client.info()
    return (
        f"\nName: {response['cluster_name']}"
        f"\nUUID: {response['cluster_uuid']}"
        f"\nOpenSearch version: {response['version']['number']}"
        f"\nLucene version: {response['version']['lucene_version']}\n"
    )


def list_aliases(client: OpenSearch) -> str:
    response_list = client.cat.aliases(format="json")
    if not response_list:
        return "No aliases present in OpenSearch cluster."

    aliases: dict = {}
    for item in response_list:
        aliases.setdefault(item["alias"], []).append(item["index"])

    output = ""
    for alias, indices in aliases.items():
        output += f"\nAlias: {alias}"
        indexes = ", ".join(sorted(indices))
        output += f"\n  Indexes: {indexes}\n"
    return output


def list_indexes(client: OpenSearch) -> str:
    indices_response = client.cat.indices(format="json")
    if not indices_response:
        return "No indexes present in OpenSearch cluster."

    output = ""
    indexes = sorted(indices_response, key=itemgetter("index"))
    for index in indexes:
        index_name = index["index"]
        aliases_response = client.indices.get_alias(index=index_name)
        aliases = aliases_response[index_name]["aliases"].keys()
        output += (
            f"\nName: {index_name}\n"
            f"  Aliases: {', '.join(aliases) or 'None'}\n"
            f"  Status: {index['status']}\n"
            f"  Health: {index['health']}\n"
            f"  Documents: {int(index['docs.count']):,}\n"
            f"  Primary store size: {index['pri.store.size']}\n"
            f"  Total store size: {index['store.size']}\n"
            f"  UUID: {index['uuid']}\n"
        )
    return output
