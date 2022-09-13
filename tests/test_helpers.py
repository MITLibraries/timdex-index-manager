import pytest
from freezegun import freeze_time

from tim import helpers


def test_confirm_action_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert helpers.confirm_action("test-index", "delete") is True


def test_confirm_action_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert helpers.confirm_action("test-index", "delete") is False


def test_confirm_action_invalid(capsys, monkeypatch):
    inputs = iter(["wrong", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    assert helpers.confirm_action("test-index", "delete") is True
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


def test_generate_bulk_actions_invalid_action_raises_error():
    records = [{"timdex_record_id": "12345", "other_fields": "some_data"}]
    actions = helpers.generate_bulk_actions("test-index", records, "wrong")
    with pytest.raises(ValueError) as error:
        next(actions)
        assert "Invalid action parameter" in str(error.value)


def test_get_source_from_index():
    assert helpers.get_source_from_index("test-index-12345-67890") == "test"


def test_get_source_from_index_without_dash():
    assert helpers.get_source_from_index("testsource") == "testsource"


def test_parse_records():
    records = list(helpers.parse_records("tests/fixtures/sample_records.json"))
    assert len(records) == 6
    assert isinstance(records[0], dict)
