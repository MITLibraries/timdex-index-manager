from collections.abc import Generator, Iterator
from datetime import UTC, datetime

import click

from tim import opensearch as tim_os
from tim.config import VALID_BULK_OPERATIONS, VALID_SOURCES


def confirm_action(input_prompt: str) -> bool:
    """Get user confirmation via the provided input prompt."""
    check = input(f"{input_prompt} [y/n]: ")
    if check.lower() == "y":
        return True
    if check.lower() == "n":
        return False
    click.echo(f"Invalid input: '{check}', must be one of 'y' or 'n'.")
    return confirm_action(input_prompt)


def generate_index_name(source: str) -> str:
    """Generate a new index name from a source short name.

    Implements our local business logic for naming indexes, using the convention
    'source-YYYY-MM-DDthh-mm-ss' where the datetime is the datetime this operation is
    run.
    """
    return f"{source}-{datetime.now(tz=UTC).strftime('%Y-%m-%dt%H-%M-%S')}"


def generate_bulk_actions(
    index: str,
    records: Iterator[dict],
    action: str,
) -> Generator[dict, None, None]:
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

        yield doc


def get_source_from_index(index_name: str) -> str:
    return index_name.split("-")[0]


def validate_bulk_cli_options(
    index: str | None, source: str, client: tim_os.OpenSearch
) -> str:
    options = [index, source]
    if all(options):
        message = "Only one of --index and --source options is allowed, not both."
        raise click.UsageError(message)
    if not any(options):
        message = "Must provide either an existing index name or a valid source."
        raise click.UsageError(message)
    if index and not client.indices.exists(index):
        message = f"Index '{index}' does not exist in the cluster."
        raise click.BadParameter(message)
    if source:
        index = tim_os.get_primary_index_for_source(client, source)
    if not index:
        message = (
            "No index name was passed and there is no primary-aliased index for "
            f"source '{source}'."
        )
        raise click.BadParameter(message)
    return index


def validate_index_name(
    ctx: click.Context, parameter_name: str, value: str  # noqa: ARG001
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
