# timdex-index-manager (tim)

TIMDEX! Index Manager (TIM) is a Python cli application for managing TIMDEX indexes in OpenSearch.

## Required ENV

- `WORKSPACE` = Set to `dev` for local development, this will be set to `stage` and `prod` in those environments by Terraform.

## Optional ENV

- `AWS_REGION` = Only needed if AWS region changes from the default of us-east-1.
- `OPENSEARCH_BULK_MAX_CHUNK_BYTES` = Chunk size limit for sending requests to the bulk indexing endpoint, in bytes. Defaults to 100 MB (the opensearchpy default) if not set.
- `OPENSEARCH_BULK_MAX_RETRIES` = Maximum number of retries when sending requests to the bulk indexing endpoint. Defaults to 8 if not set.
- `OPENSEARCH_REQUEST_TIMEOUT` = Only used for OpenSearch requests that tend to take longer than the default timeout of 10 seconds, such as bulk or index refresh requests. Defaults to 120 seconds if not set.
- `SENTRY_DSN` = If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
- `STATUS_UPDATE_INTERVAL` = The ingest process logs the # of records indexed every nth record (1000 by default). Set this env variable to any integer to change the frequency of logging status updates. Can be useful for development/debugging.
- `TIMDEX_OPENSEARCH_ENDPOINT` = If using a local Docker OpenSearch instance, this isn't needed. Otherwise set to OpenSearch instance endpoint _without_ the http scheme, e.g. `search-timdex-env-1234567890.us-east-1.es.amazonaws.com`. Can also be passed directly to the CLI via the `--url` option.

## Development

- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`
- To run the app: `pipenv run tim --help`

### Local OpenSearch with Docker

A local OpenSearch instance can be started for development purposes by running:

``` bash
$ docker run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" \
  -e "plugins.security.disabled=true" \
  opensearchproject/opensearch:1.3.3
```

To confirm the instance is up, run `pipenv run tim -u localhost ping`.

### OpenSearch on AWS

1. Ensure that you have the correct AWS credentials set for the Dev1 (or desired) account.
2. Set the `TIMDEX_OPENSEARCH_ENDPOINT` variable in your .env to match the Dev1 (or desired) TIMDEX OpenSearch endpoint (note: do not include the http scheme prefix).
3. Run `pipenv run tim ping` to confirm the client is connected to the expected TIMDEX OpenSearch instance.
