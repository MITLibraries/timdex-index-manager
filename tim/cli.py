import logging
import sys
from datetime import timedelta
from time import perf_counter
from typing import Optional

import click

from tim import helpers
from tim import opensearch as tim_os
from tim.config import configure_logger, configure_sentry

logger = logging.getLogger(__name__)


# Main command group


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
    ctx.obj["CLIENT"] = tim_os.configure_opensearch_client(url)
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


# Cluster commands


@main.command()
@click.pass_context
def aliases(ctx: click.Context) -> None:
    """List OpenSearch aliases and their associated indexes.

    Find all aliases in the OpenSearch instance. For each alias, list the names of all
    indexes associated with that alias in alphabetical order.
    """
    click.echo(tim_os.get_formatted_aliases(ctx.obj["CLIENT"]))


@main.command()
@click.pass_context
def indexes(ctx: click.Context) -> None:
    """
    Display summary information about all indexes in the cluster.

    Prints all indexes in the cluster in alphabetical order by name. For each index,
    displays information including its status, health, number of documents, primary
    store size, total store size, and UUID.
    """
    click.echo(tim_os.get_formatted_indexes(ctx.obj["CLIENT"]))


@main.command()
@click.pass_context
def ping(ctx: click.Context) -> None:
    """Ping OpenSearch and display information about the cluster."""
    click.echo(tim_os.get_formatted_info(ctx.obj["CLIENT"]))


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
    "--new",
    is_flag=True,
    help="Create a new index instead of ingesting into the current production index "
    "for the source",
)
@click.option(
    "--auto",
    is_flag=True,
    help="Automatically promote index on ingest completion. Will promote the index to "
    "the primary alias (always), any existing indexes for the source (if any), and any "
    "additional aliases passed via the --aliases option. Demotes existing index(es) "
    "for the source in all aliases, if there are any.",
)
@click.option(
    "-a",
    "--aliases",
    "extra_aliases",
    multiple=True,
    help="Additional aliases to promote the index to besisdes the primary alias. This "
    "is only useful if the '--auto' flag is also passed. Note: the primary alias is "
    "always assigned when an index is promoted and does not need to be passed "
    "explicitly.",
)
@click.argument("filepath", type=click.Path())
@click.pass_context
def ingest(  # pylint: disable=too-many-arguments
    ctx: click.Context,
    source: str,
    new: bool,
    auto: bool,
    extra_aliases: Optional[list[str]],
    filepath: str,
) -> None:
    """
    Bulk ingest records into an index.

    By default, ingests into the current primary-aliased index for the provided source,
    or creates a new one if there is no primary index for the source.

    FILEPATH: path to ingest file, use format "s3://bucketname/objectname" for s3.
    """
    logger.info(
        "Running ingest command with options: source=%s, new=%s, auto=%s, "
        "extra_aliases=%s, filepath=%s",
        source,
        new,
        auto,
        extra_aliases,
        filepath,
    )
    client = ctx.obj["CLIENT"]
    record_iterator = helpers.parse_records(filepath)
    index = tim_os.get_or_create_index_from_source(client, source, new)
    logger.info(
        "Ingesting records into %s index '%s'", "new" if new else "existing", index
    )
    results = tim_os.bulk_index(client, index, record_iterator)
    logger.info(
        "Ingest complete!\n   Errors: %d%s"
        "\n  Created: %d\n  Updated: %d\n    Total: %d",
        results["errors"],
        " (see logs for details)" if results["errors"] else "",
        results["created"],
        results["updated"],
        results["total"],
    )
    if auto is True:
        logger.info("'auto' flag was passed, automatic promotion is happening.")
        ctx.invoke(promote, index=index, alias=extra_aliases)


@main.command()
@click.option(
    "-i", "--index", required=True, help="Name of the OpenSearch index to promote."
)
@click.option(
    "-a",
    "--alias",
    multiple=True,
    help="Alias to promote the index to in addition to the primary alias. May "
    "be repeated to promote the index to multiple aliases at once.",
)
@click.pass_context
def promote(ctx: click.Context, index: str, alias: Optional[list[str]]) -> None:
    """
    Promote an index to the primary alias and add it to any additional provided aliases.

    This command promotes an index to the primary alias, any alias that already has an
    index for the same source, and any additional alias(es) passed to the command. If
    there is already an index for the source in any alias it is promoted to, the
    existing index will be demoted.

    This action is atomic.
    """
    client = ctx.obj["CLIENT"]
    tim_os.promote_index(client, index, extra_aliases=alias)
    logger.info(
        "Index promoted. Current aliases for index '%s': %s",
        index,
        tim_os.get_index_aliases(client, index),
    )
    click.echo("Current state of all aliases:")
    ctx.invoke(aliases)


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
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Pass to disable user confirmation prompt.",
)
@click.pass_context
def delete(ctx: click.Context, index: str, force: bool) -> None:
    """Delete an index.

    Will prompt for confirmation before index deletion unless the --force option is
    passed (not recommended when using on production OpenSearch instances).
    """
    client = ctx.obj["CLIENT"]
    if force or helpers.confirm_action(
        index, f"Are you sure you want to delete index '{index}'?"
    ):
        tim_os.delete_index(client, index)
        click.echo(f"\nIndex '{index}' deleted.\n")
        click.echo("Current state of all indexes:")
        ctx.invoke(indexes)
    else:
        click.echo("\nOk, index will not be deleted.\n")
        sys.exit()
