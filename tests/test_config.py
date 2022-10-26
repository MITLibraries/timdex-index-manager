import logging

from tim.config import (
    configure_index_settings,
    configure_logger,
    configure_sentry,
    opensearch_request_timeout,
)


def test_configure_index_settings():
    mappings, settings = configure_index_settings()
    assert "timdex_record_id" in mappings["properties"]
    assert "analysis" in settings


def test_configure_logger_not_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=False)
    assert logger.getEffectiveLevel() == 20
    assert result == "Logger 'tests.test_config' configured with level=INFO"


def test_configure_logger_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=True)
    assert logger.getEffectiveLevel() == 10
    assert result == "Logger 'tests.test_config' configured with level=DEBUG"


def test_configure_sentry_no_env_variable(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    result = configure_sentry()
    assert result == "No Sentry DSN found, exceptions will not be sent to Sentry"


def test_configure_sentry_env_variable_is_none(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    result = configure_sentry()
    assert result == "No Sentry DSN found, exceptions will not be sent to Sentry"


def test_configure_sentry_env_variable_is_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://1234567890@00000.ingest.sentry.io/123456")
    result = configure_sentry()
    assert result == "Sentry DSN found, exceptions will be sent to Sentry with env=test"


def test_opensearch_request_timeout_default(monkeypatch):
    monkeypatch.delenv("OPENSEARCH_REQUEST_TIMEOUT", raising=False)
    assert opensearch_request_timeout() == 120


def test_opensearch_request_timeout_from_env(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_REQUEST_TIMEOUT", "5")
    assert opensearch_request_timeout() == 5
