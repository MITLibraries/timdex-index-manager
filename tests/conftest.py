import os

import pytest
from click.testing import CliRunner


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
def runner():
    return CliRunner()
