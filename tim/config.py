import json
import logging
import os

import sentry_sdk

OPENSEARCH_BULK_CONFIG_DEFAULTS = {
    "OPENSEARCH_BULK_MAX_CHUNK_BYTES": 100 * 1024 * 1024,
    "OPENSEARCH_BULK_MAX_RETRIES": 50,
    "OPENSEARCH_REQUEST_TIMEOUT": 120,
}
PRIMARY_ALIAS = "all-current"
VALID_BULK_OPERATIONS = ["create", "delete", "index", "update"]
VALID_SOURCES = [
    "alma",
    "aspace",
    "dspace",
    "gismit",
    "gisogm",
    "libguides",
    "jpal",
    "researchdatabases",
    "whoas",
    "zenodo",
]


def configure_index_settings() -> tuple:
    with open("config/opensearch_mappings.json", encoding="utf-8") as file:
        all_settings = json.load(file)
        return all_settings["mappings"], all_settings["settings"]


def configure_logger(
    root_logger: logging.Logger,
    *,
    verbose: bool = False,
    warning_only_loggers: str | None = None,
) -> str:
    """Configure application via passed application root logger.

    If verbose=True, 3rd party libraries can be quite chatty.  For convenience, they can
    be set to WARNING level by either passing a comma seperated list of logger names to
    'warning_only_loggers' or by setting the env var WARNING_ONLY_LOGGERS.
    """
    if verbose:
        root_logger.setLevel(logging.DEBUG)
        logging_format = (
            "%(asctime)s %(levelname)s %(name)s.%(funcName)s() "
            "line %(lineno)d: %(message)s"
        )
    else:
        root_logger.setLevel(logging.INFO)
        logging_format = "%(asctime)s %(levelname)s %(name)s.%(funcName)s(): %(message)s"

    warning_only_loggers = os.getenv("WARNING_ONLY_LOGGERS", warning_only_loggers)
    if warning_only_loggers:
        for name in warning_only_loggers.split(","):
            logging.getLogger(name).setLevel(logging.WARNING)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(logging_format))
    root_logger.addHandler(handler)

    return (
        f"Logger '{root_logger.name}' configured with level="
        f"{logging.getLevelName(root_logger.getEffectiveLevel())}"
    )


def configure_opensearch_bulk_settings() -> dict[str, int]:
    result = {}
    for key, value in OPENSEARCH_BULK_CONFIG_DEFAULTS.items():
        result[key] = int(os.getenv(key) or value)
    return result


def configure_sentry() -> str:
    env = os.getenv("WORKSPACE")
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn and sentry_dsn.lower() != "none":
        sentry_sdk.init(sentry_dsn, environment=env)
        return f"Sentry DSN found, exceptions will be sent to Sentry with env={env}"
    return "No Sentry DSN found, exceptions will not be sent to Sentry"
