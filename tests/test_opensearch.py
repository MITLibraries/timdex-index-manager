import logging
from unittest import mock

import pytest
from freezegun import freeze_time
from opensearchpy.exceptions import NotFoundError, RequestError

from tim import opensearch as tim_os
from tim.config import PRIMARY_ALIAS
from tim.errors import (
    AliasNotFoundError,
    IndexExistsError,
    IndexNotFoundError,
)

from .conftest import my_vcr

# Cluster functions


def test_configure_opensearch_client_for_localhost():
    result = tim_os.configure_opensearch_client("localhost")
    assert str(result) == "<OpenSearch([{'host': 'localhost', 'port': '9200'}])>"


def test_configure_opensearch_client_for_local_opensearch_host():
    result = tim_os.configure_opensearch_client("opensearch")
    assert str(result) == "<OpenSearch([{'host': 'opensearch', 'port': '9200'}])>"


@mock.patch("boto3.session.Session")
def test_configure_opensearch_client_for_aws(mocked_boto3_session):
    result = tim_os.configure_opensearch_client("fake-dev.us-east-1.es.amazonaws.com")
    assert (
        str(result) == "<OpenSearch([{'host': 'fake-dev.us-east-1.es.amazonaws.com', "
        "'port': '443'}])>"
    )


@my_vcr.use_cassette("ping_localhost.yaml")
def test_get_formatted_info(test_opensearch_client):
    assert tim_os.get_formatted_info(test_opensearch_client) == (
        "\nName: docker-cluster"
        "\nUUID: j7tpRLtKTsSRlyng3RELug"
        "\nOpenSearch version: 1.3.3"
        "\nLucene version: 8.10.1"
        "\n"
    )


@my_vcr.use_cassette("get_aliases.yaml")
def test_get_aliases(test_opensearch_client):
    assert tim_os.get_aliases(test_opensearch_client) == {
        "alias-with-multiple-indexes": [
            "index-with-one-alias",
            "index-with-multiple-aliases",
        ],
        "alias-with-one-index": ["index-with-multiple-aliases"],
    }


@my_vcr.use_cassette("get_aliases_none_present.yaml")
def test_get_aliases_no_aliases_present(test_opensearch_client):
    assert tim_os.get_aliases(test_opensearch_client) is None


@my_vcr.use_cassette("get_aliases.yaml")
def test_get_formatted_aliases(test_opensearch_client):
    assert tim_os.get_formatted_aliases(test_opensearch_client) == (
        "Current state of all aliases:"
        "\nAlias: alias-with-multiple-indexes"
        "\n  Indexes: index-with-multiple-aliases, index-with-one-alias\n"
        "\nAlias: alias-with-one-index"
        "\n  Indexes: index-with-multiple-aliases\n"
    )


@my_vcr.use_cassette("get_aliases_none_present.yaml")
def test_get_formatted_aliases_no_aliases_present(test_opensearch_client):
    assert tim_os.get_formatted_aliases(test_opensearch_client) == (
        "Current state of all aliases:\nNo aliases present in OpenSearch cluster.\n"
    )


@my_vcr.use_cassette("get_indexes.yaml")
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


@my_vcr.use_cassette("get_indexes.yaml")
def test_get_formatted_indexes(test_opensearch_client):
    assert tim_os.get_formatted_indexes(test_opensearch_client) == (
        "Current state of all indexes:\n"
        "\nName: index-with-multiple-aliases"
        "\n  Aliases: alias-with-multiple-indexes, alias-with-one-index"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: 60Gq-vaAScOKGXkG_JAw5A"
        "\n  Primary Shards: 1"
        "\n  Replica Shards: 1"
        "\n"
        "\nName: index-with-no-aliases"
        "\n  Aliases: None"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: KqVlOA5lTw-fXZA2TEqi_g"
        "\n  Primary Shards: 1"
        "\n  Replica Shards: 1"
        "\n"
        "\nName: index-with-one-alias"
        "\n  Aliases: alias-with-multiple-indexes"
        "\n  Status: open"
        "\n  Health: yellow"
        "\n  Documents: 0"
        "\n  Primary store size: 208b"
        "\n  Total store size: 208b"
        "\n  UUID: q-NKXPp3SuWiDKhPkUxP-g"
        "\n  Primary Shards: 1"
        "\n  Replica Shards: 1"
        "\n"
    )


@my_vcr.use_cassette("get_indexes_none_present.yaml")
def test_get_formatted_indexes_no_indexes_present(test_opensearch_client):
    assert tim_os.get_formatted_indexes(test_opensearch_client) == (
        "Current state of all indexes: No indexes present in OpenSearch cluster."
    )


@my_vcr.use_cassette("get_all_aliased_indexes_for_source.yaml")
def test_get_all_aliased_indexes_for_source(test_opensearch_client):
    assert tim_os.get_aliases(test_opensearch_client) == {
        "another-alias": ["testsource-index-two"],
        "primary-alias": ["othersource-index", "testsource-index-one"],
    }
    assert tim_os.get_all_aliased_indexes_for_source(
        test_opensearch_client, "testsource"
    ) == {
        "another-alias": ["testsource-index-two"],
        "primary-alias": ["testsource-index-one"],
    }


@my_vcr.use_cassette("get_all_aliased_indexes_for_source_no_aliases.yaml")
def test_get_all_aliased_indexes_for_source_no_aliases(test_opensearch_client):
    assert list(tim_os.get_indexes(test_opensearch_client).keys()) == ["testsource-index"]
    assert tim_os.get_aliases(test_opensearch_client) is None
    assert (
        tim_os.get_all_aliased_indexes_for_source(test_opensearch_client, "testsource")
        is None
    )


@my_vcr.use_cassette(
    "get_all_aliased_indexes_for_source_no_aliased_indexes_for_source.yaml"
)
def test_get_all_aliased_indexes_for_source_no_aliased_indexes_for_source(
    test_opensearch_client,
):
    assert list(tim_os.get_indexes(test_opensearch_client).keys()) == [
        "testsource-index",
        "othersource-index",
    ]
    assert tim_os.get_aliases(test_opensearch_client) == {
        "an-alias": ["othersource-index"]
    }
    assert (
        tim_os.get_all_aliased_indexes_for_source(test_opensearch_client, "testsource")
        is None
    )


@my_vcr.use_cassette(
    "get_all_aliased_indexes_for_source_mulitple_source_indexes_with_alias.yaml"
)
def test_get_all_aliased_indexes_for_source_multi_source_indexes_with_alias_logs_error(
    caplog, test_opensearch_client
):
    assert tim_os.get_aliases(test_opensearch_client) == {
        "an-alias": ["testsource-index-one", "testsource-index-two"]
    }
    assert tim_os.get_all_aliased_indexes_for_source(
        test_opensearch_client, "testsource"
    ) == {"an-alias": ["testsource-index-one", "testsource-index-two"]}

    assert (
        "tim.opensearch",
        logging.ERROR,
        "Alias 'an-alias' had multiple existing indexes for source "
        "'testsource': ['testsource-index-one', 'testsource-index-two']",
    ) in caplog.record_tuples


# Index functions


@my_vcr.use_cassette("opensearch/create_index_success.yaml")
def test_create_index_success(test_opensearch_client):
    assert tim_os.create_index(test_opensearch_client, "test-index") == "test-index"


@my_vcr.use_cassette("opensearch/create_index_exists.yaml")
@freeze_time("2022-09-01")
def test_create_index_exists_raises_error(test_opensearch_client):
    with pytest.raises(IndexExistsError):
        tim_os.create_index(test_opensearch_client, "aspace-2022-09-01t00-00-00")


@my_vcr.use_cassette("opensearch/create_index_other_error.yaml")
@freeze_time("2022-09-01")
def test_create_index_other_error_reraises(test_opensearch_client):
    with pytest.raises(RequestError):
        tim_os.create_index(test_opensearch_client, "aspace-2022-09-01t00-00-00")


@my_vcr.use_cassette("delete_index.yaml")
def test_delete_index(test_opensearch_client):
    assert "test-index" in tim_os.get_indexes(test_opensearch_client)
    tim_os.delete_index(test_opensearch_client, "test-index")
    assert tim_os.get_indexes(test_opensearch_client) is None


@my_vcr.use_cassette("delete_index_not_present.yaml")
def test_delete_index_not_present_raises_error(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) is None
    with pytest.raises(IndexNotFoundError):
        tim_os.delete_index(test_opensearch_client, "test-index")


@my_vcr.use_cassette("get_or_create_index_from_source_primary_index_exists.yaml")
def test_get_or_create_index_from_source_index_exists(test_opensearch_client):
    aliases = tim_os.get_aliases(test_opensearch_client)
    assert (
        "test-2022-09-01t00-00-00"
        in aliases[PRIMARY_ALIAS]  # pylint: disable=unsubscriptable-object
    )
    assert tim_os.get_or_create_index_from_source(
        test_opensearch_client, "test", new=False
    ) == ("test-2022-09-01t00-00-00", False)


@freeze_time("2022-09-01")
@my_vcr.use_cassette(
    "get_or_create_index_from_source_no_primary_source_index_present.yaml"
)
def test_get_or_create_index_from_source_no_primary_source_index_present(
    test_opensearch_client,
):
    assert tim_os.get_indexes(test_opensearch_client) is None
    assert tim_os.get_or_create_index_from_source(
        test_opensearch_client, "test", new=False
    ) == ("test-2022-09-01t00-00-00", True)


@freeze_time("2022-10-01")
@my_vcr.use_cassette("get_or_create_index_from_source_new_passed.yaml")
def test_get_or_create_index_from_source_new_passed(test_opensearch_client):
    aliases = tim_os.get_aliases(test_opensearch_client)
    assert (
        "test-2022-09-01t00-00-00"
        in aliases[PRIMARY_ALIAS]  # pylint: disable=unsubscriptable-object
    )
    assert tim_os.get_or_create_index_from_source(
        test_opensearch_client, "test", new=True
    ) == ("test-2022-10-01t00-00-00", True)


@my_vcr.use_cassette("get_index_aliases_index_not_present.yaml")
def test_get_index_aliases_index_not_present(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) is None
    with pytest.raises(IndexNotFoundError):
        tim_os.get_index_aliases(test_opensearch_client, "not-here")


@my_vcr.use_cassette("get_index_aliases_none_present.yaml")
def test_get_index_aliases_no_aliases_set(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") is None


@my_vcr.use_cassette("get_index_aliases.yaml")
def test_get_index_aliases_returns_sorted_aliases(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") == [
        "bird",
        "cat",
        "dog",
        "fish",
    ]


@my_vcr.use_cassette("get_primary_index_for_source.yaml")
def test_get_primary_index_for_source(test_opensearch_client):
    assert list(tim_os.get_indexes(test_opensearch_client).keys()) == [
        "test-2022-09-01t00-00-00",
        "test-2022-10-01t00-00-00",
    ]
    aliases = tim_os.get_aliases(test_opensearch_client)
    assert aliases[PRIMARY_ALIAS] == [  # pylint: disable=unsubscriptable-object
        "test-2022-09-01t00-00-00"
    ]
    assert (
        tim_os.get_primary_index_for_source(test_opensearch_client, "test")
        == "test-2022-09-01t00-00-00"
    )


@my_vcr.use_cassette("get_primary_index_for_source_no_primary_index.yaml")
def test_get_primary_index_for_source_no_primary_index(test_opensearch_client):
    assert "test-2022-10-01t00-00-00" in tim_os.get_indexes(test_opensearch_client)
    aliases = tim_os.get_aliases(test_opensearch_client)
    assert aliases[PRIMARY_ALIAS] == [  # pylint: disable=unsubscriptable-object
        "othersource-index"
    ]
    assert tim_os.get_primary_index_for_source(test_opensearch_client, "test") is None


@my_vcr.use_cassette("get_primary_index_for_source_no_index.yaml")
def test_get_primary_index_for_source_no_index(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) is None
    assert tim_os.get_primary_index_for_source(test_opensearch_client, "test") is None


@my_vcr.use_cassette("promote_index_to_primary_alias.yaml")
def test_promote_index_always_promotes_to_primary_alias(test_opensearch_client):
    assert "testsource-index" not in tim_os.get_aliases(test_opensearch_client).get(
        PRIMARY_ALIAS
    )
    tim_os.promote_index(test_opensearch_client, "testsource-index")
    assert "testsource-index" in tim_os.get_aliases(test_opensearch_client).get(
        PRIMARY_ALIAS
    )


@my_vcr.use_cassette("promote_index_demotes_existing.yaml")
def test_promote_index_promotes_to_existing_aliases_for_source_and_demotes_old_index(
    test_opensearch_client,
):
    assert tim_os.get_aliases(test_opensearch_client) == {
        PRIMARY_ALIAS: ["testsource-index", "othersource-index"],
        "existing-alias": ["testsource-index"],
    }
    tim_os.promote_index(test_opensearch_client, "testsource-new-index")
    assert tim_os.get_aliases(test_opensearch_client) == {
        PRIMARY_ALIAS: ["testsource-new-index", "othersource-index"],
        "existing-alias": ["testsource-new-index"],
    }


@my_vcr.use_cassette("promote_index_to_extra_aliases.yaml")
def test_promote_index_promotes_to_extra_aliases_and_creates_if_not_present(
    test_opensearch_client,
):
    assert tim_os.get_aliases(test_opensearch_client) == {
        PRIMARY_ALIAS: ["testsource-index", "othersource-index"],
        "existing-alias": ["othersource-index"],
    }
    tim_os.promote_index(
        test_opensearch_client,
        "testsource-index",
        extra_aliases=("existing-alias", "new-alias"),
    )
    assert tim_os.get_aliases(test_opensearch_client) == {
        PRIMARY_ALIAS: ["testsource-index", "othersource-index"],
        "existing-alias": ["testsource-index", "othersource-index"],
        "new-alias": ["testsource-index"],
    }


@my_vcr.use_cassette("promote_index_not_present.yaml")
def test_promote_index_not_present_raises_error(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) is None
    with pytest.raises(IndexNotFoundError):
        tim_os.promote_index(test_opensearch_client, "not-an-index")


@my_vcr.use_cassette("promote_index_unexpected_error.yaml")
def test_promote_index_unexpected_error_reraises(test_opensearch_client):
    with pytest.raises(NotFoundError):
        tim_os.promote_index(test_opensearch_client, "test-index")


@my_vcr.use_cassette("remove_alias_success.yaml")
def test_remove_alias_success(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") == [
        "all-current",
        "another-alias",
    ]
    tim_os.remove_alias(test_opensearch_client, "test-index", "all-current")
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") == [
        "another-alias"
    ]


@my_vcr.use_cassette("remove_alias_index_not_present.yaml")
def test_remove_alias_index_not_present_raises_error(test_opensearch_client):
    assert tim_os.get_indexes(test_opensearch_client) is None
    with pytest.raises(IndexNotFoundError):
        tim_os.remove_alias(test_opensearch_client, "test-index", "an-alias")


@my_vcr.use_cassette("remove_alias_not_associated_with_index.yaml")
def test_remove_alias_not_associated_with_index_raises_error(test_opensearch_client):
    assert tim_os.get_index_aliases(test_opensearch_client, "test-index") is None
    with pytest.raises(AliasNotFoundError):
        tim_os.remove_alias(test_opensearch_client, "test-index", "an-alias")


@my_vcr.use_cassette("remove_alias_unexpected_error.yaml")
def test_remove_alias_unexpected_error_reraises(test_opensearch_client):
    with pytest.raises(NotFoundError):
        tim_os.remove_alias(test_opensearch_client, "test-index", "an-alias")


# Record functions


@my_vcr.use_cassette("opensearch/bulk_index_create_records.yaml")
def test_bulk_index_creates_records(
    test_opensearch_client, five_valid_index_libguides_records
):
    assert tim_os.bulk_index(
        test_opensearch_client, "test-index", five_valid_index_libguides_records
    ) == {
        "created": 5,
        "updated": 0,
        "errors": 0,
        "total": 5,
    }


@my_vcr.use_cassette("opensearch/bulk_index_update_records.yaml")
def test_bulk_index_updates_records(
    caplog, monkeypatch, test_opensearch_client, five_valid_index_libguides_records
):
    monkeypatch.setenv("STATUS_UPDATE_INTERVAL", "5")
    assert tim_os.bulk_index(
        test_opensearch_client, "test-index", five_valid_index_libguides_records
    ) == {
        "created": 0,
        "updated": 5,
        "errors": 0,
        "total": 5,
    }
    assert "Status update: 5 records indexed so far!" in caplog.text


@my_vcr.use_cassette("opensearch/bulk_index_record_mapper_parsing_error.yaml")
def test_bulk_index_logs_mapper_parsing_errors(
    caplog, test_opensearch_client, one_invalid_index_libguides_records
):
    assert tim_os.bulk_index(
        test_opensearch_client, "test-index", one_invalid_index_libguides_records
    ) == {
        "created": 0,
        "updated": 0,
        "errors": 1,
        "total": 1,
    }
    assert "Error indexing record 'libguides:guides-175846'" in caplog.text


@my_vcr.use_cassette("opensearch/bulk_delete_records.yaml")
def test_bulk_delete_deletes_records(
    caplog, monkeypatch, test_opensearch_client, one_valid_delete_libguides_records
):
    assert tim_os.bulk_delete(
        test_opensearch_client,
        "test-index",
        one_valid_delete_libguides_records,
    ) == {
        "deleted": 1,
        "errors": 0,
        "total": 1,
    }


@my_vcr.use_cassette("opensearch/bulk_delete_record_not_found.yaml")
def test_bulk_delete_logs_error_if_record_not_found(
    caplog, test_opensearch_client, one_valid_delete_libguides_records_not_found
):
    caplog.set_level("DEBUG")
    assert tim_os.bulk_delete(
        test_opensearch_client,
        "test-index",
        one_valid_delete_libguides_records_not_found,
    ) == {
        "deleted": 0,
        "errors": 1,
        "total": 1,
    }
    assert (
        "Record to delete 'i-am-not-found' was not found in index 'test-index'."
        in caplog.text
    )
