import logging
from datetime import timedelta
from time import perf_counter
from typing import Optional

import rich_click as click

from tim import errors, helpers
from tim import opensearch as tim_os
from tim.config import PRIMARY_ALIAS, VALID_SOURCES, configure_logger, configure_sentry

logger = logging.getLogger(__name__)

click.rich_click.COMMAND_GROUPS = {
    "tim": [
        {
            "name": "Get cluster-level information",
            "commands": ["ping", "indexes", "aliases"],
        },
        {
            "name": "Index management commands",
            "commands": ["create", "delete", "promote", "demote"],
        },
        {
            "name": "Bulk record processing commands",
            "commands": ["bulk-index"],
        },
    ]
}


# Main command group


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
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
    """
    TIM provides commands for interacting with OpenSearch indexes.

    For more details on a specific command, run tim COMMAND -h.
    """
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
    "-i",
    "--index",
    callback=helpers.validate_index_name,
    help="Optional name to use for new index, must use the convention "
    "'source-YYYY-MM-DDthh-mm-ss'.",
)
@click.option(
    "-s",
    "--source",
    type=click.Choice(VALID_SOURCES),
    help="Optional source to use for the new index name, must be a valid source from "
    "the configured sources list.",
)
@click.pass_context
def create(ctx: click.Context, index: Optional[str], source: Optional[str]) -> None:
    """
    Create a new index in the cluster.

    Must provide either the index name or source option. If source is provided, will
    create an index named according to our convention with the source and a generated
    timestemp.

    Raises an error if an index with the provided index name already exists, or if the
    provided index name does not match the specified naming convention.
    """
    options = [index, source]
    if all(options):
        raise click.UsageError(
            "Only one of --index and --source options is allowed, not both."
        )
    if not any(options):
        raise click.UsageError(
            "Must provide either a name or source for the new index."
        )
    if source:
        index = helpers.generate_index_name(source)
    try:
        new_index = tim_os.create_index(ctx.obj["CLIENT"], str(index))
    except errors.IndexExistsError as error:
        logger.error(error)
        raise click.Abort()
    logger.info("Index '%s' created.", new_index)
    ctx.invoke(indexes)


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
        click.echo(f"Index '{index}' deleted.")
        ctx.invoke(indexes)
    else:
        click.echo("Ok, index will not be deleted.")
        raise click.Abort()


@main.command()
@click.option(
    "-i",
    "--index",
    required=True,
    help="Name of the OpenSearch index to demote.",
)
@click.pass_context
def demote(ctx: click.Context, index: str) -> None:
    """Demote an index from all its associated aliases.

    Will prompt for confirmation before index demotion if the index is associated with
    the primary alias, as it's very rare that we would want to demote an index from the
    primary alias without simultaneously promoting a different index for the source.
    """
    client = ctx.obj["CLIENT"]
    index_aliases = tim_os.get_index_aliases(client, index) or []
    if not index_aliases:
        click.echo(
            f"Index '{index}' has no aliases, please check aliases and try again."
        )
        raise click.Abort()
    if PRIMARY_ALIAS in index_aliases:
        if not helpers.confirm_action(
            index,
            f"Are you sure you want to demote index '{index}' from the primary alias "
            "without promoting another index for the source?",
        ):
            click.echo("Ok, index will not be demoted.")
            raise click.Abort()
    for alias in index_aliases:
        tim_os.remove_alias(client, index, alias)
    click.echo(f"Index '{index}' demoted from aliases: {index_aliases}")
    ctx.invoke(aliases)


@main.command()
@click.option(
    "-i",
    "--index",
    required=True,
    help="Name of the OpenSearch index to promote.",
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
    ctx.invoke(aliases)


# Bulk record processing commands


@main.command()
@click.option("-i", "--index", help="Name of the index to bulk index records into.")
@click.option(
    "-s",
    "--source",
    type=click.Choice(VALID_SOURCES),
    help="Source whose primary-aliased index to bulk index records into.",
)
@click.argument("filepath", type=click.Path())
@click.pass_context
def bulk_index(
    ctx: click.Context, index: Optional[str], source: Optional[str], filepath: str
) -> None:
    """
    Bulk index records into an index.

    Must provide either the name of an existing index in the cluster or a valid source.
    If source is provided, will index records into the primary-aliased index for the
    source.

    Logs an error and aborts if the provided index doesn't exist in the cluster.

    FILEPATH: path to transformed records file, use format "s3://bucketname/objectname"
    for s3.
    """
    options = [index, source]
    if all(options):
        raise click.UsageError(
            "Only one of --index and --source options is allowed, not both."
        )
    if not any(options):
        raise click.UsageError(
            "Must provide either an existing index name or a valid source."
        )
    client = ctx.obj["CLIENT"]
    if index and not client.indices.exists(index):
        raise click.BadParameter(f"Index '{index}' does not exist in the cluster.")
    if source:
        index = tim_os.get_primary_index_for_source(client, source)
    if not index:
        raise click.BadParameter(
            "No index name was passed and there is no primary-aliased index for "
            f"source '{source}'."
        )

    logger.info("Bulk indexing records from file '%s' into index '%s'", filepath, index)
    record_iterator = helpers.parse_records(filepath)
    results = tim_os.bulk_index(client, index, record_iterator)
    logger.info(
        "Bulk indexing complete!\n   Errors: %d%s"
        "\n  Created: %d\n  Updated: %d\n  --------\n    Total: %d",
        results["errors"],
        " (see logs for details)" if results["errors"] else "",
        results["created"],
        results["updated"],
        results["total"],
    )
