"""Response models for the metrics router."""

from typing import Optional
from pydantic import BaseModel


class MetricSnapshot(BaseModel):
    """A single metric data point from the latest snapshot."""

    project_id: str
    branch_id: str
    metric_name: str
    metric_value: str
    threshold_level: Optional[str] = None
    snapshot_timestamp: str


MetricsOverviewResponse = list[MetricSnapshot]


class MetricTrendPoint(BaseModel):
    """Hourly aggregated metric trend point."""

    metric_name: str
    hour: str
    avg_value: str
    min_value: str
    max_value: str


MetricsTrendsResponse = list[MetricTrendPoint]
