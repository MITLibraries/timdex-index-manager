import logging
from dataclasses import dataclass
from typing import Any

import boto3

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """A class representing a single metric to be published to CloudWatch."""

    name: str
    value: int
    unit: str
    dimensions: list[dict[str, str]]

    def to_cloudwatch_metric(self) -> dict[str, Any]:
        return {
            "MetricName": self.name,
            "Value": self.value,
            "Unit": self.unit,
            "Dimensions": self._format_dimensions(),
        }

    def _format_dimensions(self) -> list:
        dimensions = []
        for dimension in self.dimensions:
            for key, value in dimension.items():
                dimensions.append({"Name": key, "Value": value})

        return dimensions


class CloudWatchMetricsClient:
    def __init__(self) -> None:
        self.client = boto3.client("cloudwatch")

    def publish_metric(self, metric: Metric, namespace: str) -> None:
        logger.info(f"Publishing '{metric.name}' to '{namespace}' namespace: {metric}")
        try:
            self.client.put_metric_data(
                Namespace=namespace, MetricData=[metric.to_cloudwatch_metric()]
            )
        except Exception:
            logger.exception(
                f"Failed to publish '{metric.name}' metric to '{namespace}' namespace",
            )
