import pytest
import vcr
from click.testing import CliRunner
from timdex_dataset_api import TIMDEXDataset

import tim.opensearch as tim_os

EXIT_CODES = {
    "success": 0,
    "error": 1,
    "invalid_command": 2,
}
my_vcr = vcr.VCR(
    cassette_library_dir="tests/fixtures/cassettes",
    filter_headers=["authorization"],
)


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test")
    monkeypatch.setenv("TIMDEX_OPENSEARCH_ENDPOINT", "localhost")


@pytest.fixture
def test_opensearch_client():
    return tim_os.configure_opensearch_client("localhost")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def timdex_dataset() -> TIMDEXDataset:
    return TIMDEXDataset("tests/fixtures/dataset")


@pytest.fixture
def five_valid_index_libguides_records(timdex_dataset):
    return timdex_dataset.read_transformed_records_iter(
        run_id="85cfe316-089c-4639-a5af-c861a7321493"
    )


@pytest.fixture
def one_invalid_index_libguides_records(timdex_dataset):
    return timdex_dataset.read_transformed_records_iter(
        run_id="21e7f272-7b96-480c-9c25-36075355fc4c"
    )


@pytest.fixture
def one_valid_delete_libguides_records(timdex_dataset):
    return timdex_dataset.read_transformed_records_iter(
        run_id="59d938b9-df61-481b-bec9-9d9eb8fbf21c"
    )


@pytest.fixture
def one_valid_delete_libguides_records_not_found(timdex_dataset):
    return timdex_dataset.read_transformed_records_iter(
        run_id="3718935d-2bc0-4385-919e-c7a83238215e"
    )
