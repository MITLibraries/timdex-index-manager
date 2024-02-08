import pytest
from click.exceptions import BadParameter, UsageError
from freezegun import freeze_time

from tim import helpers

from .conftest import my_vcr


def test_confirm_action_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert helpers.confirm_action("delete test-index") is True


def test_confirm_action_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert helpers.confirm_action("delete test-index") is False


def test_confirm_action_invalid(capsys, monkeypatch):
    inputs = iter(["wrong", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert helpers.confirm_action("delete test-index") is True
    out, _ = capsys.readouterr()
    assert out == "Invalid input: 'wrong', must be one of 'y' or 'n'.\n"


@freeze_time("2022-09-01")
def test_generate_index_name():
    assert helpers.generate_index_name("test") == "test-2022-09-01t00-00-00"


def test_generate_bulk_actions():
    records = [{"timdex_record_id": "12345", "other_fields": "some_data"}]
    actions = helpers.generate_bulk_actions("test-index", records, "create")
    assert next(actions) == {
        "_op_type": "create",
        "_index": "test-index",
        "_id": "12345",
        "_source": {"timdex_record_id": "12345", "other_fields": "some_data"},
    }


def test_generate_bulk_actions_delete():
    records = [{"timdex_record_id": "12345"}]
    actions = helpers.generate_bulk_actions("test-index", records, "delete")
    assert next(actions) == {
        "_op_type": "delete",
        "_index": "test-index",
        "_id": "12345",
    }


def test_generate_bulk_actions_invalid_action_raises_error():
    records = [{"timdex_record_id": "12345", "other_fields": "some_data"}]
    actions = helpers.generate_bulk_actions("test-index", records, "wrong")
    with pytest.raises(ValueError, match="Invalid action parameter"):
        next(actions)


def test_get_source_from_index():
    assert helpers.get_source_from_index("test-index-12345-67890") == "test"


def test_get_source_from_index_without_dash():
    assert helpers.get_source_from_index("testsource") == "testsource"


def test_parse_records():
    records = list(helpers.parse_records("tests/fixtures/sample_records.json"))
    n_sample_records = 6
    assert len(records) == n_sample_records
    assert isinstance(records[0], dict)


def test_parse_deleted_records():
    records = list(
        helpers.parse_deleted_records("tests/fixtures/sample_deleted_records.txt")
    )
    n_sample_deleted_records = 3
    assert len(records) == n_sample_deleted_records
    assert isinstance(records[0], dict)


def test_validate_bulk_cli_options_neither_index_nor_source_passed(
    test_opensearch_client,
):
    with pytest.raises(
        UsageError, match="Must provide either an existing index name or a valid source."
    ):
        helpers.validate_bulk_cli_options(None, None, test_opensearch_client)


def test_validate_bulk_cli_options_index_and_source_passed(test_opensearch_client):
    with pytest.raises(
        UsageError, match="Only one of --index and --source options is allowed, not both."
    ):
        helpers.validate_bulk_cli_options(
            "index-name", "source-name", test_opensearch_client
        )


@my_vcr.use_cassette("helpers/bulk_cli_nonexistent_index.yaml")
def test_validate_bulk_cli_options_nonexistent_index_passed(test_opensearch_client):
    with pytest.raises(
        BadParameter, match="Index 'wrong' does not exist in the cluster."
    ):
        helpers.validate_bulk_cli_options("wrong", None, test_opensearch_client)


@my_vcr.use_cassette("helpers/bulk_cli_no_primary_index_for_source.yaml")
def test_validate_bulk_cli_options_no_primary_index_for_source(test_opensearch_client):
    with pytest.raises(
        BadParameter,
        match=(
            "No index name was passed and there is no "
            "primary-aliased index for source 'dspace'."
        ),
    ):
        helpers.validate_bulk_cli_options(None, "dspace", test_opensearch_client)


def test_validate_index_name_no_value():
    assert helpers.validate_index_name({}, "name", None) is None


def test_validate_index_name_invalid_date():
    with pytest.raises(BadParameter):
        helpers.validate_index_name({}, "name", "aspace-2022-09-01t13:14:15")


def test_validate_index_name_invalid_source():
    with pytest.raises(BadParameter):
        helpers.validate_index_name({}, "name", "wrong-2022-09-01t13-14-15")


def test_validate_index_name_invalid_syntax():
    with pytest.raises(BadParameter):
        helpers.validate_index_name({}, "name", "everythingaboutthisiswrong")


def test_validate_index_name_success():
    assert (
        helpers.validate_index_name({}, "name", "aspace-2022-09-01t13-14-15")
        == "aspace-2022-09-01t13-14-15"
    )
