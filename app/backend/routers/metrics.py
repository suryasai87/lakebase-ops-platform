"""Metrics router — health KPIs and trends from lakebase_metrics."""

import random
from fastapi import APIRouter, HTTPException, Query

from ..models.metrics import MetricSnapshot, MetricTrendPoint
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# -- Adoption KPIs ----------------------------------------------------------

_ADOPTION_KPIS = [
    ("mock_classes_created", "count", 47, 32),
    ("provisioning_time_min", "min", 3.2, 8.5),
    ("dba_tickets", "count", 4, 12),
    ("dev_wait_time_hours", "hours", 0.5, 4.2),
    ("migration_success_rate", "%", 96.5, 88.0),
    ("active_branches", "count", 12, 6),
    ("ci_cd_integrations", "count", 8, 3),
    ("agent_invocations", "count", 342, 156),
    ("compliance_score", "%", 94.0, 78.0),
]

_SPRINT_NAMES = [
    "Sprint 22", "Sprint 23", "Sprint 24", "Sprint 25",
    "Sprint 26", "Sprint 27", "Sprint 28", "Sprint 29",
]


@router.get("/adoption", operation_id="metrics_adoption")
def metrics_adoption():
    """Adoption KPIs and sprint-over-sprint trend data."""
    def _trend(cur: float, prev: float) -> str:
        if cur > prev:
            return "up"
        elif cur < prev:
            return "down"
        return "flat"

    kpis = [
        {
            "name": name,
            "unit": unit,
            "current_value": current,
            "previous_value": previous,
            "trend": _trend(current, previous),
        }
        for name, unit, current, previous in _ADOPTION_KPIS
    ]

    trends = []
    for i, sprint in enumerate(_SPRINT_NAMES):
        factor = 0.4 + (i / len(_SPRINT_NAMES)) * 0.6
        trends.append({
            "sprint": sprint,
            "mock_classes_created": round(10 + 40 * factor + random.uniform(-2, 2)),
            "provisioning_time_min": round(12 - 9 * factor + random.uniform(-0.5, 0.5), 1),
            "dba_tickets": round(18 - 14 * factor + random.uniform(-1, 1)),
            "dev_wait_time_hours": round(8 - 7.5 * factor + random.uniform(-0.2, 0.2), 1),
            "migration_success_rate": round(75 + 22 * factor + random.uniform(-1, 1), 1),
            "active_branches": round(2 + 10 * factor + random.uniform(-1, 1)),
            "ci_cd_integrations": round(1 + 7 * factor + random.uniform(-0.5, 0.5)),
            "agent_invocations": round(50 + 300 * factor + random.uniform(-10, 10)),
            "compliance_score": round(65 + 30 * factor + random.uniform(-1, 1), 1),
        })

    return {"kpis": kpis, "trends": trends}

ALLOWED_METRICS = {
    "cache_hit_ratio",
    "connection_utilization",
    "dead_tuple_ratio",
    "lock_wait_time",
    "deadlocks_per_hour",
    "slow_query_pct",
    "txid_age",
    "replication_lag",
    "buffer_cache_hit",
    "connections_active",
    "connections_idle",
    "connections_total",
    "disk_usage_gb",
    "temp_files",
    "wal_bytes",
}


@router.get("/overview", operation_id="metrics_overview", response_model=list[MetricSnapshot])
def metrics_overview(
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
):
    """Latest snapshot of all health metrics."""
    safe_offset = int(offset)
    safe_limit = int(limit)

    def fetch():
        sql = f"""
        SELECT project_id, branch_id, metric_name, metric_value,
               threshold_level, snapshot_timestamp
        FROM {fqn("lakebase_metrics")}
        WHERE snapshot_timestamp = (
            SELECT MAX(snapshot_timestamp)
            FROM {fqn("lakebase_metrics")} m2
            WHERE m2.project_id = {fqn("lakebase_metrics")}.project_id
              AND m2.branch_id = {fqn("lakebase_metrics")}.branch_id
              AND m2.metric_name = {fqn("lakebase_metrics")}.metric_name
        )
        ORDER BY project_id, branch_id, metric_name
        LIMIT :row_limit OFFSET :row_offset
        """
        return execute_query(
            sql,
            parameters=[
                {"name": "row_limit", "value": safe_limit, "type": "INT"},
                {"name": "row_offset", "value": safe_offset, "type": "INT"},
            ],
        )

    return get_cached(f"metrics_overview_{safe_offset}_{safe_limit}", fetch, ttl=60)


@router.get("/trends", operation_id="metrics_trends", response_model=list[MetricTrendPoint])
def metrics_trends(
    metric: str = Query("cache_hit_ratio", description="Metric name"),
    hours: int = Query(24, ge=1, le=168),
):
    """Hourly trend for a specific metric."""
    if metric not in ALLOWED_METRICS:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Allowed: {sorted(ALLOWED_METRICS)}")

    safe_hours = int(hours)

    def fetch():
        sql = f"""
        SELECT metric_name,
               DATE_TRUNC('hour', snapshot_timestamp) AS hour,
               ROUND(AVG(metric_value), 4) AS avg_value,
               ROUND(MIN(metric_value), 4) AS min_value,
               ROUND(MAX(metric_value), 4) AS max_value
        FROM {fqn("lakebase_metrics")}
        WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL :hours HOURS
          AND metric_name = :metric_name
        GROUP BY metric_name, DATE_TRUNC('hour', snapshot_timestamp)
        ORDER BY hour
        """
        return execute_query(
            sql,
            parameters=[
                {"name": "hours", "value": safe_hours, "type": "INT"},
                {"name": "metric_name", "value": metric, "type": "STRING"},
            ],
        )

    return get_cached(f"metrics_trends_{metric}_{safe_hours}", fetch, ttl=60)
