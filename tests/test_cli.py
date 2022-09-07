from freezegun import freeze_time

from tim.cli import main

from .conftest import my_vcr


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_no_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@my_vcr.use_cassette("ping_localhost.yaml")
def test_main_group_all_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("OPENSEARCH_ENDPOINT", raising=False)
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


@freeze_time("2022-09-01")
@my_vcr.use_cassette("ingest_no_options.yaml")
def test_ingest_no_options(caplog, runner):
    result = runner.invoke(
        main,
        ["ingest", "-s", "test", "tests/fixtures/sample_records.json"],
    )
    assert result.exit_code == 0
    assert (
        "Running ingest command with options: source=test, new=False, auto=False, "
        "extra_aliases=(), filepath=tests/fixtures/sample_records.json" in caplog.text
    )
    assert "Ingesting records into existing index" in caplog.text
    assert "Ingest complete!" in caplog.text


@freeze_time("2022-09-01")
@my_vcr.use_cassette("ingest_all_options.yaml")
def test_ingest_all_options(caplog, runner):
    result = runner.invoke(
        main,
        [
            "ingest",
            "-s",
            "test",
            "--new",
            "--auto",
            "-a",
            "test-alias",
            "tests/fixtures/sample_records.json",
        ],
    )
    assert result.exit_code == 0
    assert (
        "Running ingest command with options: source=test, new=True, auto=True, "
        "extra_aliases=('test-alias',), filepath=tests/fixtures/sample_records.json"
        in caplog.text
    )
    assert "Ingesting records into new index" in caplog.text
    assert "Ingest complete!" in caplog.text
    assert "'auto' flag was passed, automatic promotion is happening." in caplog.text
    assert "Index promoted." in caplog.text


@my_vcr.use_cassette("promote_index.yaml")
def test_promote(caplog, runner):
    result = runner.invoke(main, ["promote", "-i", "testsource-index"])
    assert result.exit_code == 0
    assert "Index promoted" in caplog.text


def test_reindex(caplog, runner):
    result = runner.invoke(
        main, ["reindex", "-i", "test-index", "-d", "destination-index"]
    )
    assert result.exit_code == 0
    assert "'reindex' command not yet implemented" in caplog.text


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_with_force(runner):
    result = runner.invoke(main, ["delete", "-i", "test-index", "-f"])
    assert result.exit_code == 0
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_success.yaml")
def test_delete_with_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == 0
    assert "Index 'test-index' deleted." in result.stdout


@my_vcr.use_cassette("delete_without_confirmation.yaml")
def test_delete_without_confirmation(monkeypatch, runner):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == 0
    assert "Ok, index will not be deleted." in result.stdout
