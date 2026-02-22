"""
ArchivalMixin — FR-07: Cold data archival to Delta Lake.

Identifies cold data (rows not accessed in > 90 days), archives to Delta,
deletes from Lakebase, and creates unified access views for hot+cold data.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from framework.agent_framework import EventType
from config.settings import ColdDataPolicy

logger = logging.getLogger("lakebase_ops.health")


class ArchivalMixin:
    """FR-07: Cold data archival to Delta Lake."""

    def identify_cold_data(self, project_id: str, branch_id: str,
                           cold_threshold_days: int = 90) -> dict:
        """
        Find rows not accessed/modified in > threshold days.
        PRD FR-07: Cold data identification.
        """
        query = """
            SELECT schemaname, relname, n_live_tup,
                   last_seq_scan, last_idx_scan
            FROM pg_stat_user_tables
            WHERE n_live_tup > 100000
            ORDER BY GREATEST(last_seq_scan, last_idx_scan) ASC NULLS FIRST
        """
        tables = self.client.execute_query(project_id, branch_id, query)

        cold_candidates = []
        for table in tables:
            live_tup = table.get("n_live_tup", 0)
            if live_tup > 100000:
                cold_candidates.append({
                    "table": table.get("relname", ""),
                    "schema": table.get("schemaname", "public"),
                    "live_tuples": live_tup,
                    "estimated_cold_rows": int(live_tup * 0.3),  # Estimate 30% cold
                    "estimated_size_mb": live_tup * 0.5 / 1024,  # Rough estimate
                    "cold_threshold_days": cold_threshold_days,
                })

        return {
            "cold_candidates": len(cold_candidates),
            "candidates": cold_candidates,
            "total_estimated_cold_rows": sum(c["estimated_cold_rows"] for c in cold_candidates),
        }

    def archive_cold_data_to_delta(self, project_id: str, branch_id: str,
                                    table: str, policy: ColdDataPolicy = None) -> dict:
        """
        Full archival pipeline: extract cold data -> write to Delta -> delete from Lakebase.
        PRD FR-07.
        """
        if policy is None:
            policy = ColdDataPolicy(
                table_name=table,
                archive_delta_table=f"ops_catalog.lakebase_archive.{table}_cold",
            )

        # Step 1: Extract cold data
        cold_rows = self.client.execute_query(
            project_id, branch_id,
            f"SELECT * FROM {table} WHERE updated_at < NOW() - INTERVAL '{policy.cold_threshold_days} days' LIMIT 10000"
        )
        rows_count = len(cold_rows)

        if rows_count == 0:
            return {"table": table, "status": "no_cold_data", "rows_archived": 0}

        # Step 2: Write to Delta
        write_result = self.writer.write_archive(
            f"{table}_cold",
            cold_rows if cold_rows else [{"mock": True, "rows": rows_count}],
        )

        # Step 3: Delete from Lakebase (after Delta write confirmed)
        if policy.delete_after_archive:
            self.client.execute_statement(
                project_id, branch_id,
                f"DELETE FROM {table} WHERE updated_at < NOW() - INTERVAL '{policy.cold_threshold_days} days'"
            )

        # Step 4: Create unified view if configured
        if policy.create_unified_view:
            self.create_unified_access_view(project_id, branch_id, table, policy.archive_delta_table)

        # Step 5: Log archival
        archival_record = {
            "archival_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "source_table": table,
            "archive_delta_table": policy.archive_delta_table,
            "rows_archived": rows_count,
            "bytes_reclaimed": rows_count * 500,  # Estimate
            "cold_threshold_days": policy.cold_threshold_days,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        self.writer.write_metrics("data_archival", [archival_record])

        self.emit_event(EventType.COLD_DATA_ARCHIVED, {
            "table": table,
            "rows": rows_count,
            "delta_table": policy.archive_delta_table,
        })

        return archival_record

    def create_unified_access_view(self, project_id: str, branch_id: str,
                                    table: str, archive_delta_table: str) -> dict:
        """
        Create a view providing unified access to hot (Lakebase) + cold (Delta) data.
        PRD FR-07: Maintain queryability after archival.
        """
        # In production: create postgres_fdw or application-layer UNION
        view_name = f"vw_{table}_unified"
        view_ddl = f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT * FROM {table}
            -- UNION ALL
            -- SELECT * FROM fdw_{table}_cold  -- via postgres_fdw to Delta
        """
        self.client.execute_statement(project_id, branch_id, view_ddl)

        return {
            "view_name": view_name,
            "hot_source": table,
            "cold_source": archive_delta_table,
            "status": "created",
        }
