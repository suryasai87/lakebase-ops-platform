"""Operations router — vacuum, sync, branches, archival."""

from fastapi import APIRouter, Query
from ..services.sql_service import execute_query, fqn, get_cached

router = APIRouter(prefix="/api/operations", tags=["operations"])


# -- Vacuum ------------------------------------------------------------------

@router.get("/vacuum")
def vacuum_history(days: int = Query(7, ge=1, le=30)):
    """Vacuum operations grouped by date and type."""
    def fetch():
        sql = f"""
        SELECT DATE(executed_at) AS vacuum_date, operation_type,
               COUNT(*) AS operations,
               COUNT(CASE WHEN status = 'success' THEN 1 END) AS successful,
               COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed,
               ROUND(AVG(duration_seconds), 2) AS avg_duration_s
        FROM {fqn('vacuum_history')}
        WHERE executed_at > CURRENT_TIMESTAMP - INTERVAL {days} DAYS
        GROUP BY DATE(executed_at), operation_type
        ORDER BY vacuum_date DESC
        """
        return execute_query(sql)
    return get_cached(f"vacuum_{days}", fetch, ttl=300)


# -- Sync --------------------------------------------------------------------

@router.get("/sync")
def sync_status():
    """Latest sync validation status for every table pair."""
    def fetch():
        sql = f"""
        SELECT source_table, target_table, source_count, target_count,
               count_drift,
               ROUND(freshness_lag_seconds / 60.0, 1) AS lag_minutes,
               checksum_match, status, validated_at
        FROM {fqn('sync_validation_history')} sv
        WHERE validated_at = (
            SELECT MAX(validated_at)
            FROM {fqn('sync_validation_history')} sv2
            WHERE sv2.source_table = sv.source_table
        )
        """
        return execute_query(sql)
    return get_cached("sync_status", fetch, ttl=60)


# -- Branches ----------------------------------------------------------------

@router.get("/branches")
def branch_activity():
    """Branch lifecycle events over the last 30 days."""
    def fetch():
        sql = f"""
        SELECT DATE(event_timestamp) AS event_date, event_type,
               COUNT(*) AS events,
               COUNT(DISTINCT branch_id) AS unique_branches
        FROM {fqn('branch_lifecycle')}
        WHERE event_timestamp > CURRENT_TIMESTAMP - INTERVAL 30 DAYS
        GROUP BY DATE(event_timestamp), event_type
        ORDER BY event_date DESC, event_type
        """
        return execute_query(sql)
    return get_cached("branches", fetch, ttl=300)


# -- Archival ----------------------------------------------------------------

@router.get("/archival")
def archival_summary():
    """Cold-data archival operations summary."""
    def fetch():
        sql = f"""
        SELECT DATE(archived_at) AS archive_date, source_table,
               SUM(rows_archived) AS total_rows_archived,
               SUM(bytes_reclaimed) AS total_bytes_reclaimed,
               ROUND(SUM(bytes_reclaimed) / 1024.0 / 1024.0, 2) AS mb_reclaimed,
               COUNT(*) AS operations
        FROM {fqn('data_archival_history')}
        WHERE status = 'success'
        GROUP BY DATE(archived_at), source_table
        ORDER BY archive_date DESC
        """
        return execute_query(sql)
    return get_cached("archival", fetch, ttl=300)
