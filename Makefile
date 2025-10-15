### This is the Terraform-generated header for timdex-index-manager-dev ###
ECR_NAME_DEV:=timdex-index-manager-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/timdex-index-manager-dev
### End of Terraform-generated header ###

SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

help: # preview Makefile commands
	@awk 'BEGIN { FS = ":.*#"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*#/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

#######################
# Dependency commands
#######################

install: # Install Python dependencies
	pipenv install --dev
	pipenv run pre-commit install

update: install # Update Python dependencies
	pipenv clean
	pipenv update git+https://github.com/MITLibraries/timdex-dataset-api.git
	pipenv update --dev

######################
# Unit test commands
######################

test: # Run tests and print a coverage report
	pipenv run coverage run --source=tim -m pytest -vv
	pipenv run coverage report -m

coveralls: test # Write coverage data to an LCOV report
	pipenv run coverage lcov -o ./coverage/lcov.info

####################################
# Code quality and safety commands
####################################

lint: black mypy ruff safety # Run linters

black: # Run 'black' linter and print a preview of suggested changes
	pipenv run black --check --diff .

mypy: # Run 'mypy' linter
	pipenv run mypy .

ruff: # Run 'ruff' linter and print a preview of errors
	pipenv run ruff check .

safety: # Check for security vulnerabilities and verify Pipfile.lock is up-to-date
	pipenv run pip-audit --ignore-vuln GHSA-4xh5-x5gv-qwph
	pipenv verify

lint-apply: black-apply ruff-apply # Apply changes with 'black' and resolve 'fixable errors' with 'ruff'

black-apply: # Apply changes with 'black'
	pipenv run black .

ruff-apply: # Resolve 'fixable errors' with 'ruff'
	pipenv run ruff check --fix .

## Terraform-generated commands for container build and deployment in dev
dist-dev: # build docker container (intended for developer-based manual build)
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_DEV):latest \
		-t $(ECR_URL_DEV):`git describe --always` \
		-t $(ECR_NAME_DEV):latest .

publish-dev: dist-dev # build, tag and push (intended for developer-based manual publish)
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_DEV)
	docker push $(ECR_URL_DEV):latest
	docker push $(ECR_URL_DEV):`git describe --always`

## Terraform-generated commands for container build and deployment in stage \
This requires that ECR_NAME_STAGE and ECR_URL_STAGE environment variables \
are set locally by the developer and that the developer has \
authenticated to the correct AWS Account. The values for the environment \
variables can be found in the stage_build.yml caller workflow. \
While Stage should generally only be used in an emergency for most repos, \
it is necessary for any testing requiring access to the Data Warehouse \
because Cloud Connector is not enabled on Dev1.
dist-stage:
	docker build --platform linux/amd64 \
	    -t $(ECR_URL_STAGE):latest \
		-t $(ECR_URL_STAGE):`git describe --always` \
		-t $(ECR_NAME_STAGE):latest .

publish-stage:
	docker login -u AWS -p $$(aws ecr get-login-password --region us-east-1) $(ECR_URL_STAGE)
	docker push $(ECR_URL_STAGE):latest
	docker push $(ECR_URL_STAGE):`git describe --always`

##############################
# Local Opensearch commands
##############################

local-opensearch-start: # Start local instance of Opensearch
	docker compose --env-file .env up

local-opensearch-stop: # Stop local instance of Opensearch
	docker compose --env-file .env stop

local-opensearch-teardown: # Teardown local instance of Opensearch (includes data volume)
	docker compose --env-file .env down -v