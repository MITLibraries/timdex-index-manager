import json
from unittest.mock import MagicMock, patch

from tim.cli import main
from tim.errors import BulkIndexingError

from .conftest import EXIT_CODES


@patch("timdex_dataset_api.dataset.TIMDEXDataset.load")
@patch("tim.helpers.validate_bulk_cli_options")
@patch("tim.opensearch.bulk_delete")
@patch("tim.opensearch.bulk_index")
def test_bulk_update_with_source_success(
    mock_bulk_index,
    mock_bulk_delete,
    mock_validate_bulk_cli_options,
    mock_timdex_dataset,
    caplog,
    monkeypatch,
    runner,
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    mock_bulk_index.return_value = {
        "created": 1000,
        "updated": 0,
        "errors": 0,
        "total": 1000,
    }
    mock_bulk_delete.return_value = {"deleted": 0, "errors": 0, "total": 0}
    mock_validate_bulk_cli_options.return_value = "alma"
    mock_timdex_dataset.return_value = MagicMock()

    result = runner.invoke(
        main,
        [
            "bulk-update",
            "--source",
            "alma",
            "--run-date",
            "2024-12-01",
            "--run-id",
            "abc123",
            "s3://test-timdex-bucket/dataset",
        ],
    )
    assert result.exit_code == EXIT_CODES["success"]
    assert (
        "Bulk update complete: "
        f'{{"index": {json.dumps(mock_bulk_index())}, '
        f'"delete": {json.dumps(mock_bulk_delete())}}}' in caplog.text
    )


@patch("timdex_dataset_api.dataset.TIMDEXDataset.load")
@patch("tim.helpers.validate_bulk_cli_options")
@patch("tim.opensearch.bulk_delete")
@patch("tim.opensearch.bulk_index")
def test_bulk_update_with_source_raise_bulk_indexing_error(
    mock_bulk_index,
    mock_bulk_delete,
    mock_validate_bulk_cli_options,
    mock_timdex_dataset,
    caplog,
    monkeypatch,
    runner,
):
    monkeypatch.delenv("TIMDEX_OPENSEARCH_ENDPOINT", raising=False)
    mock_bulk_index.side_effect = BulkIndexingError(
        record="alma:0", index="index", error="exception"
    )
    mock_bulk_delete.return_value = {"deleted": 0, "errors": 0, "total": 0}
    mock_validate_bulk_cli_options.return_value = "alma"
    mock_timdex_dataset.return_value = MagicMock()

    index_results_default = {
        "created": 0,
        "updated": 0,
        "errors": 0,
        "total": 0,
    }

    result = runner.invoke(
        main,
        [
            "bulk-update",
            "--source",
            "alma",
            "--run-date",
            "2024-12-01",
            "--run-id",
            "abc123",
            "s3://test-timdex-bucket/dataset",
        ],
    )
    assert result.exit_code == EXIT_CODES["success"]
    assert (
        "Bulk update complete: "
        f'{{"index": {json.dumps(index_results_default)}, '
        f'"delete": {json.dumps(mock_bulk_delete())}}}' in caplog.text
    )
