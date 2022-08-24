from unittest import mock

import vcr

from tim import opensearch as tim_os


def test_configure_opensearch_client_for_localhost():
    result = tim_os.configure_opensearch_client("localhost")
    assert str(result) == "<OpenSearch([{'host': 'localhost', 'port': '9200'}])>"


@mock.patch("boto3.session.Session")
def test_configure_opensearch_client_for_aws(mocked_boto3_session):  # noqa
    result = tim_os.configure_opensearch_client("fake-dev.us-east-1.es.amazonaws.com")
    assert (
        str(result) == "<OpenSearch([{'host': 'fake-dev.us-east-1.es.amazonaws.com', "
        "'port': '443'}])>"
    )


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_get_info(test_opensearch_client):
    assert tim_os.get_info(test_opensearch_client) == (
        "\nName: docker-cluster"
        "\nUUID: j7tpRLtKTsSRlyng3RELug"
        "\nOpenSearch version: 1.3.3"
        "\nLucene version: 8.10.1"
        "\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/list_aliases.yaml")
def test_list_aliases(test_opensearch_client):
    assert tim_os.list_aliases(test_opensearch_client) == (
        "\nAlias: alias-with-multiple-indexes"
        "\n  Indexes: index-with-multiple-aliases, index-with-one-alias\n"
        "\nAlias: alias-with-one-index"
        "\n  Indexes: index-with-multiple-aliases\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/list_aliases_none_present.yaml")
def test_list_aliases_no_aliases_present(test_opensearch_client):
    assert tim_os.list_aliases(test_opensearch_client) == (
        "No aliases present in OpenSearch cluster."
    )


@vcr.use_cassette("tests/fixtures/cassettes/list_indexes.yaml")
def test_list_indexes(test_opensearch_client):
    assert tim_os.list_indexes(test_opensearch_client) == (
        "\nName: index-with-multiple-aliases"
        "\n  Aliases: alias-with-multiple-indexes, alias-with-one-index"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: 60Gq-vaAScOKGXkG_JAw5A"
        "\n"
        "\nName: index-with-no-aliases"
        "\n  Aliases: None"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: KqVlOA5lTw-fXZA2TEqi_g"
        "\n"
        "\nName: index-with-one-alias"
        "\n  Aliases: alias-with-multiple-indexes"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: q-NKXPp3SuWiDKhPkUxP-g"
        "\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/list_indexes_none_present.yaml")
def test_list_indexes_no_indexes_present(test_opensearch_client):
    assert tim_os.list_indexes(test_opensearch_client) == (
        "No indexes present in OpenSearch cluster."
    )
