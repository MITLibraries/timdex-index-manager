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
        f"\nName: {response['cluster_name']}\n"
        f"UUID: {response['cluster_uuid']}\n"
        f"OpenSearch version: {response['version']['number']}\n"
        f"Lucene version: {response['version']['lucene_version']}\n"
    )


def list_indexes(client: OpenSearch) -> str:
    response = client.cat.indices(format="json")
    if not response:
        return "No indexes present in OpenSearch cluster."
    indices = sorted(response, key=itemgetter("index"))
    output = ""
    for index in indices:
        output += (
            f"\nName: {index['index']}\n"
            f"\tStatus: {index['status']}\n"
            f"\tHealth: {index['health']}\n"
            f"\tDocuments: {int(index['docs.count']):,}\n"
            f"\tPrimary store size: {index['pri.store.size']}\n"
            f"\tTotal store size: {index['store.size']}\n"
            f"\tUUID: {index['uuid']}\n"
        )
    return output
