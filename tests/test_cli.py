import re

from freezegun import freeze_time

from tim.cli import main

from .conftest import my_vcr


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
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_all_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["--verbose", "--url", "localhost", "ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=DEBUG" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_options_from_env_configures_correctly_and_invokes_result_callback(
    caplog, runner
):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("get_aliases.yaml")
def test_aliases(runner):
    result = runner.invoke(main, ["aliases"])
    assert result.exit_code == 0
    assert "Alias: alias-with-multiple-indexes" in result.stdout


@my_vcr.use_cassette("get_indexes.yaml")
def test_indexes(runner):
    result = runner.invoke(main, ["indexes"])
    assert result.exit_code == 0
    assert "Name: index-with-multiple-aliases" in result.stdout


@my_vcr.use_cassette("ping_localhost.yaml")
def test_ping(runner):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Name: docker-cluster" in result.stdout


def test_create_index_neither_name_nor_source_passed(runner):
    result = runner.invoke(main, ["create"])
    assert result.exit_code == 2
    assert "Must provide either a name or source for the new index." in result.stdout


def test_create_index_name_and_source_passed(runner):
    result = runner.invoke(
        main,
        ["create", "--index", "aspace-2022-09-01t12-34-56", "--source", "aspace"],
    )
    assert result.exit_code == 2
    assert (
        "Only one of --index and --source options is allowed, not both."
        in escape_ansi(result.stdout)
    )


def test_create_index_invalid_name_passed(runner):
    result = runner.invoke(main, ["create", "--index", "wrong"])
    assert result.exit_code == 2


def test_create_index_invalid_source_passed(runner):
    result = runner.invoke(main, ["create", "--source", "wrong"])
    assert result.exit_code == 2


@my_vcr.use_cassette("cli/create_index_exists.yaml")
def test_create_index_exists(caplog, runner):
    result = runner.invoke(main, ["create", "--index", "aspace-2022-09-20t15-59-38"])
    assert result.exit_code == 1
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
    assert result.exit_code == 0
    assert "Index 'aspace-2022-09-01t00-00-00' created." in caplog.text


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_index_with_force(runner):
    result = runner.invoke(main, ["delete", "-i", "test-index", "-f"])
    assert result.exit_code == 0
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_index_with_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == 0
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_without_confirmation.yaml")
def test_delete_index_without_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == 1
    assert "Ok, index will not be deleted." in result.stdout


@my_vcr.use_cassette("demote_no_aliases_for_index.yaml")
def test_demote_index_no_aliases_for_index(runner):
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == 1
    assert (
        "Index 'test-index' has no aliases, please check aliases and try again."
        in result.stdout
    )


@my_vcr.use_cassette("demote_from_primary_alias_with_confirmation.yaml")
def test_demote_index_from_primary_alias_with_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == 0
    assert "Index 'test-index' demoted from aliases: ['all-current']" in result.stdout


@my_vcr.use_cassette("demote_from_primary_alias_without_confirmation.yaml")
def test_demote_index_from_primary_alias_without_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == 1
    assert "Ok, index will not be demoted." in result.stdout


@my_vcr.use_cassette("demote_no_primary_alias.yaml")
def test_demote_index_no_primary_alias(runner):
    result = runner.invoke(main, ["demote", "-i", "test-index"])
    assert result.exit_code == 0
    assert "Index 'test-index' demoted from aliases: ['not-primary']" in result.stdout


@my_vcr.use_cassette("promote_index.yaml")
def test_promote_index(caplog, runner):
    result = runner.invoke(main, ["promote", "-i", "testsource-index"])
    assert result.exit_code == 0
    assert "Index promoted" in caplog.text


# Test bulk record processing commands


@freeze_time("2022-09-01")
@my_vcr.use_cassette("cli/bulk_index_with_index_name_success.yaml")
def test_bulk_index_with_index_name_success(caplog, runner):
    result = runner.invoke(
        main,
        [
            "bulk-index",
            "--index",
            "dspace-2022-09-01t00-00-00",
            "tests/fixtures/sample_records.json",
        ],
    )
    assert result.exit_code == 0
    assert (
        "Bulk indexing records from file 'tests/fixtures/sample_records.json' into "
        "index 'dspace-2022-09-01t00-00-00'" in caplog.text
    )
    assert "Bulk indexing complete!" in caplog.text


@freeze_time("2022-09-01")
@my_vcr.use_cassette("cli/bulk_index_with_source_success.yaml")
def test_bulk_index_with_source_success(caplog, runner):
    result = runner.invoke(
        main,
        ["bulk-index", "--source", "dspace", "tests/fixtures/sample_records.json"],
    )
    assert result.exit_code == 0
    assert (
        "Bulk indexing records from file 'tests/fixtures/sample_records.json' into "
        "index 'dspace-2022-09-01t00-00-00'" in caplog.text
    )
    assert "Bulk indexing complete!" in caplog.text


@freeze_time("2022-09-01")
@my_vcr.use_cassette("cli/bulk_delete_with_index_name_success.yaml")
def test_bulk_delete_with_index_name_success(caplog, runner):
    result = runner.invoke(
        main,
        [
            "bulk-delete",
            "--index",
            "alma-2022-09-01t00-00-00",
            "tests/fixtures/sample_deleted_records.txt",
        ],
    )
    assert result.exit_code == 0
    assert (
        "Bulk deleting records in file 'tests/fixtures/sample_deleted_records.txt' "
        "from index 'alma-2022-09-01t00-00-00'" in caplog.text
    )
    assert "Bulk deletion complete!" in caplog.text


@freeze_time("2022-09-01")
@my_vcr.use_cassette("cli/bulk_delete_with_source_success.yaml")
def test_bulk_delete_with_source_success(caplog, runner):
    result = runner.invoke(
        main,
        [
            "bulk-delete",
            "--source",
            "alma",
            "tests/fixtures/sample_deleted_records.txt",
        ],
    )
    assert result.exit_code == 0
    assert (
        "Bulk deleting records in file 'tests/fixtures/sample_deleted_records.txt' "
        "from index 'alma-2022-09-01t00-00-00'" in caplog.text
    )
    assert "Bulk deletion complete!" in caplog.text
