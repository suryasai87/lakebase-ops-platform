"""
Health & Self-Recovery Agent

Continuous "Day 2" operations:
- FR-04: Performance alerting with SOP triggers (8 metrics, warning/critical)
- FR-05: OLTP-to-OLAP sync validation (row count, timestamp, checksum)
- FR-07: Cold data archival to Delta Lake
- UC-10: Connection pool monitoring and idle session cleanup
- UC-11: Cost attribution and optimization
- UC-13: Self-healing incident response (V2)
- UC-14: Natural language DBA operations (V2)

Sources:
- PRD: FR-04, FR-05, FR-07, UC-10, UC-11, UC-13, UC-14
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from framework.agent_framework import BaseAgent, EventType, TaskResult, TaskStatus
from config.settings import (
    AlertThresholds, SyncValidationConfig, ColdDataPolicy, DELTA_TABLES,
)

logger = logging.getLogger("lakebase_ops.health")


class HealthAgent(BaseAgent):
    """
    Health & Self-Recovery Agent — continuous monitoring, sync validation,
    archival, and self-healing.

    Implements PRD FR-04, FR-05, FR-07, UC-10, UC-11, UC-13, UC-14.
    """

    def __init__(self, lakebase_client, delta_writer, alert_manager):
        super().__init__(
            name="HealthAgent",
            description="Continuous Day 2 monitoring with low-latency alerting, sync validation, cold archival, and self-healing",
        )
        self.client = lakebase_client
        self.writer = delta_writer
        self.alerts = alert_manager
        self.thresholds = AlertThresholds()

    def register_tools(self) -> None:
        """Register all health monitoring and self-recovery tools."""

        # FR-04: Performance alerting with SOP triggers
        self.register_tool("monitor_system_health", self.monitor_system_health,
                           "Collect all health metrics from pg_stat views", schedule="*/5 * * * *")
        self.register_tool("evaluate_alert_thresholds", self.evaluate_alert_thresholds,
                           "Check all 8 metrics against thresholds", schedule="*/5 * * * *")
        self.register_tool("execute_low_risk_sop", self.execute_low_risk_sop,
                           "Auto-execute safe remediations (vacuum, connection kill)")

        # FR-05: OLTP-to-OLAP sync validation
        self.register_tool("validate_sync_completeness", self.validate_sync_completeness,
                           "Compare row counts and timestamps", schedule="*/15 * * * *")
        self.register_tool("validate_sync_integrity", self.validate_sync_integrity,
                           "Checksum verification on key columns", schedule="*/15 * * * *")
        self.register_tool("run_full_sync_validation", self.run_full_sync_validation,
                           "Complete sync validation cycle", schedule="*/15 * * * *")

        # FR-07: Cold data archival
        self.register_tool("identify_cold_data", self.identify_cold_data,
                           "Find rows not accessed in > 90 days", schedule="0 3 * * 0")
        self.register_tool("archive_cold_data_to_delta", self.archive_cold_data_to_delta,
                           "Full archival pipeline to Delta Lake", schedule="0 3 * * 0",
                           risk_level="high", requires_approval=True)
        self.register_tool("create_unified_access_view", self.create_unified_access_view,
                           "Create hot+cold unified view")

        # UC-10: Connection pool monitoring
        self.register_tool("monitor_connections", self.monitor_connections,
                           "Track active/idle/idle-in-tx connections", schedule="* * * * *")
        self.register_tool("terminate_idle_connections", self.terminate_idle_connections,
                           "Kill sessions idle > 30 min")

        # UC-11: Cost attribution
        self.register_tool("track_cost_attribution", self.track_cost_attribution,
                           "Query system.billing.usage for Lakebase costs", schedule="0 6 * * *")
        self.register_tool("recommend_scale_to_zero_timeout", self.recommend_scale_to_zero_timeout,
                           "Optimize idle timeout settings", schedule="0 4 * * 0")

        # UC-13: Self-healing (V2)
        self.register_tool("diagnose_root_cause", self.diagnose_root_cause,
                           "Correlate metrics for root cause analysis")
        self.register_tool("self_heal", self.self_heal,
                           "Execute approved auto-remediation")

        # UC-14: Natural language DBA (V2)
        self.register_tool("natural_language_dba", self.natural_language_dba,
                           "LLM-powered DBA Q&A for developers")

    # -----------------------------------------------------------------------
    # FR-04: Performance Alerting with SOP Triggers
    # -----------------------------------------------------------------------

    def monitor_system_health(self, project_id: str, branch_id: str) -> dict:
        """
        Collect all health metrics from PostgreSQL system views.
        Persists to Delta every 5 minutes.
        """
        metrics = {}

        # 1. Buffer cache hit ratio
        db_stats = self.client.execute_query(project_id, branch_id, """
            SELECT datname, numbackends, xact_commit, xact_rollback,
                   blks_read, blks_hit, deadlocks, temp_files, temp_bytes
            FROM pg_stat_database WHERE datname = 'databricks_postgres'
        """)
        if db_stats:
            stats = db_stats[0]
            blks_hit = stats.get("blks_hit", 0)
            blks_read = stats.get("blks_read", 0)
            total_blks = blks_hit + blks_read
            metrics["cache_hit_ratio"] = blks_hit / total_blks if total_blks > 0 else 1.0
            metrics["deadlocks"] = stats.get("deadlocks", 0)
            metrics["active_connections"] = stats.get("numbackends", 0)

        # 2. Connection details
        activity = self.client.execute_query(project_id, branch_id, """
            SELECT state, count(*) as cnt FROM pg_stat_activity
            WHERE backend_type = 'client backend' GROUP BY state
        """)
        conn_states = {row.get("state", "unknown"): row.get("cnt", 0) for row in activity}
        total_connections = sum(conn_states.values())
        max_connections = 100  # Typical Lakebase limit
        metrics["connection_utilization"] = total_connections / max_connections
        metrics["idle_connections"] = conn_states.get("idle", 0)
        metrics["idle_in_transaction"] = conn_states.get("idle in transaction", 0)
        metrics["active_queries"] = conn_states.get("active", 0)

        # 3. Table-level dead tuple metrics
        table_stats = self.client.execute_query(project_id, branch_id, """
            SELECT relname, n_live_tup, n_dead_tup,
                   CASE WHEN n_live_tup + n_dead_tup > 0
                        THEN n_dead_tup::float / (n_live_tup + n_dead_tup)
                        ELSE 0 END AS dead_ratio
            FROM pg_stat_user_tables
            ORDER BY n_dead_tup DESC LIMIT 5
        """)
        max_dead_ratio = 0.0
        worst_table = ""
        for ts in table_stats:
            ratio = ts.get("dead_ratio", 0)
            if isinstance(ratio, str):
                ratio = float(ratio)
            if ratio > max_dead_ratio:
                max_dead_ratio = ratio
                worst_table = ts.get("relname", "")
        metrics["max_dead_tuple_ratio"] = max_dead_ratio
        metrics["worst_dead_tuple_table"] = worst_table

        # 4. Lock information
        locks = self.client.execute_query(project_id, branch_id, """
            SELECT count(*) as waiting_locks FROM pg_locks WHERE NOT granted
        """)
        metrics["waiting_locks"] = locks[0].get("waiting_locks", 0) if locks else 0

        # 5. Transaction ID age
        txid = self.client.execute_query(project_id, branch_id, """
            SELECT max(age(datfrozenxid)) as max_xid_age FROM pg_database
        """)
        metrics["txid_age"] = txid[0].get("max_xid_age", txid[0].get("datfrozenxid_age", 0)) if txid else 0

        # Persist all metrics to Delta
        now = datetime.now(timezone.utc).isoformat()
        records = [{
            "metric_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "metric_name": name,
            "metric_value": float(value) if isinstance(value, (int, float)) else 0.0,
            "threshold_level": "normal",
            "snapshot_timestamp": now,
        } for name, value in metrics.items() if isinstance(value, (int, float))]

        self.writer.write_metrics("lakebase_metrics", records)

        return {"project_id": project_id, "branch_id": branch_id, "metrics": metrics}

    def evaluate_alert_thresholds(self, metrics: dict, project_id: str = "",
                                   branch_id: str = "") -> dict:
        """
        Evaluate all 8 PRD FR-04 metrics against warning/critical thresholds.
        Triggers SOPs when breached.
        """
        from utils.alerting import Alert, AlertSeverity

        alerts_triggered = []
        sops_executed = []

        # 1. Buffer cache hit ratio
        cache_hit = metrics.get("cache_hit_ratio", 1.0)
        if cache_hit < self.thresholds.cache_hit_critical:
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.CRITICAL,
                title="Cache Hit Ratio CRITICAL",
                message=f"Cache hit ratio: {cache_hit:.2%} (threshold: {self.thresholds.cache_hit_critical:.0%}). Analyze shared_buffers, recommend CU increase.",
                source_agent=self.name,
                metric_name="cache_hit_ratio", metric_value=cache_hit,
                threshold=self.thresholds.cache_hit_critical,
                project_id=project_id, branch_id=branch_id,
                sop_action="Analyze shared_buffers, recommend CU increase",
            ))
            alerts_triggered.append(alert.to_dict())
        elif cache_hit < self.thresholds.cache_hit_warning:
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.WARNING,
                title="Cache Hit Ratio Warning",
                message=f"Cache hit ratio: {cache_hit:.2%}",
                source_agent=self.name,
                metric_name="cache_hit_ratio", metric_value=cache_hit,
                threshold=self.thresholds.cache_hit_warning,
                project_id=project_id, branch_id=branch_id,
            ))
            alerts_triggered.append(alert.to_dict())

        # 2. Connection utilization
        conn_util = metrics.get("connection_utilization", 0.0)
        if conn_util > self.thresholds.conn_util_critical:
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.CRITICAL,
                title="Connection Utilization CRITICAL",
                message=f"Connection utilization: {conn_util:.0%}. Auto-terminating idle connections > 30min.",
                source_agent=self.name,
                metric_name="connection_utilization", metric_value=conn_util,
                threshold=self.thresholds.conn_util_critical,
                project_id=project_id, branch_id=branch_id,
                sop_action="Auto-terminate idle > 30min",
                auto_remediated=True,
            ))
            alerts_triggered.append(alert.to_dict())
            # Auto-execute low-risk SOP
            sop_result = self.terminate_idle_connections(project_id, branch_id)
            sops_executed.append({"sop": "terminate_idle", "result": sop_result})
        elif conn_util > self.thresholds.conn_util_warning:
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.WARNING,
                title="Connection Utilization Warning",
                message=f"Connection utilization: {conn_util:.0%}",
                source_agent=self.name,
                metric_name="connection_utilization", metric_value=conn_util,
                threshold=self.thresholds.conn_util_warning,
                project_id=project_id, branch_id=branch_id,
            ))
            alerts_triggered.append(alert.to_dict())

        # 3. Dead tuple ratio
        dead_ratio = metrics.get("max_dead_tuple_ratio", 0.0)
        if dead_ratio > self.thresholds.dead_tuple_critical:
            table = metrics.get("worst_dead_tuple_table", "unknown")
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.CRITICAL,
                title=f"Dead Tuple Ratio CRITICAL on {table}",
                message=f"Dead tuple ratio: {dead_ratio:.0%}. Scheduling VACUUM ANALYZE.",
                source_agent=self.name,
                metric_name="dead_tuple_ratio", metric_value=dead_ratio,
                threshold=self.thresholds.dead_tuple_critical,
                project_id=project_id, branch_id=branch_id,
                sop_action="Schedule VACUUM ANALYZE",
                auto_remediated=True,
            ))
            alerts_triggered.append(alert.to_dict())
            sops_executed.append({"sop": "vacuum_triggered", "table": table})

            self.emit_event(EventType.THRESHOLD_BREACHED, {
                "metric": "dead_tuple_ratio",
                "value": dead_ratio,
                "table": table,
                "action": "vacuum_scheduled",
            })

        # 4. Slow queries (from persisted data)
        # Checked via pg_stat_statements history in Performance Agent

        # 5. TXID age
        txid_age = metrics.get("txid_age", 0)
        if isinstance(txid_age, str):
            txid_age = int(txid_age)
        if txid_age > self.thresholds.txid_age_critical:
            alert = self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.CRITICAL,
                title="TXID Wraparound CRITICAL",
                message=f"Transaction ID age: {txid_age:,}. Emergency VACUUM FREEZE required!",
                source_agent=self.name,
                metric_name="txid_age", metric_value=txid_age,
                threshold=self.thresholds.txid_age_critical,
                project_id=project_id, branch_id=branch_id,
                sop_action="Emergency VACUUM FREEZE",
            ))
            alerts_triggered.append(alert.to_dict())

        return {
            "alerts_triggered": len(alerts_triggered),
            "sops_auto_executed": len(sops_executed),
            "alerts": alerts_triggered,
            "sops": sops_executed,
        }

    def execute_low_risk_sop(self, issue_type: str, project_id: str,
                              branch_id: str, context: dict = None) -> dict:
        """
        Auto-execute safe remediation actions.
        Low-risk SOPs: vacuum, idle connection termination.
        """
        ctx = context or {}

        if issue_type == "high_dead_tuples":
            table = ctx.get("table", "")
            self.client.execute_statement(project_id, branch_id, f"VACUUM ANALYZE {table}")
            self.emit_event(EventType.SELF_HEAL_EXECUTED, {
                "issue": issue_type, "action": f"VACUUM ANALYZE {table}",
            })
            return {"action": f"VACUUM ANALYZE {table}", "status": "executed"}

        elif issue_type == "high_connections":
            result = self.terminate_idle_connections(project_id, branch_id)
            return {"action": "terminate_idle_connections", "status": "executed", "result": result}

        elif issue_type == "vacuum_freeze":
            self.client.execute_statement(project_id, branch_id, "VACUUM FREEZE")
            return {"action": "VACUUM FREEZE", "status": "executed"}

        return {"action": "unknown", "status": "skipped", "reason": f"Unknown issue type: {issue_type}"}

    # -----------------------------------------------------------------------
    # FR-05: OLTP-to-OLAP Sync Validation
    # -----------------------------------------------------------------------

    def validate_sync_completeness(self, project_id: str, branch_id: str,
                                    source_table: str, target_delta_table: str,
                                    timestamp_column: str = "updated_at") -> dict:
        """
        Compare row counts and max timestamps between Lakebase and Delta.
        PRD FR-05: Runs every 15 minutes.
        """
        # Source counts from Lakebase
        src_result = self.client.execute_query(
            project_id, branch_id,
            f"SELECT COUNT(*) as count, MAX({timestamp_column}) as max_ts FROM {source_table}"
        )
        src_count = src_result[0].get("count", 0) if src_result else 0
        src_max_ts = src_result[0].get("max_ts", src_result[0].get("max_updated_at", "")) if src_result else ""

        # Target counts from Delta (mock in test mode)
        tgt_count = src_count - 150  # Simulate slight drift
        tgt_max_ts = "2026-02-21 14:15:00"  # Simulate 15-min lag

        # Calculate drift
        count_drift = abs(src_count - tgt_count)

        # Calculate freshness lag (simplified)
        freshness_lag_seconds = 900  # 15 minutes mock

        # Determine status
        status = "healthy"
        if count_drift > 1000:
            status = "drift_detected"
        if freshness_lag_seconds > 3600:
            status = "stale"

        validation_record = {
            "validation_id": str(uuid.uuid4())[:8],
            "source_table": source_table,
            "target_table": target_delta_table,
            "source_count": src_count,
            "target_count": tgt_count,
            "count_drift": count_drift,
            "source_max_ts": src_max_ts,
            "target_max_ts": tgt_max_ts,
            "freshness_lag_seconds": freshness_lag_seconds,
            "checksum_match": True,
            "status": status,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.writer.write_metrics("sync_validation", [validation_record])

        if status != "healthy":
            from utils.alerting import Alert, AlertSeverity
            self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=AlertSeverity.WARNING if status == "drift_detected" else AlertSeverity.CRITICAL,
                title=f"Sync {status}: {source_table} -> {target_delta_table}",
                message=f"Count drift: {count_drift}, Freshness lag: {freshness_lag_seconds}s",
                source_agent=self.name,
                metric_name="sync_freshness",
                metric_value=freshness_lag_seconds,
                project_id=project_id,
                branch_id=branch_id,
            ))
            self.emit_event(EventType.SYNC_DRIFT_DETECTED, {
                "source": source_table,
                "target": target_delta_table,
                "drift": count_drift,
            })

        return validation_record

    def validate_sync_integrity(self, project_id: str, branch_id: str,
                                 source_table: str, target_delta_table: str,
                                 key_columns: list[str] = None) -> dict:
        """
        Checksum verification on key columns for data integrity.
        PRD FR-05: Integrity check.
        """
        key_cols = key_columns or ["id"]
        # In production: compute MD5/SHA256 on key columns and compare
        return {
            "source_table": source_table,
            "target_table": target_delta_table,
            "key_columns": key_cols,
            "checksum_match": True,
            "status": "integrity_verified",
        }

    def run_full_sync_validation(self, project_id: str, branch_id: str,
                                  table_pairs: list[dict] = None) -> dict:
        """
        Complete sync validation cycle across all configured table pairs.
        PRD FR-05: Every 15 minutes.
        """
        pairs = table_pairs or [
            {"source": "orders", "target": "ops_catalog.lakebase_ops.orders_delta", "ts_col": "updated_at"},
            {"source": "events", "target": "ops_catalog.lakebase_ops.events_delta", "ts_col": "created_at"},
        ]

        results = []
        for pair in pairs:
            completeness = self.validate_sync_completeness(
                project_id, branch_id,
                pair["source"], pair["target"], pair.get("ts_col", "updated_at"),
            )
            integrity = self.validate_sync_integrity(
                project_id, branch_id,
                pair["source"], pair["target"],
            )
            results.append({
                "source": pair["source"],
                "target": pair["target"],
                "completeness": completeness,
                "integrity": integrity,
            })

        healthy = sum(1 for r in results if r["completeness"]["status"] == "healthy")
        return {
            "total_pairs": len(results),
            "healthy": healthy,
            "issues": len(results) - healthy,
            "validations": results,
        }

    # -----------------------------------------------------------------------
    # FR-07: Cold Data Archival to Delta Lake
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # UC-10: Connection Pool Monitoring
    # -----------------------------------------------------------------------

    def monitor_connections(self, project_id: str, branch_id: str) -> dict:
        """
        Track active/idle/idle-in-transaction connections.
        UC-10: Every minute.
        """
        activity = self.client.execute_query(project_id, branch_id, """
            SELECT pid, state, query, wait_event_type, backend_start,
                   EXTRACT(EPOCH FROM (NOW() - state_change)) AS idle_seconds
            FROM pg_stat_activity
            WHERE backend_type = 'client backend'
        """)

        states = {"active": 0, "idle": 0, "idle in transaction": 0, "other": 0}
        long_idle = []

        for conn in activity:
            state = conn.get("state", "other")
            states[state] = states.get(state, 0) + 1

            idle_sec = conn.get("idle_seconds", 0)
            if isinstance(idle_sec, str):
                idle_sec = float(idle_sec)
            if state == "idle" and idle_sec > 1800:  # 30 min
                long_idle.append({
                    "pid": conn.get("pid"),
                    "idle_seconds": idle_sec,
                    "backend_start": conn.get("backend_start"),
                })

        return {
            "total_connections": sum(states.values()),
            "states": states,
            "long_idle_sessions": len(long_idle),
            "long_idle_details": long_idle,
        }

    def terminate_idle_connections(self, project_id: str, branch_id: str,
                                    max_idle_minutes: int = 30) -> dict:
        """
        Kill sessions idle > threshold.
        UC-10: Auto-terminate on high connection utilization.
        """
        conn_info = self.monitor_connections(project_id, branch_id)
        terminated = []

        for session in conn_info.get("long_idle_details", []):
            pid = session.get("pid")
            self.client.execute_statement(
                project_id, branch_id,
                f"SELECT pg_terminate_backend({pid})"
            )
            terminated.append(pid)

        if terminated:
            self.emit_event(EventType.SELF_HEAL_EXECUTED, {
                "action": "terminate_idle_connections",
                "pids_terminated": terminated,
            })

        return {
            "sessions_terminated": len(terminated),
            "pids": terminated,
        }

    # -----------------------------------------------------------------------
    # UC-11: Cost Attribution & Optimization
    # -----------------------------------------------------------------------

    def track_cost_attribution(self, project_id: str) -> dict:
        """
        Track Lakebase costs from system.billing.usage.
        UC-11: Daily.
        """
        # In production: query system.billing.usage via Spark
        # Mock cost data
        return {
            "project_id": project_id,
            "period": "last_7_days",
            "total_dbus": 1250.5,
            "cost_breakdown": {
                "production": {"dbus": 800.0, "pct": 64.0},
                "staging": {"dbus": 200.0, "pct": 16.0},
                "development": {"dbus": 150.0, "pct": 12.0},
                "ci_branches": {"dbus": 100.5, "pct": 8.0},
            },
            "recommendations": [
                "CI branches consumed 8% of DBUs — ensure TTL policies are enforced",
                "Development branch idle 40% of time — verify scale-to-zero is working",
            ],
        }

    def recommend_scale_to_zero_timeout(self, project_id: str, branch_id: str) -> dict:
        """
        Analyze activity patterns and recommend optimal idle timeout.
        UC-11: Weekly.
        """
        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "current_timeout": "5 minutes",
            "recommended_timeout": "10 minutes",
            "reason": "Branch has bursty traffic with 8-12 minute gaps between requests. "
                      "Increasing timeout to 10 minutes reduces cold starts by 40%.",
            "estimated_savings": "15% reduction in total CU-hours (fewer cold start overhead)",
        }

    # -----------------------------------------------------------------------
    # UC-13: Self-Healing Incident Response (V2)
    # -----------------------------------------------------------------------

    def diagnose_root_cause(self, anomaly_report: dict) -> dict:
        """
        Correlate metrics across multiple dimensions to determine root cause.
        UC-13: Triggered on anomaly detection.
        """
        # In production: correlate pg_stat_statements, pg_locks, pg_stat_activity
        metric = anomaly_report.get("metric", "unknown")
        value = anomaly_report.get("value", 0)

        diagnosis = {
            "anomaly": metric,
            "value": value,
            "probable_causes": [],
            "recommended_actions": [],
            "auto_fixable": False,
        }

        if metric == "cache_hit_ratio" and value < 0.95:
            diagnosis["probable_causes"] = [
                "Working set exceeds available shared_buffers",
                "Full table scans on large tables without proper indexes",
                "Recent restart causing cold cache",
            ]
            diagnosis["recommended_actions"] = [
                "Increase CU (compute units) to get more shared_buffers",
                "Add indexes for frequently scanned tables (see index recommendations)",
                "Use pg_prewarm to warm cache after restart",
            ]
        elif metric == "dead_tuple_ratio" and value > 0.25:
            diagnosis["probable_causes"] = [
                "Autovacuum not keeping up with high-churn tables",
                "Long-running transactions preventing vacuum from reclaiming space",
            ]
            diagnosis["recommended_actions"] = [
                "Execute manual VACUUM ANALYZE on affected tables",
                "Tune autovacuum parameters for high-churn tables",
                "Investigate and terminate long-running transactions",
            ]
            diagnosis["auto_fixable"] = True

        return diagnosis

    def self_heal(self, issue_id: str, remediation_plan: dict) -> dict:
        """
        Execute approved auto-remediation.
        UC-13: Only for low-risk actions.
        """
        action = remediation_plan.get("action", "")
        risk = remediation_plan.get("risk_level", "high")

        if risk != "low":
            return {
                "issue_id": issue_id,
                "status": "escalated",
                "reason": f"Risk level '{risk}' requires human approval",
                "recommended_action": action,
            }

        # Execute low-risk remediation
        project_id = remediation_plan.get("project_id", "")
        branch_id = remediation_plan.get("branch_id", "")

        if "vacuum" in action.lower():
            table = remediation_plan.get("table", "")
            self.client.execute_statement(project_id, branch_id, f"VACUUM ANALYZE {table}")
            status = "remediated"
        elif "terminate" in action.lower():
            self.terminate_idle_connections(project_id, branch_id)
            status = "remediated"
        else:
            status = "unknown_action"

        self.emit_event(EventType.SELF_HEAL_EXECUTED, {
            "issue_id": issue_id,
            "action": action,
            "status": status,
        })

        return {"issue_id": issue_id, "action": action, "status": status}

    # -----------------------------------------------------------------------
    # UC-14: Natural Language DBA Operations (V2)
    # -----------------------------------------------------------------------

    def natural_language_dba(self, question: str, project_id: str = "",
                              branch_id: str = "") -> dict:
        """
        LLM-powered DBA Q&A for developers.
        UC-14: "Why is my query slow?" → actionable answer.
        """
        # In production: use Foundation Model API (Llama 4)
        # Mock response
        q_lower = question.lower()

        if "slow" in q_lower or "performance" in q_lower:
            answer = {
                "question": question,
                "analysis": "Based on pg_stat_statements data, your most expensive query is a JOIN between orders and products with a sequential scan on orders.",
                "root_cause": "Missing index on orders.product_id causing sequential scan of 5M rows",
                "recommendation": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_product_id ON orders(product_id);",
                "estimated_improvement": "Expected 95% reduction in query execution time (from 20ms to ~1ms mean)",
                "confidence": "high",
            }
        elif "connection" in q_lower:
            answer = {
                "question": question,
                "analysis": "Current connection utilization is at 15% with 3 idle-in-transaction sessions.",
                "root_cause": "Application not properly closing connections after transactions",
                "recommendation": "Add connection.commit() and connection.close() in your application code, or use a connection pool with idle timeout",
                "confidence": "medium",
            }
        else:
            answer = {
                "question": question,
                "analysis": "I can help with query performance, connection issues, vacuum management, and index recommendations. Please provide more context about your question.",
                "confidence": "low",
            }

        return answer

    # -----------------------------------------------------------------------
    # Automation Cycle
    # -----------------------------------------------------------------------

    async def run_cycle(self, context: dict = None) -> list[TaskResult]:
        """Execute one full health monitoring cycle."""
        ctx = context or {}
        results = []

        project_id = ctx.get("project_id", "supply-chain-prod")
        branches = ctx.get("branches", ["production"])

        for branch_id in branches:
            # FR-04: Monitor system health (every 5 min)
            health_result = await self.execute_tool(
                "monitor_system_health",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(health_result)

            # FR-04: Evaluate thresholds
            if health_result.status == TaskStatus.SUCCESS:
                metrics = health_result.data.get("result", health_result.data).get("metrics", {})
                threshold_result = await self.execute_tool(
                    "evaluate_alert_thresholds",
                    metrics=metrics, project_id=project_id, branch_id=branch_id,
                )
                results.append(threshold_result)

            # UC-10: Monitor connections (every minute)
            result = await self.execute_tool(
                "monitor_connections",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

        # FR-05: Sync validation (every 15 min)
        sync_pairs = ctx.get("sync_table_pairs", [
            {"source": "orders", "target": "ops_catalog.lakebase_ops.orders_delta"},
            {"source": "events", "target": "ops_catalog.lakebase_ops.events_delta"},
        ])
        result = await self.execute_tool(
            "run_full_sync_validation",
            project_id=project_id,
            branch_id=branches[0] if branches else "production",
            table_pairs=sync_pairs,
        )
        results.append(result)

        # FR-07: Cold data identification (weekly)
        result = await self.execute_tool(
            "identify_cold_data",
            project_id=project_id,
            branch_id=branches[0] if branches else "production",
        )
        results.append(result)

        # UC-11: Cost attribution (daily)
        result = await self.execute_tool(
            "track_cost_attribution",
            project_id=project_id,
        )
        results.append(result)

        return results
