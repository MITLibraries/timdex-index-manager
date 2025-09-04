# timdex-index-manager (tim)

TIMDEX! Index Manager (TIM) is a Python CLI application for managing TIMDEX indices in OpenSearch.

## Development

- To preview a list of available Makefile commands: `make help`
- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- To run local OpenSearch with Docker: `make local-opensearch`
- To run the app: `pipenv run tim --help`

**Important note:** The sections that follow provide instructions for running OpenSearch **locally with Docker**. These instructions are useful for testing. Please make sure the environment variable `TIMDEX_OPENSEARCH_ENDPOINT` is **not** set before proceeding.

### Running OpenSearch locally with Docker

1. Run the following command:

``` bash
docker run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" \
-e "plugins.security.disabled=true" \
opensearchproject/opensearch:2
```

2. To confirm the instance is up, run `pipenv run tim -u localhost ping` or visit http://localhost:9200/. This should produce a log that looks like the following:
 
```text
2024-02-08 13:22:16,826 INFO tim.cli.main(): OpenSearch client configured for endpoint 'localhost'

Name: docker-cluster
UUID: RVCmwQ_LQEuh1GrtwGnRMw
OpenSearch version: 2.11.1
Lucene version: 9.7.0

2024-02-08 13:22:16,930 INFO tim.cli.log_process_time(): Total time to complete process: 0:00:00.105506
```

### Running Opensearch and OpenSearch Dashboards locally with Docker

You can use the included Docker Compose file ([compose.yaml](compose.yaml)) to start an OpenSearch instance along with OpenSearch Dashboards, "[the user interface that lets you visualize your Opensearch data and run and scale your OpenSearch clusters](https://opensearch.org/docs/latest/dashboards/)". Two tools that are useful for exploring indices are [DevTools](https://opensearch.org/docs/latest/dashboards/dev-tools/index-dev/) and [Discover](https://opensearch.org/docs/latest/dashboards/discover/index-discover/).

**Note:** To use Discover, you'll need to create an index pattern. When creating the index pattern, decline the option to set a date field. When set, it detects a date field in our indices but then crashes trying to use it. When prompted, enter an index or alias to pull patterns from, and it will automatically be configured to work well enough for initial data exploration.

First, ensure the following environment variables are set:

0. First, set some environment variables:

```shell
OPENSEARCH_INITIAL_ADMIN_PASSWORD=SuperSecret42!
```

1. Run the following command:

```shell
docker pull opensearchproject/opensearch:2
docker pull opensearchproject/opensearch-dashboards:2
docker compose up
```

2. To confirm the instance is up, run `pipenv run tim ping` or visit http://localhost:9200/.

3. Access OpenSearch Dashboards through <http://localhost:5601>.

For a more detailed example with test data, please refer to the Confluence document: [How to run and query OpenSearch locally](https://mitlibraries.atlassian.net/wiki/spaces/D/pages/3586129972/How+to+run+and+query+OpenSearch+locally).

### Index records into local OpenSearch Docker container

1. Follow the instructions in either [Running Opensearch locally with Docker](#running-opensearch-locally-with-docker) or [Running Opensearch and OpenSearch Dashboards locally with Docker](#running-opensearch-and-opensearch-dashboards-locally-with-docker). 

2. Open a new terminal, and create a new index. Copy the name of the created index printed to the terminal's output.

```shell
pipenv run tim create -s <source-name>
```

3. Copy the index name and promote the index to the alias.

```shell
pipenv run tim promote -a <source-name> -i <index-name>
```

4. Bulk index records from a specified directory (e.g., including S3).

```shell
pipenv run tim bulk-index -s <source-name> <filepath-to-records>
``` 

5. After verifying that the bulk-index was successful, clean up your local OpenSearch instance by deleting the index.

```shell
pipenv run tim delete -i <index-name>
```

### Running OpenSearch on AWS

1. Ensure that you have the correct AWS credentials set for the Dev1 (or desired) account.

2. Set the `TIMDEX_OPENSEARCH_ENDPOINT` variable in your .env to match the Dev1 (or desired) TIMDEX OpenSearch endpoint (note: do not include the http scheme prefix).

3. Run `pipenv run tim ping` to confirm the client is connected to the expected TIMDEX OpenSearch instance.


## Environment Variables 

### Required ENV

```shell
WORKSPACE=### Set to `dev` for local development, this will be set to `stage` and `prod` in those environments by Terraform.
```

## Optional ENV

```shell
AWS_REGION=### Only needed if AWS region changes from the default of us-east-1.
OPENSEARCH_BULK_MAX_CHUNK_BYTES=### Chunk size limit for sending requests to the bulk indexing endpoint, in bytes. Defaults to 104857600 (100 * 1024 * 1024) if not set.
OPENSEARCH_BULK_MAX_RETRIES=### Maximum number of retries when sending requests to the bulk indexing endpoint. Defaults to 50 if not set.
OPENSEARCH_INITIAL_ADMIN_PASSWORD=###If using a local Docker OpenSearch instance, this must be set (for versions >= 2.12.0).
OPENSEARCH_REQUEST_TIMEOUT=### Only used for OpenSearch requests that tend to take longer than the default timeout of 10 seconds, such as bulk or index refresh requests. Defaults to 120 seconds if not set.
STATUS_UPDATE_INTERVAL=### The ingest process logs the # of records indexed every nth record. Set this env variable to any integer to change the frequency of logging status updates. Can be useful for development/debugging. Defaults to 1000 if not set.
TIMDEX_OPENSEARCH_ENDPOINT=### If using a local Docker OpenSearch instance, this isn't needed. Otherwise set to OpenSearch instance endpoint without the http scheme (e.g., "search-timdex-env-1234567890.us-east-1.es.amazonaws.com"). Can also be passed directly to the CLI via the `--url` option.
SENTRY_DSN=### If set to a valid Sentry DSN, enables Sentry exception monitoring This is not needed for local development.
```

## CLI commands

All CLI commands can be run with `pipenv run`. 

```
 Usage: tim [OPTIONS] COMMAND [ARGS]...                                                                                  
                                                                                                                         
 TIM provides commands for interacting with OpenSearch indexes.                                                          
 For more details on a specific command, run tim COMMAND -h.                                                             
                                                                                                                         
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --url      -u  TEXT  The OpenSearch instance endpoint minus the http scheme, e.g.                                     │
│                      'search-timdex-env-1234567890.us-east-1.es.amazonaws.com'. If not provided, will attempt to get  │
│                      from the TIMDEX_OPENSEARCH_ENDPOINT environment variable. Defaults to 'localhost'.               │
│ --verbose  -v        Pass to log at debug level instead of info                                                       │
│ --help     -h        Show this message and exit.                                                                      │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Get cluster-level information ───────────────────────────────────────────────────────────────────────────────────────╮
│ ping           Ping OpenSearch and display information about the cluster.                                             │
│ indexes        Display summary information about all indexes in the cluster.                                          │
│ aliases        List OpenSearch aliases and their associated indexes.                                                  │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Index management commands ───────────────────────────────────────────────────────────────────────────────────────────╮
│ create      Create a new index in the cluster.                                                                        │
│ delete      Delete an index.                                                                                          │
│ promote     Promote index as the primary alias and add it to any additional provided aliases.                         │
│ demote      Demote an index from all its associated aliases.                                                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Bulk record processing commands ─────────────────────────────────────────────────────────────────────────────────────╮
│ bulk-update          Bulk update records for an index.                                                                │
│ reindex-source       Perform a full refresh for a source in Opensearch for all current records.                       │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

