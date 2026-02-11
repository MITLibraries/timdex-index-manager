import logging

from tim.config import (
    OPENSEARCH_BULK_CONFIG_DEFAULTS,
    configure_index_settings,
    configure_logger,
    configure_opensearch_bulk_settings,
    configure_sentry,
)


def test_configure_index_settings():
    mappings, settings = configure_index_settings()
    assert "timdex_record_id" in mappings["properties"]
    assert "analysis" in settings


def test_configure_logger_not_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=False)

    assert logger.getEffectiveLevel() == logging.INFO
    assert result == "Logger 'tests.test_config' configured with level=INFO"


def test_configure_logger_verbose():
    logger = logging.getLogger(__name__)
    result = configure_logger(logger, verbose=True)
    assert logger.getEffectiveLevel() == logging.DEBUG
    assert result == "Logger 'tests.test_config' configured with level=DEBUG"


def test_configure_opensearch_bulk_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_BULK_MAX_CHUNK_BYTES", "10")
    monkeypatch.setenv("OPENSEARCH_BULK_MAX_RETRIES", "2")
    monkeypatch.setenv("OPENSEARCH_REQUEST_TIMEOUT", "20")
    assert configure_opensearch_bulk_settings() == {
        "OPENSEARCH_BULK_MAX_CHUNK_BYTES": 10,
        "OPENSEARCH_BULK_MAX_RETRIES": 2,
        "OPENSEARCH_REQUEST_TIMEOUT": 20,
    }


def test_configure_opensearch_bulk_settings_uses_defaults(monkeypatch):
    monkeypatch.delenv("OPENSEARCH_BULK_MAX_CHUNK_BYTES", raising=False)
    monkeypatch.delenv("OPENSEARCH_BULK_MAX_RETRIES", raising=False)
    monkeypatch.delenv("OPENSEARCH_REQUEST_TIMEOUT", raising=False)
    assert configure_opensearch_bulk_settings() == OPENSEARCH_BULK_CONFIG_DEFAULTS


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
