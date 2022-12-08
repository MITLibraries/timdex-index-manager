import json
import logging
import os

import sentry_sdk

OPENSEARCH_BULK_CONFIG_DEFAULTS = {
    "OPENSEARCH_BULK_MAX_CHUNK_BYTES": 100 * 1024 * 1024,
    "OPENSEARCH_BULK_MAX_RETRIES": 8,
    "OPENSEARCH_REQUEST_TIMEOUT": 120,
}
PRIMARY_ALIAS = "all-current"
VALID_BULK_OPERATIONS = ["create", "delete", "index", "update"]
VALID_SOURCES = ["alma", "aspace", "dspace", "jpal", "whoas", "zenodo"]


def configure_index_settings() -> tuple:
    with open("config/opensearch_mappings.json", "r", encoding="utf-8") as file:
        all_settings = json.load(file)
        return all_settings["mappings"], all_settings["settings"]


def configure_logger(logger: logging.Logger, verbose: bool) -> str:
    if verbose:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s.%(funcName)s() line %(lineno)d: "
            "%(message)s"
        )
        logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(
            format="%(asctime)s %(levelname)s %(name)s.%(funcName)s(): %(message)s"
        )
        logger.setLevel(logging.INFO)
    for handler in logging.root.handlers:
        handler.addFilter(logging.Filter("tim"))
    return (
        f"Logger '{logger.name}' configured with level="
        f"{logging.getLevelName(logger.getEffectiveLevel())}"
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
