# timdex-index-manager (tim)

TIMDEX! Index Manager (TIM) is a Python cli application for managing TIMDEX indexes in OpenSearch.

## Required ENV

- `OPENSEARCH_ENDPOINT` = Optional (can also be passed directly to the CLI via the `--url` option). If using a local Docker OpenSearch instance, this isn't needed. Otherwise set to OpenSearch instance endpoint _without_ the http scheme, e.g. `search-timdex-env-1234567890.us-east-1.es.amazonaws.com`
- `SENTRY_DSN` = If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
- `WORKSPACE` = Set to `dev` for local development, this will be set to `stage` and `prod` in those environments by Terraform.

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
2. Set the `OPENSEARCH_ENDPOINT` variable in your .env to match the Dev1 (or desired) TIMDEX OpenSearch endpoint (note: do not include the http scheme prefix).
3. Run `pipenv run tim ping` to confirm the client is connected to the expected TIMDEX OpenSearch instance.
