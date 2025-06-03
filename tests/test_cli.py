import json
import re
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from tim.cli import main
from tim.errors import BulkIndexingError

from .conftest import EXIT_CODES, my_vcr


def escape_ansi(line):
    """Escape ANSI color codes that are added to CLI output by rich-click."""
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_no_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_all_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["--verbose", "--url", "localhost", "ping"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Logger 'root' configured with level=DEBUG" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_options_from_env_configures_correctly_and_invokes_result_callback(
    caplog, runner
):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("get_aliases.yaml")
def test_aliases(runner):
    result = runner.invoke(main, ["aliases"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Alias: alias-with-multiple-indexes" in result.stdout


@my_vcr.use_cassette("get_indexes.yaml")
def test_indexes(runner):
    result = runner.invoke(main, ["indexes"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Name: index-with-multiple-aliases" in result.stdout


@my_vcr.use_cassette("ping_localhost.yaml")
def test_ping(runner):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Name: docker-cluster" in result.stdout


def test_create_index_neither_name_nor_source_passed(runner):
    result = runner.invoke(main, ["create"])
    assert result.exit_code == EXIT_CODES["invalid_command"]
    assert "Must provide either a name or source for the new index." in result.stderr


def test_create_index_name_and_source_passed(runner):
    result = runner.invoke(
        main,
        ["create", "--index", "aspace-2022-09-01t12-34-56", "--source", "aspace"],
    )
    assert result.exit_code == EXIT_CODES["invalid_command"]
    assert (
        "Only one of --index and --source options is allowed, not both."
        in escape_ansi(result.stderr)
    )


def test_create_index_invalid_name_passed(runner):
    result = runner.invoke(main, ["create", "--index", "wrong"])
    assert result.exit_code == EXIT_CODES["invalid_command"]


def test_create_index_invalid_source_passed(runner):
    result = runner.invoke(main, ["create", "--source", "wrong"])
    assert result.exit_code == EXIT_CODES["invalid_command"]


@my_vcr.use_cassette("cli/create_index_exists.yaml")
def test_create_index_exists(caplog, runner):
    result = runner.invoke(main, ["create", "--index", "aspace-2022-09-20t15-59-38"])
    assert result.exit_code == EXIT_CODES["error"]
    assert (
        "tim.cli",
        40,
        "Index 'aspace-2022-09-20t15-59-38' already exists in the cluster, cannot "
        "create.",
    ) in caplog.record_tuples


@freeze_time("2022-09-01")
@my_vcr.use_cassette("cli/create_index_success.yaml")
def test_create_index_success(caplog, runner):
    result = runner.invoke(main, ["create", "--source", "aspace"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index 'aspace-2022-09-01t00-00-00' created." in caplog.text


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_index_with_force(runner):
    result = runner.invoke(main, ["delete", "-i", "test-index", "-f"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_index_with_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_without_confirmation.yaml")
def test_delete_index_without_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["error"]
    assert "Ok, index will not be deleted." in result.stdout


@my_vcr.use_cassette("demote_no_aliases_for_index.yaml")
def test_demote_index_no_aliases_for_index(runner):
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["error"]
    assert (
        "Index 'test-index' has no aliases, please check aliases and try again."
        in result.stdout
    )


@my_vcr.use_cassette("demote_from_primary_alias_with_confirmation.yaml")
def test_demote_index_from_primary_alias_with_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index 'test-index' demoted from aliases: ['all-current']" in result.stdout


@my_vcr.use_cassette("demote_from_primary_alias_without_confirmation.yaml")
def test_demote_index_from_primary_alias_without_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["error"]
    assert "Ok, index will not be demoted." in result.stdout


@my_vcr.use_cassette("demote_no_primary_alias.yaml")
def test_demote_index_no_primary_alias(runner):
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index 'test-index' demoted from aliases: ['not-primary']" in result.stdout


@my_vcr.use_cassette("promote_index.yaml")
def test_promote_index(caplog, runner):
    result = runner.invoke(main, ["promote", "-i", "testsource-index"])
    assert result.exit_code == EXIT_CODES["success"]
    assert "Index promoted" in caplog.text


# Test bulk record processing commands


@patch("timdex_dataset_api.dataset.TIMDEXDataset.load")
@patch("tim.helpers.validate_bulk_cli_options")
@patch("tim.opensearch.bulk_delete")
@patch("tim.opensearch.bulk_index")
def test_bulk_update_with_source_success(
    mock_bulk_index,
    mock_bulk_delete,
    mock_validate_bulk_cli_options,
    mock_timdex_dataset,
    caplog,
    monkeypatch,
    runner,
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    mock_bulk_index.return_value = {
        "created": 1000,
        "updated": 0,
        "errors": 0,
        "total": 1000,
    }
    mock_bulk_delete.return_value = {"deleted": 0, "errors": 0, "total": 0}
    mock_validate_bulk_cli_options.return_value = "alma"
    mock_timdex_dataset.return_value = MagicMock()

    result = runner.invoke(
        main,
        [
            "bulk-update",
            "--source",
            "alma",
            "--run-date",
            "2024-12-01",
            "--run-id",
            "abc123",
            "s3://test-timdex-bucket/dataset",
        ],
    )
    assert result.exit_code == EXIT_CODES["success"]
    assert (
        "Bulk update complete: "
        f'{{"index": {json.dumps(mock_bulk_index())}, '
        f'"delete": {json.dumps(mock_bulk_delete())}}}' in caplog.text
    )


@patch("timdex_dataset_api.dataset.TIMDEXDataset.load")
@patch("tim.helpers.validate_bulk_cli_options")
@patch("tim.opensearch.bulk_delete")
@patch("tim.opensearch.bulk_index")
def test_bulk_update_with_source_raise_bulk_indexing_error(
    mock_bulk_index,
    mock_bulk_delete,
    mock_validate_bulk_cli_options,
    mock_timdex_dataset,
    caplog,
    monkeypatch,
    runner,
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    mock_bulk_index.side_effect = BulkIndexingError(
        record="alma:0", index="index", error="exception"
    )
    mock_bulk_delete.return_value = {"deleted": 0, "errors": 0, "total": 0}
    mock_validate_bulk_cli_options.return_value = "alma"
    mock_timdex_dataset.return_value = MagicMock()

    index_results_default = {
        "created": 0,
        "updated": 0,
        "errors": 0,
        "total": 0,
    }

    result = runner.invoke(
        main,
        [
            "bulk-update",
            "--source",
            "alma",
            "--run-date",
            "2024-12-01",
            "--run-id",
            "abc123",
            "s3://test-timdex-bucket/dataset",
        ],
    )
    assert result.exit_code == EXIT_CODES["success"]
    assert (
        "Bulk update complete: "
        f'{{"index": {json.dumps(index_results_default)}, '
        f'"delete": {json.dumps(mock_bulk_delete())}}}' in caplog.text
    )
