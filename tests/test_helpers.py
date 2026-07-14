from unittest.mock import Mock, patch

import pytest
from click.exceptions import BadParameter
from freezegun import freeze_time
from opensearchpy.exceptions import NotFoundError, RequestError, TransportError

from tim import helpers
from tim.errors import RetryFailedWithUnexpectedError


@freeze_time("2026-07-09 10:00:00", auto_tick_seconds=10)
@patch("tim.helpers.time.sleep")
def test_retry_decorator_with_sleep_success(mock_sleep):
    """Retry resulting in retryable error returns success within allowed time."""
    # init TransportError with 507 status
    retryable_error = TransportError(507, "Insufficient Storage")

    # mock method that yields TransportError to force retry
    # then yields success after retry
    hello_world = Mock()
    hello_world.__name__ = "hello_world"
    hello_world.side_effect = [retryable_error, "Hello"]

    wrapped_hello_world = helpers.retry()(hello_world)

    assert wrapped_hello_world() == "Hello"
    assert hello_world.call_count == 2  # noqa: PLR2004


@patch("tim.helpers.time.sleep")
def test_retry_decorator_with_sleep_raises_timeout_error(mock_sleep):
    """Retry resulting in retryable error raises error if timeout reached."""
    # init TransportError with 507 status
    retryable_error = TransportError(507, "Insufficient Storage")

    # mock method that yields TransportError to force retry
    # then yields success after retry
    hello_world = Mock()
    hello_world.__name__ = "hello_world"
    hello_world.side_effect = retryable_error

    wrapped_hello_world = helpers.retry(max_attempts=2)(hello_world)

    with pytest.raises(TimeoutError):
        wrapped_hello_world()
    assert hello_world.call_count == 2  # noqa: PLR2004


@patch("tim.helpers.time.sleep")
def test_retry_decorator_without_sleep(mock_sleep):
    """Retry resulting in success returns immediately."""

    @helpers.retry()
    def hello_world():
        return "Hello"

    result = hello_world()

    assert result == "Hello"
    assert mock_sleep.call_count == 0


@patch("tim.helpers.time.sleep")
def test_retry_decorator_raises_retry_failed_with_unexpected_error(mock_sleep):
    """Retry resulting in unexpected error raises error."""

    @helpers.retry()
    def hello_world():
        raise Exception("Unexpected error")  # noqa: TRY002

    with pytest.raises(RetryFailedWithUnexpectedError):
        hello_world()


@patch("tim.helpers.time.sleep")
def test_retry_decorator_raises_not_found_error(mock_sleep):
    """Retry raises NotFoundError caused by missing documents."""

    @helpers.retry()
    def hello_world():
        raise NotFoundError

    with pytest.raises(NotFoundError):
        hello_world()


@patch("tim.helpers._is_mapper_parsing_exception")
@patch("tim.helpers.time.sleep")
def test_retry_decorator_raises_mapper_parsing_request_error(
    mock_sleep, mock_is_mapper_parsing_exception
):
    """Retry raises RequestError caused by mapper parsing exception."""
    mock_is_mapper_parsing_exception.return_value = True

    @helpers.retry()
    def hello_world():
        raise RequestError

    with pytest.raises(RequestError):
        hello_world()


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


def test_generate_bulk_actions_update():
    records = [{"timdex_record_id": "12345"}]
    actions = helpers.generate_bulk_actions("test-index", records, "update")
    assert next(actions) == {
        "_op_type": "update",
        "_index": "test-index",
        "_id": "12345",
        "doc": {"timdex_record_id": "12345"},
    }


def test_generate_bulk_actions_invalid_action_raises_error():
    records = [{"timdex_record_id": "12345", "other_fields": "some_data"}]
    actions = helpers.generate_bulk_actions("test-index", records, "wrong")
    with pytest.raises(ValueError, match=r"Invalid action parameter"):
        next(actions)


def test_get_source_from_index():
    assert helpers.get_source_from_index("test-index-12345-67890") == "test"


def test_get_source_from_index_without_dash():
    assert helpers.get_source_from_index("testsource") == "testsource"


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
