from unittest import mock

import vcr

from tim.opensearch import configure_opensearch_client, get_info, list_indexes


def test_configure_opensearch_client_for_localhost():
    result = configure_opensearch_client("localhost")
    assert str(result) == "<OpenSearch([{'host': 'localhost', 'port': '9200'}])>"


@mock.patch("boto3.session.Session")
def test_configure_opensearch_client_for_aws(mocked_boto3_session):  # noqa
    result = configure_opensearch_client("fake-dev.us-east-1.es.amazonaws.com")
    assert (
        str(result) == "<OpenSearch([{'host': 'fake-dev.us-east-1.es.amazonaws.com', "
        "'port': '443'}])>"
    )


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_get_info(test_opensearch_client):
    assert get_info(test_opensearch_client) == (
        "\nName: docker-cluster"
        "\nUUID: j7tpRLtKTsSRlyng3RELug"
        "\nOpenSearch version: 1.3.3"
        "\nLucene version: 8.10.1"
        "\n"
    )


@vcr.use_cassette("tests/fixures/cassettes/list_indexes.yaml")
def test_list_indexes(test_opensearch_client):
    assert list_indexes(test_opensearch_client) == (
        "\nName: test-index"
        "\n\tStatus: open"
        "\n\tHealth: yellow"
        "\n\tDocuments: 0"
        "\n\tPrimary store size: 208b"
        "\n\tTotal store size: 208b"
        "\n\tUUID: xERdq2rbQUy1IgtP5-ydVg"
        "\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/list_indexes_none_present.yaml")
def test_list_indexes_no_indexes_present(test_opensearch_client):
    assert list_indexes(test_opensearch_client) == (
        "No indexes present in OpenSearch cluster."
    )
