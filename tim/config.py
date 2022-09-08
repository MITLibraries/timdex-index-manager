import json
import logging
import os

import sentry_sdk

PRIMARY_ALIAS = "all-current"


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


def configure_sentry() -> str:
    env = os.getenv("WORKSPACE")
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn and sentry_dsn.lower() != "none":
        sentry_sdk.init(sentry_dsn, environment=env)
        return f"Sentry DSN found, exceptions will be sent to Sentry with env={env}"
    return "No Sentry DSN found, exceptions will not be sent to Sentry"


def opensearch_request_timeout() -> int:
    return int(os.getenv("OPENSEARCH_REQUEST_TIMEOUT", "30"))
