from datetime import datetime
from typing import Generator, Iterator, Optional

import click
import ijson
import smart_open

from tim import opensearch as tim_os
from tim.config import VALID_BULK_OPERATIONS, VALID_SOURCES


def confirm_action(index: str, input_prompt: str) -> bool:
    """Get user confirmation via the provided input prompt."""
    check = input(f"{input_prompt} [y/n]: ")
    if check.lower() == "y":
        return True
    if check.lower() == "n":
        return False
    print(f"Invalid input: '{check}', must be one of 'y' or 'n'.")
    return confirm_action(index, input_prompt)


def generate_index_name(source: str) -> str:
    """Generate a new index name from a source short name.

    Implements our local business logic for naming indexes, using the convention
    'source-YYYY-MM-DDthh-mm-ss' where the datetime is the datetime this operation is
    run.
    """
    return f"{source}-{datetime.now().strftime('%Y-%m-%dt%H-%M-%S')}"


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
        raise ValueError(
            f"Invalid action parameter, must be one of {VALID_BULK_OPERATIONS}. Action "
            f"passed was '{action}'"
        )
    for record in records:
        doc = {
            "_op_type": action,
            "_index": index,
            "_id": record["timdex_record_id"],
        }
        if action != "delete":
            doc["_source"] = record
        yield doc


def get_source_from_index(index_name: str) -> str:
    return index_name.split("-")[0]


def parse_records(filepath: str) -> Generator[dict, None, None]:
    """Open an input JSON file, iterate through it and yield one record at a time.

    This function expects that the input file contains an array of objects
    representing individual records in our standard TIMDEX record JSON format.
    """
    with smart_open.open(filepath, "rb") as json_input:
        for item in ijson.items(json_input, "item"):
            yield item


def parse_deleted_records(filepath: str) -> Generator[dict, None, None]:
    """Open an input file, iterate through it and yield one deleted record at a time.

    This function expects that the input file contains a list of TIMDEX record IDs, one
    per line in the file.
    """
    with smart_open.open(filepath, "r") as file_input:
        for item in file_input.readlines():
            yield {"timdex_record_id": item.rstrip()}


def validate_bulk_cli_options(
    index: Optional[str], source: Optional[str], client: tim_os.OpenSearch
) -> str:
    options = [index, source]
    if all(options):
        raise click.UsageError(
            "Only one of --index and --source options is allowed, not both."
        )
    if not any(options):
        raise click.UsageError(
            "Must provide either an existing index name or a valid source."
        )
    if index and not client.indices.exists(index):
        raise click.BadParameter(f"Index '{index}' does not exist in the cluster.")
    if source:
        index = tim_os.get_primary_index_for_source(client, source)
    if not index:
        raise click.BadParameter(
            "No index name was passed and there is no primary-aliased index for "
            f"source '{source}'."
        )
    return index


def validate_index_name(
    ctx: click.Context, parameter_name: str, value: Optional[str]  # noqa
) -> Optional[str]:
    """Click callback to validate a provided index name against our business rules."""
    if value is None:
        return value
    try:
        source_end = value.index("-")
        date_start = source_end + 1
    except ValueError as error:
        raise click.BadParameter(
            "Index name must be in the format <source>-<timestamp>, e.g. "
            "'aspace-2022-01-01t12:34:56'."
        ) from error
    if value[:source_end] not in VALID_SOURCES:
        raise click.BadParameter(
            "Source in index name must be a valid configured source, one of: "
            f"{VALID_SOURCES}"
        )
    try:
        datetime.strptime(value[date_start:], "%Y-%m-%dt%H-%M-%S")
    except ValueError as error:
        raise click.BadParameter(
            "Date in index name must be in the format 'YYYY-MM-DDthh-mm-ss', e.g. "
            "'aspace_2022-01-01t12:34:56'."
        ) from error
    return value
