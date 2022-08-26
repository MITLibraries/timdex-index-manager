from unittest import mock

import vcr

from tim import opensearch as tim_os

# Cluster functions


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
def test_get_formatted_info(test_opensearch_client):
    assert tim_os.get_formatted_info(test_opensearch_client) == (
        "\nName: docker-cluster"
        "\nUUID: j7tpRLtKTsSRlyng3RELug"
        "\nOpenSearch version: 1.3.3"
        "\nLucene version: 8.10.1"
        "\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/get_aliases.yaml")
def test_get_aliases(test_opensearch_client):
    assert tim_os.get_aliases(test_opensearch_client) == {
        "alias-with-multiple-indexes": [
            "index-with-one-alias",
            "index-with-multiple-aliases",
        ],
        "alias-with-one-index": ["index-with-multiple-aliases"],
    }


@vcr.use_cassette("tests/fixtures/cassettes/get_aliases_none_present.yaml")
def test_get_aliases_no_aliases_present(test_opensearch_client):
    assert tim_os.get_aliases(test_opensearch_client) is None


@vcr.use_cassette("tests/fixtures/cassettes/get_aliases.yaml")
def test_get_formatted_aliases(test_opensearch_client):
    assert tim_os.get_formatted_aliases(test_opensearch_client) == (
        "\nAlias: alias-with-multiple-indexes"
        "\n  Indexes: index-with-multiple-aliases, index-with-one-alias\n"
        "\nAlias: alias-with-one-index"
        "\n  Indexes: index-with-multiple-aliases\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/get_aliases_none_present.yaml")
def test_get_formatted_aliases_no_aliases_present(test_opensearch_client):
    assert tim_os.get_formatted_aliases(test_opensearch_client) == (
        "\nNo aliases present in OpenSearch cluster.\n"
    )


@vcr.use_cassette("tests/fixtures/cassettes/get_indexes.yaml")
def test_get_indexes(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) == {
        "index-with-multiple-aliases": {
            "docs.count": "0",
            "docs.deleted": "0",
            "health": "yellow",
            "pri": "1",
            "pri.store.size": "208b",
            "rep": "1",
            "status": "open",
            "store.size": "208b",
            "uuid": "60Gq-vaAScOKGXkG_JAw5A",
        },
        "index-with-no-aliases": {
            "docs.count": "0",
            "docs.deleted": "0",
            "health": "yellow",
            "pri": "1",
            "pri.store.size": "208b",
            "rep": "1",
            "status": "open",
            "store.size": "208b",
            "uuid": "KqVlOA5lTw-fXZA2TEqi_g",
        },
        "index-with-one-alias": {
            "docs.count": "0",
            "docs.deleted": "0",
            "health": "yellow",
            "pri": "1",
            "pri.store.size": "208b",
            "rep": "1",
            "status": "open",
            "store.size": "208b",
            "uuid": "q-NKXPp3SuWiDKhPkUxP-g",
        },
    }


@vcr.use_cassette("tests/fixtures/cassettes/get_indexes.yaml")
def test_get_formatted_indexes(test_opensearch_client):
    assert tim_os.get_formatted_indexes(test_opensearch_client) == (
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


@vcr.use_cassette("tests/fixtures/cassettes/get_indexes_none_present.yaml")
def test_get_formatted_indexes_no_indexes_present(test_opensearch_client):
    assert tim_os.get_formatted_indexes(test_opensearch_client) == (
        "\nNo indexes present in OpenSearch cluster.\n"
    )


# Index functions


@vcr.use_cassette("tests/fixtures/cassettes/get_index_aliases_none_present.yaml")
def test_get_index_aliases_no_aliases_set(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") is None


@vcr.use_cassette("tests/fixtures/cassettes/get_index_aliases.yaml")
def test_get_index_aliases_returns_sorted_aliases(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") == [
        "bird",
        "cat",
        "dog",
        "fish",
    ]
