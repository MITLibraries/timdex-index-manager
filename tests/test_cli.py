from tim.cli import main


def test_main_group_no_options_configures_correctly_and_invokes_result_callback(
    caplog, runner
):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=INFO" in caplog.text
    assert "Total time to complete process" in caplog.text


def test_main_group_all_options_configures_correctly_and_invokes_result_callback(
    caplog, runner
):
    result = runner.invoke(main, ["--verbose", "ping"])
    assert result.exit_code == 0
    assert "Logger 'root' configured with level=DEBUG" in caplog.text
    assert "Total time to complete process" in caplog.text


def test_aliases(caplog, runner):
    result = runner.invoke(main, ["aliases"])
    assert result.exit_code == 0
    assert "'aliases' command not yet implemented" in caplog.text


def test_indexes(caplog, runner):
    result = runner.invoke(main, ["indexes"])
    assert result.exit_code == 0
    assert "'indexes' command not yet implemented" in caplog.text


def test_ping(caplog, runner):
    result = runner.invoke(main, ["ping"])
    assert result.exit_code == 0
    assert "'ping' command not yet implemented" in caplog.text


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
