import vcr

from tim.cli import main


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_main_group_no_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_main_group_all_options_configures_correctly_and_invokes_result_callback(
    caplog, monkeypatch, runner
):
    monkeypatch.delenv("OPENSEARCH_ENDPOINT", raising=False)
    result = runner.invoke(main, ["--verbose", "--url", "localhost", "ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=DEBUG" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_main_group_options_from_env_configures_correctly_and_invokes_result_callback(
    caplog, runner
):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "OpenSearch client configured for endpoint 'localhost'" in caplog.text
    assert "Total time to complete process" in caplog.text


@vcr.use_cassette("tests/fixtures/cassettes/list_aliases.yaml")
def test_aliases(runner):
    result = runner.invoke(main, ["aliases"])
    assert result.exit_code == 0
    assert "Alias: alias-with-multiple-indexes" in result.stdout


@vcr.use_cassette("tests/fixtures/cassettes/list_indexes.yaml")
def test_indexes(runner):
    result = runner.invoke(main, ["indexes"])
    assert result.exit_code == 0
    assert "Name: index-with-multiple-aliases" in result.stdout


@vcr.use_cassette("tests/fixtures/cassettes/ping_localhost.yaml")
def test_ping(runner):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Name: docker-cluster" in result.stdout


def test_ingest_no_options(caplog, runner):
    result = runner.invoke(
        main,
        ["ingest", "-s", "aspace", "tests/fixtures/sample-records.json"],
    )
    assert result.exit_code == 0
    assert "'ingest' command not yet implemented" in caplog.text


def test_ingest_all_options(caplog, runner):
    result = runner.invoke(
        main,
        [
            "ingest",
            "-s",
            "dspace",
            "-c",
            "title",
            "--new",
            "--auto",
            "tests/fixtures/sample-records.json",
        ],
    )
    assert result.exit_code == 0
    assert "'ingest' command not yet implemented" in caplog.text


def test_promote(caplog, runner):
    result = runner.invoke(main, ["promote", "-i", "test-index"])
    assert result.exit_code == 0
    assert "'promote' command not yet implemented" in caplog.text


def test_reindex(caplog, runner):
    result = runner.invoke(
        main, ["reindex", "-i", "test-index", "-d", "destination-index"]
    )
    assert result.exit_code == 0
    assert "'reindex' command not yet implemented" in caplog.text


def test_delete(caplog, runner):
    result = runner.invoke(main, ["delete", "-i", "test-index"])
    assert result.exit_code == 0
    assert "'delete' command not yet implemented" in caplog.text
