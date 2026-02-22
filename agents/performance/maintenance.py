"""FR-03: VACUUM/ANALYZE scheduling and UC-09: Autovacuum tuning."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from framework.agent_framework import EventType
from sql import queries

logger = logging.getLogger("lakebase_ops.performance")


class MaintenanceMixin:
    """Mixin for vacuum scheduling, TXID wraparound monitoring, and autovacuum tuning."""

    def identify_tables_needing_vacuum(self, project_id: str, branch_id: str) -> dict:
        """Find tables with dead_tuple_ratio > 10% or last_autovacuum > 24h."""
        rows = self.client.execute_query(project_id, branch_id, queries.TABLES_NEEDING_VACUUM)

        needs_vacuum = []
        needs_vacuum_full = []

        for row in rows:
            dead_pct = row.get("dead_pct", 0)
            if isinstance(dead_pct, str):
                try:
                    dead_pct = float(dead_pct)
                except ValueError:
                    dead_pct = 0

            n_live = row.get("n_live_tup", 0)
            n_dead = row.get("n_dead_tup", 0)
            if n_live + n_dead > 0:
                dead_pct = (n_dead / (n_live + n_dead)) * 100

            if dead_pct > 30:
                needs_vacuum_full.append({
                    "table": row.get("relname", ""),
                    "schema": row.get("schemaname", "public"),
                    "dead_tuple_pct": round(dead_pct, 2),
                    "dead_tuples": n_dead,
                    "action": "VACUUM FULL (requires exclusive lock)",
                })
            elif dead_pct > 10:
                needs_vacuum.append({
                    "table": row.get("relname", ""),
                    "schema": row.get("schemaname", "public"),
                    "dead_tuple_pct": round(dead_pct, 2),
                    "dead_tuples": n_dead,
                    "action": "VACUUM ANALYZE",
                })

        return {
            "tables_needing_vacuum": len(needs_vacuum),
            "tables_needing_vacuum_full": len(needs_vacuum_full),
            "vacuum_targets": needs_vacuum,
            "vacuum_full_targets": needs_vacuum_full,
        }

    def schedule_vacuum_analyze(self, project_id: str, branch_id: str,
                                 tables: list[str] = None) -> dict:
        """Execute VACUUM ANALYZE on identified tables."""
        if tables is None:
            analysis = self.identify_tables_needing_vacuum(project_id, branch_id)
            tables = [t["table"] for t in analysis.get("vacuum_targets", [])]

        results = []
        for table in tables:
            stmt = f"VACUUM ANALYZE {table}"
            try:
                self.client.execute_statement(project_id, branch_id, stmt)
                results.append({"table": table, "operation": "VACUUM ANALYZE", "status": "success"})
            except Exception as e:
                results.append({"table": table, "operation": "VACUUM ANALYZE", "status": "failed", "error": str(e)})

        records = [{
            "operation_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "table_name": r["table"],
            "schema_name": "public",
            "operation_type": "VACUUM ANALYZE",
            "dead_tuples_before": 0,
            "dead_tuples_after": 0,
            "duration_seconds": 0.0,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": r["status"],
        } for r in results]
        self.writer.write_metrics("vacuum_history", records)

        self.emit_event(EventType.VACUUM_COMPLETED, {
            "project_id": project_id,
            "tables_vacuumed": len([r for r in results if r["status"] == "success"]),
        })

        return {
            "tables_vacuumed": len([r for r in results if r["status"] == "success"]),
            "tables_failed": len([r for r in results if r["status"] == "failed"]),
            "results": results,
        }

    def schedule_vacuum_full(self, project_id: str, branch_id: str, table: str) -> dict:
        """Execute VACUUM FULL on heavily bloated table."""
        locks = self.client.execute_query(
            project_id, branch_id,
            f"SELECT count(*) as lock_count FROM pg_locks WHERE relation = '{table}'::regclass AND granted"
        )
        active_locks = locks[0].get("lock_count", 0) if locks else 0

        if active_locks > 0:
            logger.warning(f"Table {table} has {active_locks} active locks, deferring VACUUM FULL")
            return {
                "table": table,
                "operation": "VACUUM FULL",
                "status": "deferred",
                "reason": f"{active_locks} active locks",
            }

        stmt = f"VACUUM FULL {table}"
        self.client.execute_statement(project_id, branch_id, stmt)

        self.writer.write_metrics("vacuum_history", [{
            "operation_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "table_name": table,
            "schema_name": "public",
            "operation_type": "VACUUM FULL",
            "dead_tuples_before": 0,
            "dead_tuples_after": 0,
            "duration_seconds": 0.0,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }])

        return {"table": table, "operation": "VACUUM FULL", "status": "success"}

    def check_txid_wraparound_risk(self, project_id: str, branch_id: str) -> dict:
        """Check transaction ID age and alert on wraparound risk."""
        rows = self.client.execute_query(project_id, branch_id, queries.TXID_WRAPAROUND_RISK)

        risk_level = "safe"
        for row in rows:
            xid_age = row.get("datfrozenxid_age", row.get("xid_age", 0))
            if isinstance(xid_age, str):
                xid_age = int(xid_age)

            if xid_age > self.thresholds.txid_age_critical:
                risk_level = "critical"
                from utils.alerting import Alert, AlertSeverity
                self.alerts.send_alert(Alert(
                    alert_id=str(uuid.uuid4())[:8],
                    severity=AlertSeverity.CRITICAL,
                    title="Transaction ID Wraparound CRITICAL",
                    message=f"XID age: {xid_age:,} ({xid_age / 2_000_000_000 * 100:.1f}% of 2B limit). Emergency VACUUM FREEZE required!",
                    source_agent=self.name,
                    metric_name="txid_age",
                    metric_value=xid_age,
                    threshold=self.thresholds.txid_age_critical,
                    project_id=project_id,
                    branch_id=branch_id,
                    sop_action="Emergency VACUUM FREEZE",
                ))
            elif xid_age > self.thresholds.txid_age_warning:
                risk_level = "warning"
                from utils.alerting import Alert, AlertSeverity
                self.alerts.send_alert(Alert(
                    alert_id=str(uuid.uuid4())[:8],
                    severity=AlertSeverity.WARNING,
                    title="Transaction ID Wraparound Warning",
                    message=f"XID age: {xid_age:,} approaching safety threshold",
                    source_agent=self.name,
                    metric_name="txid_age",
                    metric_value=xid_age,
                    threshold=self.thresholds.txid_age_warning,
                    project_id=project_id,
                    branch_id=branch_id,
                ))

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "risk_level": risk_level,
            "databases": rows,
        }

    def tune_autovacuum_parameters(self, project_id: str, branch_id: str) -> dict:
        """Dynamically adjust per-table autovacuum thresholds based on table size and churn."""
        tables = self.client.execute_query(project_id, branch_id, queries.AUTOVACUUM_CANDIDATES)

        tuning_actions = []
        for table in tables:
            n_live = table.get("n_live_tup", 0)
            relname = table.get("relname", "")

            if n_live > 1_000_000:
                threshold = max(1000, int(n_live * 0.01))
                scale_factor = 0.01
            elif n_live > 100_000:
                threshold = max(500, int(n_live * 0.05))
                scale_factor = 0.05
            else:
                continue

            stmt = f"""
                ALTER TABLE {relname} SET (
                    autovacuum_vacuum_threshold = {threshold},
                    autovacuum_vacuum_scale_factor = {scale_factor},
                    autovacuum_analyze_threshold = {threshold},
                    autovacuum_analyze_scale_factor = {scale_factor}
                )
            """
            self.client.execute_statement(project_id, branch_id, stmt)
            tuning_actions.append({
                "table": relname,
                "live_tuples": n_live,
                "vacuum_threshold": threshold,
                "scale_factor": scale_factor,
            })

        return {
            "tables_tuned": len(tuning_actions),
            "actions": tuning_actions,
        }
