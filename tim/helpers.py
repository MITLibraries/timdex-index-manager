from datetime import datetime
from typing import Generator, Iterator

import ijson
import smart_open

VALID_BULK_OPERATIONS = ["create", "delete", "index", "update"]


def generate_index_name(source: str) -> str:
    """Generate a new index name from a source short name.

    Implements our local business logic for naming indexes, using the convention
    'source-YYYY-MM-DDthh-mm-ss' where the datetime is the datetime this operation is
    run.
    """
    return f"{source}-{datetime.today().strftime('%Y-%m-%dt%H-%M-%S')}"


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
            "_source": record,
        }
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
