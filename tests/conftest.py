import pytest
import vcr
from click.testing import CliRunner

import tim.opensearch as tim_os

EXIT_CODES = {
    "success": 0,
    "error": 1,
    "invalid_command": 2,
}
my_vcr = vcr.VCR(
    cassette_library_dir="tests/fixtures/cassettes",
    filter_headers=["authorization"],
)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test")
    monkeypatch.setenv("TIMDEX_OPENSEARCH_ENDPOINT", "localhost")


@pytest.fixture
def test_opensearch_client():
    return tim_os.configure_opensearch_client("localhost")


@pytest.fixture
def runner():
    return CliRunner()
