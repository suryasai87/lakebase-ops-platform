"""Performance router — slow queries and regression detection."""

from fastapi import APIRouter, Query
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/queries")
def slow_queries(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(10, ge=1, le=50),
):
    """Top N slowest queries over the given window."""
    def fetch():
        sql = f"""
        SELECT query, queryid,
               SUM(calls) AS total_calls,
               ROUND(AVG(mean_exec_time), 2) AS avg_exec_time_ms,
               ROUND(SUM(total_exec_time), 2) AS total_time_ms,
               SUM(rows) AS total_rows,
               ROUND(SUM(shared_blks_read) * 8.0 / 1024, 2) AS total_read_mb,
               MAX(snapshot_timestamp) AS last_seen
        FROM {fqn('pg_stat_history')}
        WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
        GROUP BY query, queryid
        ORDER BY total_time_ms DESC
        LIMIT {limit}
        """
        return execute_query(sql)
    return get_cached(f"slow_queries_{hours}_{limit}", fetch, ttl=60)


@router.get("/regressions")
def regressions():
    """Detect query performance regressions (last 2h vs previous day)."""
    def fetch():
        sql = f"""
        WITH recent AS (
            SELECT queryid, AVG(mean_exec_time) AS recent_avg
            FROM {fqn('pg_stat_history')}
            WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 2 HOURS
            GROUP BY queryid
        ),
        baseline AS (
            SELECT queryid, AVG(mean_exec_time) AS baseline_avg
            FROM {fqn('pg_stat_history')}
            WHERE snapshot_timestamp BETWEEN CURRENT_TIMESTAMP - INTERVAL 25 HOURS
                                            AND CURRENT_TIMESTAMP - INTERVAL 1 HOUR
            GROUP BY queryid
        )
        SELECT r.queryid,
               ROUND(b.baseline_avg, 2) AS baseline_ms,
               ROUND(r.recent_avg, 2) AS recent_ms,
               ROUND((r.recent_avg - b.baseline_avg) / NULLIF(b.baseline_avg, 0) * 100, 1) AS pct_change,
               CASE
                   WHEN r.recent_avg > b.baseline_avg * 2 THEN 'REGRESSION'
                   WHEN r.recent_avg > b.baseline_avg * 1.5 THEN 'WARNING'
                   ELSE 'STABLE'
               END AS status
        FROM recent r
        JOIN baseline b ON r.queryid = b.queryid
        WHERE b.baseline_avg > 0
        ORDER BY pct_change DESC
        LIMIT 20
        """
        return execute_query(sql)
    return get_cached("regressions", fetch, ttl=60)
