"""Operations router — vacuum, sync, branches, archival."""

import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query

from ..models.operations import (
    ArchivalDaySummary,
    BranchActivityDay,
    SyncTableStatus,
    VacuumDaySummary,
)
from ..services.sql_service import execute_query, fqn, get_cached

logger = logging.getLogger("lakebase_ops_app.operations")
router = APIRouter(prefix="/api/operations", tags=["operations"])


# -- Vacuum ------------------------------------------------------------------


@router.get("/vacuum", operation_id="vacuum_history", response_model=list[VacuumDaySummary])
def vacuum_history(
    days: int = Query(7, ge=1, le=30),
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
):
    """Vacuum operations grouped by date and type."""
    safe_days = int(days)
    safe_offset = int(offset)
    safe_limit = int(limit)

    def fetch():
        sql = f"""
        SELECT DATE(executed_at) AS vacuum_date, operation_type,
               COUNT(*) AS operations,
               COUNT(CASE WHEN status = 'success' THEN 1 END) AS successful,
               COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed,
               ROUND(AVG(duration_seconds), 2) AS avg_duration_s
        FROM {fqn("vacuum_history")}
        WHERE executed_at > CURRENT_TIMESTAMP - INTERVAL :days DAYS
        GROUP BY DATE(executed_at), operation_type
        ORDER BY vacuum_date DESC
        LIMIT :row_limit OFFSET :row_offset
        """
        return execute_query(
            sql,
            parameters=[
                {"name": "days", "value": safe_days, "type": "INT"},
                {"name": "row_limit", "value": safe_limit, "type": "INT"},
                {"name": "row_offset", "value": safe_offset, "type": "INT"},
            ],
        )

    return get_cached(f"vacuum_{safe_days}_{safe_offset}_{safe_limit}", fetch, ttl=300)


# -- Sync --------------------------------------------------------------------


@router.get("/sync", operation_id="sync_status", response_model=list[SyncTableStatus])
def sync_status():
    """Latest sync validation status for every table pair."""

    def fetch():
        sql = f"""
        SELECT source_table, target_table, source_count, target_count,
               count_drift,
               ROUND(freshness_lag_seconds / 60.0, 1) AS lag_minutes,
               checksum_match, status, validated_at
        FROM {fqn("sync_validation_history")} sv
        WHERE validated_at = (
            SELECT MAX(validated_at)
            FROM {fqn("sync_validation_history")} sv2
            WHERE sv2.source_table = sv.source_table
        )
        """
        return execute_query(sql)

    return get_cached("sync_status", fetch, ttl=60)


# -- Branches ----------------------------------------------------------------


@router.get("/branches", operation_id="branch_activity", response_model=list[BranchActivityDay])
def branch_activity(
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
):
    """Branch lifecycle events over the last 30 days."""
    safe_offset = int(offset)
    safe_limit = int(limit)

    def fetch():
        sql = f"""
        SELECT DATE(event_timestamp) AS event_date, event_type,
               COUNT(*) AS events,
               COUNT(DISTINCT branch_id) AS unique_branches
        FROM {fqn("branch_lifecycle")}
        WHERE event_timestamp > CURRENT_TIMESTAMP - INTERVAL 30 DAYS
        GROUP BY DATE(event_timestamp), event_type
        ORDER BY event_date DESC, event_type
        LIMIT :row_limit OFFSET :row_offset
        """
        return execute_query(
            sql,
            parameters=[
                {"name": "row_limit", "value": safe_limit, "type": "INT"},
                {"name": "row_offset", "value": safe_offset, "type": "INT"},
            ],
        )

    return get_cached(f"branches_{safe_offset}_{safe_limit}", fetch, ttl=300)


# -- Branch Status (Lakebase API) -------------------------------------------

def _get_lakebase_branches() -> list[dict]:
    """Fetch branch list from the Lakebase Database Projects API."""
    project_id = os.getenv("LAKEBASE_PROJECT_ID", "")
    if not project_id:
        return []
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        resp = w.api_client.do(
            "GET",
            f"/api/2.0/database-projects/{project_id}/branches",
        )
        branches_raw = resp.get("branches", []) if isinstance(resp, dict) else []
        now = datetime.now(timezone.utc)
        result = []
        for b in branches_raw:
            name = b.get("name", "")
            parent = b.get("parent_branch", "production")
            created = b.get("created_at", now.isoformat())
            result.append({
                "branch_name": name,
                "parent_branch": parent,
                "ttl_days": b.get("ttl_days"),
                "created_at": created,
                "creator_type": b.get("creator_type", "api"),
                "schema_drift_status": b.get("schema_drift_status", "clean"),
                "storage_mb": b.get("storage_mb", 0),
            })
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch Lakebase branches: {e}")
        return _mock_branches()


def _mock_branches() -> list[dict]:
    """Return mock branch data when the Lakebase API is unavailable."""
    now = datetime.now(timezone.utc)
    return [
        {"branch_name": "production", "parent_branch": "", "ttl_days": None,
         "created_at": (now - timedelta(days=90)).isoformat(), "creator_type": "system",
         "schema_drift_status": "clean", "storage_mb": 1024},
        {"branch_name": "dev/feature-indexes", "parent_branch": "production", "ttl_days": 14,
         "created_at": (now - timedelta(days=3)).isoformat(), "creator_type": "agent",
         "schema_drift_status": "clean", "storage_mb": 128},
        {"branch_name": "dev/migration-test", "parent_branch": "production", "ttl_days": 7,
         "created_at": (now - timedelta(days=1)).isoformat(), "creator_type": "user",
         "schema_drift_status": "drifted", "storage_mb": 256},
        {"branch_name": "staging", "parent_branch": "production", "ttl_days": None,
         "created_at": (now - timedelta(days=60)).isoformat(), "creator_type": "system",
         "schema_drift_status": "clean", "storage_mb": 512},
    ]


@router.get("/branches/status", operation_id="branch_status")
def branch_status():
    """Current branch status from the Lakebase API."""
    return get_cached("branch_status", _get_lakebase_branches, ttl=30)


@router.get("/branches/observability", operation_id="branch_observability")
def branch_observability():
    """Branch observability metrics: age distribution, storage, creation rate, TTL compliance."""
    branches = get_cached("branch_status", _get_lakebase_branches, ttl=30)
    now = datetime.now(timezone.utc)

    # Age distribution
    buckets = {"< 1 day": 0, "1-7 days": 0, "7-30 days": 0, "> 30 days": 0}
    for b in branches:
        try:
            created = datetime.fromisoformat(b["created_at"].replace("Z", "+00:00"))
            age = (now - created).days
        except Exception:
            age = 0
        if age < 1:
            buckets["< 1 day"] += 1
        elif age <= 7:
            buckets["1-7 days"] += 1
        elif age <= 30:
            buckets["7-30 days"] += 1
        else:
            buckets["> 30 days"] += 1

    # Storage per branch
    storage = [{"branch_name": b["branch_name"], "storage_mb": b.get("storage_mb", 0)} for b in branches]

    # Creation rate (last 7 days)
    creation_rate = []
    for d in range(6, -1, -1):
        day = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        created_count = sum(1 for b in branches if b["created_at"][:10] == day)
        creation_rate.append({"date": day, "created": created_count, "deleted": 0})

    # TTL compliance
    with_ttl = sum(1 for b in branches if b.get("ttl_days"))
    no_ttl = len(branches) - with_ttl
    expired = sum(1 for b in branches if b.get("ttl_days") and _is_expired(b, now))
    compliant = with_ttl - expired

    return {
        "age_distribution": [{"bucket": k, "count": v} for k, v in buckets.items()],
        "storage_per_branch": sorted(storage, key=lambda x: x["storage_mb"], reverse=True),
        "creation_rate": creation_rate,
        "ttl_compliance": [
            {"status": "Compliant", "count": compliant},
            {"status": "No TTL", "count": no_ttl},
            {"status": "Expired", "count": expired},
        ],
    }


def _is_expired(branch: dict, now: datetime) -> bool:
    try:
        created = datetime.fromisoformat(branch["created_at"].replace("Z", "+00:00"))
        ttl = branch.get("ttl_days", 0) or 0
        return (now - created).days > ttl
    except Exception:
        return False


# -- Lakehouse Sync (CDC) ---------------------------------------------------


@router.get("/lakehouse-sync", operation_id="lakehouse_sync_status")
def lakehouse_sync_status():
    """Lakehouse Sync CDC pipeline status and replication lag (GAP-032)."""

    def fetch():
        sql = f"""
        SELECT project_id, branch_id, source_table, target_table,
               lag_bytes, lag_seconds, scd2_valid, status, checked_at
        FROM {fqn("lakehouse_sync_status")} ls
        WHERE checked_at = (
            SELECT MAX(checked_at)
            FROM {fqn("lakehouse_sync_status")} ls2
            WHERE ls2.project_id = ls.project_id
              AND ls2.source_table = ls.source_table
        )
        ORDER BY lag_seconds DESC
        """
        return execute_query(sql)

    return get_cached("lakehouse_sync", fetch, ttl=60)


# -- Archival ----------------------------------------------------------------


@router.get("/archival", operation_id="archival_summary", response_model=list[ArchivalDaySummary])
def archival_summary(
    offset: int = Query(0, ge=0, description="Number of rows to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
):
    """Cold-data archival operations summary."""
    safe_offset = int(offset)
    safe_limit = int(limit)

    def fetch():
        sql = f"""
        SELECT DATE(archived_at) AS archive_date, source_table,
               SUM(rows_archived) AS total_rows_archived,
               SUM(bytes_reclaimed) AS total_bytes_reclaimed,
               ROUND(SUM(bytes_reclaimed) / 1024.0 / 1024.0, 2) AS mb_reclaimed,
               COUNT(*) AS operations
        FROM {fqn("data_archival_history")}
        WHERE status = 'success'
        GROUP BY DATE(archived_at), source_table
        ORDER BY archive_date DESC
        LIMIT :row_limit OFFSET :row_offset
        """
        return execute_query(
            sql,
            parameters=[
                {"name": "row_limit", "value": safe_limit, "type": "INT"},
                {"name": "row_offset", "value": safe_offset, "type": "INT"},
            ],
        )

    return get_cached(f"archival_{safe_offset}_{safe_limit}", fetch, ttl=300)
