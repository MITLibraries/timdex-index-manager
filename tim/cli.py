# ruff: noqa: TRY003, EM101
import json
import logging
from datetime import timedelta
from time import perf_counter

import rich_click as click
from timdex_dataset_api import TIMDEXDataset

from tim import errors, helpers
from tim import opensearch as tim_os
from tim.config import PRIMARY_ALIAS, VALID_SOURCES, configure_logger, configure_sentry
from tim.errors import BulkIndexingError

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
            "commands": ["bulk-update", "reindex-source"],
        },
    ]
}


# Main command group


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-u",
    "--url",
    envvar="TIMDEX_OPENSEARCH_ENDPOINT",
    default="localhost",
    help="The OpenSearch instance endpoint minus the http scheme, e.g. "
    "'search-timdex-env-1234567890.us-east-1.es.amazonaws.com'. If not provided, will "
    "attempt to get from the TIMDEX_OPENSEARCH_ENDPOINT environment variable. Defaults "
    "to 'localhost'.",
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Pass to log at debug level instead of info"
)
@click.pass_context
def main(ctx: click.Context, url: str, *, verbose: bool) -> None:
    """TIM provides commands for interacting with OpenSearch indexes.

    For more details on a specific command, run tim COMMAND -h.
    """
    ctx.ensure_object(dict)
    ctx.obj["START_TIME"] = perf_counter()
    root_logger = logging.getLogger()
    logger.info(configure_logger(root_logger, verbose=verbose))
    logger.info(configure_sentry())
    ctx.obj["CLIENT"] = tim_os.configure_opensearch_client(url)
    logger.info("OpenSearch client configured for endpoint '%s'", url)


@main.result_callback()
@click.pass_context
def log_process_time(ctx: click.Context, _result: object, **_kwargs: dict) -> None:
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
    """Display summary information about all indexes in the cluster.

    Prints all indexes in the cluster in alphabetical order by name. For each index,
    displays information including its status, health, number of documents, primary
    store size, total store size, UUID, primary shard count, and replica shard count.
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
    callback=helpers.validate_index_name,  # type: ignore[arg-type]
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
def create(ctx: click.Context, index: str, source: str) -> None:
    """Create a new index in the cluster.

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
        raise click.UsageError("Must provide either a name or source for the new index.")
    if source:
        index = helpers.generate_index_name(source)
    try:
        new_index = tim_os.create_index(ctx.obj["CLIENT"], str(index))
    except errors.IndexExistsError as error:
        logger.error(error)  # noqa: TRY400
        raise click.Abort from error
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
def delete(ctx: click.Context, index: str, *, force: bool) -> None:
    """Delete an index.

    Will prompt for confirmation before index deletion unless the --force option is
    passed (not recommended when using on production OpenSearch instances).
    """
    client = ctx.obj["CLIENT"]
    if force or helpers.confirm_action(
        f"Are you sure you want to delete index '{index}'?"
    ):
        tim_os.delete_index(client, index)
        click.echo(f"Index '{index}' deleted.")
        ctx.invoke(indexes)
    else:
        click.echo("Ok, index will not be deleted.")
        raise click.Abort


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
        click.echo(f"Index '{index}' has no aliases, please check aliases and try again.")
        raise click.Abort
    if PRIMARY_ALIAS in index_aliases and not helpers.confirm_action(
        f"Are you sure you want to demote index '{index}' from the primary alias "
        "without promoting another index for the source?",
    ):
        click.echo("Ok, index will not be demoted.")
        raise click.Abort
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
def promote(ctx: click.Context, index: str, alias: list[str]) -> None:
    """Promote index as the primary alias and add it to any additional provided aliases.

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
@click.option(
    "-i",
    "--index",
    help="Name of the index on which to perform bulk indexing and deletion.",
)
@click.option(
    "-s",
    "--source",
    type=click.Choice(VALID_SOURCES),
    help="Source whose primary-aliased index to bulk index records into.",
)
@click.option("-d", "--run-date", help="Run date, formatted as YYYY-MM-DD.")
@click.option("-rid", "--run-id", help="Run ID.")
@click.argument("dataset_path", type=click.Path())
@click.pass_context
def bulk_update(
    ctx: click.Context,
    index: str,
    source: str,
    run_date: str,
    run_id: str,
    dataset_path: str,
) -> None:
    """Bulk update records for an index.

    Must provide either the name of an existing index in the cluster or a valid source.
    If source is provided, it will perform indexing and/or deletion of records for
    the primary-aliased index for the source.

    The method will read transformed records from a TIMDEXDataset
    located at dataset_path using the 'timdex-dataset-api' library. The dataset
    is filtered by run date and run ID.

    Logs an error and aborts if the provided index doesn't exist in the cluster.
    """
    client = ctx.obj["CLIENT"]
    index = helpers.validate_bulk_cli_options(index, source, client)

    logger.info(f"Bulk updating records from dataset '{dataset_path}' into '{index}'")

    index_results = {"created": 0, "updated": 0, "errors": 0, "total": 0}
    delete_results = {"deleted": 0, "errors": 0, "total": 0}

    td = TIMDEXDataset(location=dataset_path)

    # bulk index records
    records_to_index = td.read_transformed_records_iter(
        run_date=run_date,
        run_id=run_id,
        action="index",
    )
    try:
        index_results.update(tim_os.bulk_index(client, index, records_to_index))
    except BulkIndexingError as exception:
        logger.info(f"Bulk indexing failed: {exception}")

    # bulk delete records
    records_to_delete = td.read_dicts_iter(
        columns=["timdex_record_id"],
        run_date=run_date,
        run_id=run_id,
        action="delete",
    )
    delete_results.update(tim_os.bulk_delete(client, index, records_to_delete))

    summary_results = {"index": index_results, "delete": delete_results}
    logger.info(f"Bulk update complete: {json.dumps(summary_results)}")


# Bulk update existing records with embeddings commands


@main.command()
@click.option(
    "-i",
    "--index",
    help="Name of the index where the bulk update to add embeddings is performed.",
)
@click.option(
    "-s",
    "--source",
    type=click.Choice(VALID_SOURCES),
    help=(
        "Source whose primary-aliased index will receive the bulk updated "
        "records with embeddings."
    ),
)
@click.option("-d", "--run-date", help="Run date, formatted as YYYY-MM-DD.")
@click.option("-rid", "--run-id", help="Run ID.")
@click.argument("dataset_path", type=click.Path())
@click.pass_context
def bulk_update_embeddings(
    ctx: click.Context,
    index: str,
    source: str,
    run_date: str,
    run_id: str,
    dataset_path: str,
) -> None:
    client = ctx.obj["CLIENT"]
    index = helpers.validate_bulk_cli_options(index, source, client)

    logger.info(
        f"Bulk updating records with embeddings from dataset '{dataset_path}' "
        f"into '{index}'"
    )

    update_results = {"updated": 0, "errors": 0, "total": 0}

    td = TIMDEXDataset(location=dataset_path)

    # TODO @ghukill: https://mitlibraries.atlassian.net/browse/USE-143 # noqa: FIX002
    # Remove temporary code and replace with TDA
    # method to read embeddings
    # ==== START TEMPORARY CODE ====
    # The code below reads transformed records from
    # the TIMDEX dataset. To simulate embeddings,
    # which are added to the record post-creation, a list
    # of dicts containing only the 'timdex_record_id' and
    # the new field (i.e., what would be the embedding fields)
    # is created. For simulation purposes, the 'alternate_titles'
    # field represents the new field as it is already added
    # to the OpenSearch mapping in config/opensearch_mappings.json.
    # When testing, the user is expected to pass in a source that
    # does not set this field (e.g., libguides).
    # Once TDA has been updated to read/write embeddings
    # from/to the TIMDEX dataset, this code should be replaced
    # with a simple call to read vector embeddings, which should
    # return an iter of dicts representing the embeddings.
    transformed_records = td.read_transformed_records_iter(
        run_date=run_date,
        run_id=run_id,
        action="index",
    )

    records_to_update = iter(
        [
            {
                "timdex_record_id": record["timdex_record_id"],
                "alternate_titles": [{"kind": "Test", "value": "Test Alternate Title"}],
            }
            for record in transformed_records
        ]
    )
    # ==== END TEMPORARY CODE ====
    try:
        update_results.update(tim_os.bulk_update(client, index, records_to_update))
    except BulkIndexingError as exception:
        logger.info(f"Bulk update with embeddings failed: {exception}")

    logger.info(f"Bulk update with embeddings complete: {json.dumps(update_results)}")


@main.command()
@click.option(
    "-s",
    "--source",
    type=click.Choice(VALID_SOURCES),
    required=True,
    help="TIMDEX Source to fully reindex in Opensearch.",
)
@click.option(
    "-a",
    "--alias",
    multiple=True,
    help="Alias to promote the index to in addition to the primary alias. May "
    "be repeated to promote the index to multiple aliases at once.",
)
@click.argument(
    "dataset_path",
    type=click.Path(),
    help="Location of TIMDEX parquet dataset from which transformed records are read."
    "This value can be a local filepath or an S3 URI.",
)
@click.pass_context
def reindex_source(
    ctx: click.Context,
    source: str,
    alias: tuple[str],
    dataset_path: str,
) -> None:
    """Perform a full refresh for a source in Opensearch for all current records.

    This CLI command performs the following:
        1. creates a new index for the source
        2. promotes this index as the primary for the source alias, and added to any other
        aliases passed (e.g. 'timdex')
        3. uses the TDA library to yield only current records from the parquet dataset
        for the source
        4. bulk index these records to the new Opensearch index

    The net effect is a full refresh for a source in Opensearch, ensuring only current,
    non-deleted versions of records are used from the parquet dataset.
    """
    client = ctx.obj["CLIENT"]

    # create new index
    index = helpers.generate_index_name(source)
    new_index = tim_os.create_index(ctx.obj["CLIENT"], str(index))
    logger.info("Index '%s' created.", new_index)

    # promote index
    aliases = [source, *list(alias)]
    tim_os.promote_index(client, index, extra_aliases=aliases)
    logger.info(
        "Index promoted. Current aliases for index '%s': %s",
        index,
        tim_os.get_index_aliases(client, index),
    )

    # perform bulk indexing of current records from source
    index_results = {"created": 0, "updated": 0, "errors": 0, "total": 0}

    td = TIMDEXDataset(location=dataset_path)

    # bulk index records
    records_to_index = td.read_transformed_records_iter(
        table="current_records",
        source=source,
        action="index",
    )
    try:
        index_results.update(tim_os.bulk_index(client, index, records_to_index))
    except BulkIndexingError as exception:
        logger.info(f"Bulk indexing failed: {exception}")

    summary_results = {"index": index_results}
    logger.info(f"Reindex source complete: {json.dumps(summary_results)}")


if __name__ == "__main__":
    main()
