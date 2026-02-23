"""Metrics router — health KPIs and trends from lakebase_metrics."""

from fastapi import APIRouter, Query
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _fetch_overview():
    sql = f"""
    SELECT project_id, branch_id, metric_name, metric_value,
           threshold_level, snapshot_timestamp
    FROM {fqn('lakebase_metrics')}
    WHERE snapshot_timestamp = (
        SELECT MAX(snapshot_timestamp)
        FROM {fqn('lakebase_metrics')} m2
        WHERE m2.project_id = {fqn('lakebase_metrics')}.project_id
          AND m2.branch_id = {fqn('lakebase_metrics')}.branch_id
          AND m2.metric_name = {fqn('lakebase_metrics')}.metric_name
    )
    ORDER BY project_id, branch_id, metric_name
    """
    return execute_query(sql)


@router.get("/overview")
def metrics_overview():
    """Latest snapshot of all health metrics."""
    return get_cached("metrics_overview", _fetch_overview, ttl=60)


@router.get("/trends")
def metrics_trends(
    metric: str = Query("cache_hit_ratio", description="Metric name"),
    hours: int = Query(24, ge=1, le=168),
):
    """Hourly trend for a specific metric."""
    def fetch():
        sql = f"""
        SELECT metric_name,
               DATE_TRUNC('hour', snapshot_timestamp) AS hour,
               ROUND(AVG(metric_value), 4) AS avg_value,
               ROUND(MIN(metric_value), 4) AS min_value,
               ROUND(MAX(metric_value), 4) AS max_value
        FROM {fqn('lakebase_metrics')}
        WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
          AND metric_name = '{metric}'
        GROUP BY metric_name, DATE_TRUNC('hour', snapshot_timestamp)
        ORDER BY hour
        """
        return execute_query(sql)
    return get_cached(f"metrics_trends_{metric}_{hours}", fetch, ttl=60)
