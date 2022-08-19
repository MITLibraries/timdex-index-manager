import os

import pytest
from click.testing import CliRunner

from tim.opensearch import configure_opensearch_client


@pytest.fixture(autouse=True)
def test_env():
    os.environ = {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_SESSION_TOKEN": "test",
        "OPENSEARCH_ENDPOINT": "localhost",
        "SENTRY_DSN": None,
        "WORKSPACE": "test",
    }
    yield


@pytest.fixture()
def test_opensearch_client():
    return configure_opensearch_client("localhost")


@pytest.fixture()
def runner():
    return CliRunner()
