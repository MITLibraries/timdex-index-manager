### This is the Terraform-generated header for timdex-index-manager-dev. If ###
###   this is a Lambda repo, uncomment the FUNCTION line below               ###
###   and review the other commented lines in the document.                  ###
.PHONY: test
ECR_NAME_DEV := timdex-index-manager-dev
ECR_URL_DEV := 222053980223.dkr.ecr.us-east-1.amazonaws.com/timdex-index-manager-dev
CPU_ARCH ?= $(shell cat .aws-architecture 2>/dev/null || echo "linux/amd64")
### End of Terraform-generated header                                        ###

SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

help: # Preview Makefile commands
	@awk 'BEGIN { FS = ":.*#"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*#/ { printf "  %-15s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ensure OS binaries aren't called if naming conflict with Make recipes
.PHONY: help install venv update test coveralls lint lint-fix security tim

##############################################
# Python Environment and Dependency commands
##############################################

install: .venv .git/hooks/pre-commit .git/hooks/pre-push # Install Python dependencies and create virtual environment if not exists
	uv sync --dev

.venv: # Creates virtual environment if not found
	@echo "Creating virtual environment at .venv..."
	uv venv .venv

.git/hooks/pre-commit: # Sets up pre-commit commit hooks if not setup
	@echo "Installing pre-commit commit hooks..."
	uv run pre-commit install --hook-type pre-commit

.git/hooks/pre-push: # Sets up pre-commit push hooks if not setup
	@echo "Installing pre-commit push hooks..."
	uv run pre-commit install --hook-type pre-push

venv: .venv # Create the Python virtual environment

update: # Update Python dependencies
	uv lock --upgrade
	uv sync --dev

######################
# Unit test commands
######################

test: # Run tests and print a coverage report
	uv run coverage run --source=tim -m pytest -vv
	uv run coverage report -m

coveralls: test # Write coverage data to an LCOV report
	uv run coverage lcov -o ./coverage/lcov.info

####################################
# Code linting and formatting
####################################

lint: # Run linting, alerts only, no code changes
	uv run ruff format --diff
	uv run mypy .
	uv run ruff check .

lint-fix: # Run linting, auto fix behaviors where supported
	uv run ruff format .
	uv run ruff check --fix .

security: # Run security / vulnerability checks
	uv run pip-audit

##############################
# CLI convenience commands
##############################

tim: # CLI without any arguments, utilizing uv script entrypoint
	uv run tim

#############
# Terraform
#############

### Terraform-generated Developer Deploy Commands for Dev environment ###
check-arch:
	@ARCH_FILE=".aws-architecture"; \
	if [[ "$(CPU_ARCH)" != "linux/amd64" && "$(CPU_ARCH)" != "linux/arm64" ]]; then \
        echo "Invalid CPU_ARCH: $(CPU_ARCH)"; exit 1; \
    fi; \
	if [[ -f $$ARCH_FILE ]]; then \
		echo "latest-$(shell echo $(CPU_ARCH) | cut -d'/' -f2)" > .arch_tag; \
	else \
		echo "latest" > .arch_tag; \
	fi

dist-dev: check-arch # Build docker container (intended for developer-based manual build)
	@ARCH_TAG=$$(cat .arch_tag); \
	docker buildx inspect $(ECR_NAME_DEV) >/dev/null 2>&1 || docker buildx create --name $(ECR_NAME_DEV) --use; \
	docker buildx use $(ECR_NAME_DEV); \
	docker buildx build --platform $(CPU_ARCH) \
		--load \
		--tag $(ECR_URL_DEV):$$ARCH_TAG \
		--tag $(ECR_URL_DEV):make-$$ARCH_TAG \
		--tag $(ECR_URL_DEV):make-$(shell git describe --always) \
		--tag $(ECR_NAME_DEV):$$ARCH_TAG \
		.

publish-dev: dist-dev # Build, tag and push (intended for developer-based manual publish)
	@ARCH_TAG=$$(cat .arch_tag); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL_DEV); \
	docker push $(ECR_URL_DEV):$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$(shell git describe --always); \
	echo "Cleaning up dangling Docker images..."; \
	docker image prune -f --filter "dangling=true"

### Terraform-generated Developer Deploy Commands for Stage environment ###
## This requires that ECR_NAME_STAGE and ECR_URL_STAGE environment variables
## are set locally by the developer and that the developer has
## authenticated to the correct AWS Account. The values for the environment
## variables can be found in the stage_build.yml caller workflow.
## While Stage should generally only be used in an emergency for most repos,
## it is necessary for any testing requiring access to the Data Warehouse
## because Cloud Connector is not enabled on Dev1.
dist-stage: check-arch
	@ARCH_TAG=$$(cat .arch_tag); \
	docker buildx inspect $(ECR_NAME_STAGE) >/dev/null 2>&1 || docker buildx create --name $(ECR_NAME_STAGE) --use; \
	docker buildx use $(ECR_NAME_STAGE); \
	docker buildx build --platform $(CPU_ARCH) \
		--load \
		--tag $(ECR_URL_STAGE):$$ARCH_TAG \
		--tag $(ECR_URL_STAGE):make-$$ARCH_TAG \
		--tag $(ECR_URL_STAGE):make-$(shell git describe --always) \
		--tag $(ECR_NAME_STAGE):$$ARCH_TAG \
		.

publish-stage: dist-stage
	@ARCH_TAG=$$(cat .arch_tag); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL_STAGE); \
	docker push $(ECR_URL_STAGE):$$ARCH_TAG; \
	docker push $(ECR_URL_STAGE):make-$$ARCH_TAG; \
	docker push $(ECR_URL_STAGE):make-$(shell git describe --always); \
	echo "Cleaning up dangling Docker images..."; \
	docker image prune -f --filter "dangling=true"

docker-clean: # Clean up Docker detritus
	@ARCH_TAG=$$(cat .arch_tag); \
	echo "Cleaning up Docker leftovers (containers, images, builders)"; \
	docker rmi -f $(ECR_URL_DEV):$$ARCH_TAG; \
	docker rmi -f $(ECR_URL_DEV):make-$$ARCH_TAG; \
	docker rmi -f $(ECR_URL_DEV):make-$(shell git describe --always) || true; \
	docker rmi -f $(ECR_NAME_DEV):$$ARCH_TAG || true; \
	docker buildx rm $(ECR_NAME_DEV) || true
	@rm -rf .arch_tag

##############################
# Local Opensearch commands
##############################

local-opensearch-start: # Start local instance of Opensearch
	docker compose --env-file .env up

local-opensearch-stop: # Stop local instance of Opensearch
	docker compose --env-file .env stop

local-opensearch-teardown: # Teardown local instance of Opensearch (includes data volume)
	docker compose --env-file .env down -v
