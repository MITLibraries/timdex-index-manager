import functools
import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Generator, Iterator
from datetime import UTC, datetime

import click
from opensearchpy.exceptions import TransportError

from tim.config import VALID_BULK_OPERATIONS, VALID_SOURCES
from tim.errors import SingleOperationError

logger = logging.getLogger(__name__)
TRANSPORT_ERROR_507 = 507


def retry(
    delay: float = 5,
    max_attempts: int = 8,
) -> Callable:
    """Retry the decorated function until success or max attempts reached.

    Args:
        delay: Time to wait, in seconds, between retry attempts. This value is
        multiplied by the attempt number, resulting in a progressive backoff.
        max_attempts: Number of allowed retries.
    """

    def retry_decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Callable:  # type: ignore[no-untyped-def] # noqa: ANN002, ANN003
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                logger.info(f"Calling {func.__name__}, attempt {attempt}")

                try:
                    return func(*args, **kwargs)
                except Exception as exception:
                    if (
                        isinstance(exception, TransportError)
                        and exception.status_code == TRANSPORT_ERROR_507
                    ):
                        logger.warning(
                            f"{func.__name__} raised retryable exception, attempt {attempt}: "  # noqa: E501
                            f"{exception}"
                        )
                    else:
                        logger.exception(
                            f"{func.__name__} raised unexpected exception, attempt {attempt}"  # noqa: E501
                        )
                        raise SingleOperationError from exception

                logger.debug(f"Sleeping {delay} seconds before retrying {func.__name__}")
                time.sleep(delay * attempt)

            raise TimeoutError(f"Timed out after {attempt} attempts")

        return wrapper

    return retry_decorator


def confirm_action(input_prompt: str) -> bool:
    """Get user confirmation via the provided input prompt."""
    check = input(f"{input_prompt} [y/n]: ")
    if check.lower() == "y":
        return True
    if check.lower() == "n":
        return False
    click.echo(f"Invalid input: '{check}', must be one of 'y' or 'n'.")
    return confirm_action(input_prompt)


def format_embeddings(embeddings: Iterator[dict]) -> Iterator[dict]:
    """Format embeddings for bulk update command.

    This method yields a dict that maps the embedding to the
    corresponding field in OpenSearch, using the 'embedding_strategy'
    to form the field name and assigning 'embedding_object' as the value.
    """
    for embedding in embeddings:
        yield {
            "timdex_record_id": embedding["timdex_record_id"],
            f"embedding_{embedding['embedding_strategy']}": json.loads(
                embedding["embedding_object"]
            ),
        }


def format_fulltexts(fulltexts: Iterator[dict]) -> Iterator[dict]:
    """Format fulltexts for bulk update command."""
    for fulltext in fulltexts:
        yield {
            "timdex_record_id": fulltext["timdex_record_id"],
            "fulltext": fulltext["fulltext"].decode(),
        }


def generate_index_name(source: str) -> str:
    """Generate a new index name from a source short name.

    Implements our local business logic for naming indexes, using the convention
    'source-YYYY-MM-DDthh-mm-ss' where the datetime is the datetime this operation is
    run.
    """
    return f"{source}-{datetime.now(tz=UTC).strftime('%Y-%m-%dt%H-%M-%S')}"


def generate_bulk_actions(
    index: str, records: Iterator[dict], action: str, cache: defaultdict | None = None
) -> Generator[dict]:
    """Iterate through records, create and yield an OpenSearch bulk action for each.

    The provided action must be one of the four OpenSearch bulk operation types.
    Each record must contain the "timdex_record_id" field.
    """
    if action not in VALID_BULK_OPERATIONS:
        message = (
            f"Invalid action parameter, must be one of {VALID_BULK_OPERATIONS}. Action "
            f"passed was '{action}'"
        )
        raise ValueError(message)
    for record in records:
        doc = {
            "_op_type": action,
            "_index": index,
            "_id": record["timdex_record_id"],
        }

        match action:
            case "update":
                doc["doc"] = record
            case _ if action != "delete":
                doc["_source"] = record

        if cache is not None:
            cache[record["timdex_record_id"]].append(doc)

        yield doc


def get_source_from_index(index_name: str) -> str:
    return index_name.split("-", maxsplit=1)[0]


def pop_cache_entry(cache: defaultdict, record_id: str) -> None:
    """Remove the oldest action for a record from the cache."""
    actions_deque = cache.get(record_id)
    if actions_deque:
        actions_deque.popleft()
        if not actions_deque:
            del cache[record_id]


def validate_index_name(
    ctx: click.Context,  # noqa: ARG001
    parameter_name: str,  # noqa: ARG001
    value: str,
) -> str:
    """Click callback to validate a provided index name against our business rules."""
    if value is None:
        return value
    try:
        source_end = value.index("-")
        date_start = source_end + 1
    except ValueError as error:
        message = (
            "Index name must be in the format <source>-<timestamp>, e.g. "
            "'aspace-2022-01-01t12:34:56'."
        )
        raise click.BadParameter(message) from error
    if value[:source_end] not in VALID_SOURCES:
        message = (
            "Source in index name must be a valid configured source, one of: "
            f"{VALID_SOURCES}"
        )
        raise click.BadParameter(message)
    try:
        datetime.strptime(value[date_start:], "%Y-%m-%dt%H-%M-%S").astimezone()
    except ValueError as error:
        message = (
            "Date in index name must be in the format 'YYYY-MM-DDthh-mm-ss', e.g. "
            "'aspace_2022-01-01t12:34:56'."
        )
        raise click.BadParameter(message) from error
    return value
