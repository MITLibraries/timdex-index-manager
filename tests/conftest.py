import pytest
import vcr
from click.testing import CliRunner

from tim.opensearch import configure_opensearch_client

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
    return configure_opensearch_client("localhost")


@pytest.fixture
def runner():
    return CliRunner()
