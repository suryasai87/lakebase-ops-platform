"""FR-01: pg_stat_statements persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sql import queries

logger = logging.getLogger("lakebase_ops.performance")


class MetricsMixin:
    """Mixin for pg_stat_statements persistence and stats info collection."""

    def persist_pg_stat_statements(self, project_id: str, branch_id: str) -> dict:
        """
        Capture ALL columns from pg_stat_statements and persist to Delta.
        Runs every 5 minutes for 90-day historical trending and cross-branch comparison.

        Note: pg_stat_statements is persistent since PG15+ (stats_fetch_consistency).
        Lakebase runs PG17, so stats survive restarts. We persist to Delta for
        long-term retention (90 days), cross-branch comparison, and AI/BI dashboards.
        """
        rows = self.client.execute_query(project_id, branch_id, queries.PG_STAT_STATEMENTS_FULL)

        if not rows:
            return {"status": "skipped", "reason": "no data", "records": 0}

        snapshot_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        records = []
        for row in rows:
            records.append({
                "snapshot_id": snapshot_id,
                "project_id": project_id,
                "branch_id": branch_id,
                "queryid": row.get("queryid"),
                "query": row.get("query", "")[:4000],
                "calls": row.get("calls", 0),
                "total_exec_time": row.get("total_exec_time", 0.0),
                "mean_exec_time": row.get("mean_exec_time", 0.0),
                "rows": row.get("rows", 0),
                "shared_blks_hit": row.get("shared_blks_hit", 0),
                "shared_blks_read": row.get("shared_blks_read", 0),
                "temp_blks_written": row.get("temp_blks_written", 0),
                "temp_blks_read": row.get("temp_blks_read", 0),
                "wal_records": row.get("wal_records", 0),
                "wal_fpi": row.get("wal_fpi", 0),
                "wal_bytes": row.get("wal_bytes", 0),
                "jit_functions": row.get("jit_functions", 0),
                "jit_generation_time": row.get("jit_generation_time", 0.0),
                "jit_inlining_time": row.get("jit_inlining_time", 0.0),
                "jit_optimization_time": row.get("jit_optimization_time", 0.0),
                "jit_emission_time": row.get("jit_emission_time", 0.0),
                "snapshot_timestamp": now,
            })

        write_result = self.writer.write_metrics("pg_stat_history", records)

        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "records": len(records),
            "top_query_by_time": rows[0].get("query", "")[:80] if rows else "",
            "write_result": write_result,
        }

    def collect_pg_stat_statements_info(self, project_id: str, branch_id: str) -> dict:
        """
        Query pg_stat_statements_info (PG14+) for deallocation and reset stats.
        Useful for monitoring if pg_stat_statements is evicting entries.
        """
        rows = self.client.execute_query(project_id, branch_id, queries.PG_STAT_STATEMENTS_INFO)
        if not rows:
            return {"status": "no_data"}

        info = rows[0]
        return {
            "dealloc": info.get("dealloc", 0),
            "stats_reset": info.get("stats_reset"),
            "note": "High dealloc count means pg_stat_statements.max is too low",
        }
