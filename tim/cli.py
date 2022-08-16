import logging
import pprint
from datetime import timedelta
from time import perf_counter
from typing import Optional

import click

from tim.config import configure_logger, configure_sentry
from tim.opensearch import configure_opensearch_client

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "-u",
    "--url",
    envvar="OPENSEARCH_ENDPOINT",
    default="localhost",
    help="The OpenSearch instance endpoint minus the http scheme, e.g. "
    "'search-timdex-env-1234567890.us-east-1.es.amazonaws.com'. If not provided, will "
    "attempt to get from the OPENSEARCH_ENDPOINT environment variable. Defaults to "
    "'localhost'.",
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Pass to log at debug level instead of info"
)
@click.pass_context
def main(ctx: click.Context, url: str, verbose: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["START_TIME"] = perf_counter()
    root_logger = logging.getLogger()
    logger.info(configure_logger(root_logger, verbose))
    logger.info(configure_sentry())
    ctx.obj["CLIENT"] = configure_opensearch_client(url)
    logger.info("OpenSearch client configured for endpoint '%s'", url)


@main.result_callback()
@click.pass_context
def log_process_time(
    ctx: click.Context, result: Optional[object], **kwargs: dict  # noqa
) -> None:
    elapsed_time = perf_counter() - ctx.obj["START_TIME"]
    logger.info(
        "Total time to complete process: %s", str(timedelta(seconds=elapsed_time))
    )


# OpenSearch instance commands


@main.command()
def aliases() -> None:
    """List OpenSearch aliases and their associated indexes.

    Find all aliases in the OpenSearch instance. For each alias, list the names of all
    indexes associated with that alias in alphabetical order.
    """
    logger.info("'aliases' command not yet implemented")


@main.command()
def indexes() -> None:
    """
    List all OpenSearch indexes.

    Find all indexes in the OpenSearch cluster. List the indexes in alphabetical order
    by name. For each index, display: index name, number of documents, health, status,
    UUID, size.
    """
    logger.info("'indexes' command not yet implemented")


@main.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Ping OpenSearch and display information about the cluster."""
    client = ctx.obj["CLIENT"]
    output = pprint.pformat(client.info(), indent=2)
    logger.info(output)


# Index commands


@main.command()
@click.option(
    "-s",
    "--source",
    required=True,
    help="Short name for source of records, e.g. 'dspace'. Will be used to identify or "
    "create index according to the naming convention 'source-timestamp",
)
@click.option(
    "-c",
    "--consumer",
    type=click.Choice(["os", "json", "title", "silent"]),
    default="os",
    show_default=True,
    help="Consumer to use. Non-default optioins can be useful for development and "
    "troubleshooting.",
)
@click.option(
    "--new",
    is_flag=True,
    help="Create a new index instead of ingesting into the current production index "
    "for the source",
)
@click.option(
    "--auto",
    is_flag=True,
    help="Automatically promote index to the production alias on ingest copmletion. "
    "Will demote the existing production index for the source if there is one.",
)
@click.argument("filepath", type=click.Path())
def ingest(
    source: str, consumer: str, new: bool, auto: bool, filepath: str  # noqa
) -> None:
    """
    Bulk ingest records into an index.

    By default, ingests into the current production index for the provided source."

    FILEPATH: path to ingest file, use format "s3://bucketname/objectname" for s3.
    """
    logger.info("'ingest' command not yet implemented")


@main.command()
@click.option(
    "-i", "--index", required=True, help="Name of the OpenSearch index to promote."
)
def promote(index: str) -> None:  # noqa
    """
    Promote an index to the production alias.

    Demotes the existing production index for the provided source if there is one.
    """
    logger.info("'promote' command not yet implemented")


@main.command()
@click.option(
    "-i",
    "--index",
    required=True,
    help="Name of the OpenSearch index to copy.",
)
@click.option(
    "-d",
    "--destination",
    required=True,
    help="Name of the destination index.",
)
def reindex(index: str, destination: str) -> None:  # noqa
    """
    Reindex one index to another index.

    Copy one index to another. The doc source must be present in the original index.
    """
    logger.info("'reindex' command not yet implemented")


@main.command()
@click.option(
    "-i",
    "--index",
    required=True,
    help="Name of the OpenSearch index to delete.",
)
def delete(index: str) -> None:  # noqa
    """Delete an index."""
    logger.info("'delete' command not yet implemented")
