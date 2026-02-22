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

from framework.agent_framework import BaseAgent, TaskStatus
from config.settings import AlertThresholds

from .monitoring import MonitoringMixin
from .sync import SyncMixin
from .archival import ArchivalMixin
from .connections import ConnectionMixin
from .operations import OperationsMixin

logger = logging.getLogger("lakebase_ops.health")


class HealthAgent(MonitoringMixin, SyncMixin, ArchivalMixin, ConnectionMixin, OperationsMixin, BaseAgent):
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
    # Automation Cycle
    # -----------------------------------------------------------------------

    async def run_cycle(self, context: dict = None) -> list:
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
