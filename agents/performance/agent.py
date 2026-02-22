"""
Performance & Optimization Agent

Automates "Day 1+" performance tasks:
- FR-01: pg_stat_statements persistence (5-min collection, 90-day retention)
- FR-02: Automated index health management (unused, bloated, missing, duplicate)
- FR-03: VACUUM/ANALYZE scheduling (replacing pg_cron)
- UC-09: Autovacuum parameter tuning
- UC-12: AI-powered query optimization (V2)
- UC-15: Capacity planning forecasting (V2)
"""

from __future__ import annotations

import logging

from framework.agent_framework import BaseAgent, EventType, TaskResult, TaskStatus
from config.settings import AlertThresholds

from .metrics import MetricsMixin
from .indexes import IndexMixin
from .maintenance import MaintenanceMixin
from .optimization import OptimizationMixin

logger = logging.getLogger("lakebase_ops.performance")


class PerformanceAgent(MetricsMixin, IndexMixin, MaintenanceMixin, OptimizationMixin, BaseAgent):
    """
    Performance & Optimization Agent — continuous performance monitoring and tuning.

    Implements PRD FR-01, FR-02, FR-03, UC-09, UC-12, UC-15.
    """

    def __init__(self, lakebase_client, delta_writer, alert_manager):
        super().__init__(
            name="PerformanceAgent",
            description="Proactively analyzes query patterns, indexing, and runtime configs; persists metrics to Delta for 90-day historical analysis and cross-branch comparison",
        )
        self.client = lakebase_client
        self.writer = delta_writer
        self.alerts = alert_manager
        self.thresholds = AlertThresholds()

    def register_tools(self) -> None:
        """Register all performance monitoring and optimization tools."""

        # FR-01: pg_stat_statements persistence
        self.register_tool("persist_pg_stat_statements", self.persist_pg_stat_statements,
                           "Capture pg_stat_statements to Delta (every 5 min)", schedule="*/5 * * * *")

        # FR-02: Index health management
        self.register_tool("detect_unused_indexes", self.detect_unused_indexes,
                           "Find indexes with idx_scan=0 for 7+ days", schedule="0 * * * *")
        self.register_tool("detect_bloated_indexes", self.detect_bloated_indexes,
                           "Find indexes with bloat ratio > 2.0x", schedule="0 * * * *")
        self.register_tool("detect_missing_indexes", self.detect_missing_indexes,
                           "Find tables with seq_scan >> idx_scan", schedule="0 * * * *")
        self.register_tool("detect_duplicate_indexes", self.detect_duplicate_indexes,
                           "Find overlapping column sets", schedule="0 * * * *")
        self.register_tool("detect_missing_fk_indexes", self.detect_missing_fk_indexes,
                           "Find unindexed foreign keys", schedule="0 * * * *")
        self.register_tool("run_full_index_analysis", self.run_full_index_analysis,
                           "Complete index health analysis (all checks)", schedule="0 * * * *")

        # FR-03: VACUUM/ANALYZE
        self.register_tool("identify_tables_needing_vacuum", self.identify_tables_needing_vacuum,
                           "Find tables with high dead tuple ratio", schedule="0 2 * * *")
        self.register_tool("schedule_vacuum_analyze", self.schedule_vacuum_analyze,
                           "Execute VACUUM ANALYZE on identified tables", schedule="0 2 * * *")
        self.register_tool("schedule_vacuum_full", self.schedule_vacuum_full,
                           "Execute VACUUM FULL on heavily bloated tables",
                           risk_level="high", requires_approval=True)
        self.register_tool("check_txid_wraparound_risk", self.check_txid_wraparound_risk,
                           "Alert on transaction ID wraparound risk", schedule="*/5 * * * *")

        # UC-09: Autovacuum tuning
        self.register_tool("tune_autovacuum_parameters", self.tune_autovacuum_parameters,
                           "Dynamically adjust per-table autovacuum thresholds", schedule="0 3 * * *")

        # UC-12: AI query optimization (V2)
        self.register_tool("analyze_slow_queries_with_ai", self.analyze_slow_queries_with_ai,
                           "LLM-powered slow query analysis and rewrite suggestions")

        # UC-15: Capacity planning (V2)
        self.register_tool("forecast_capacity_needs", self.forecast_capacity_needs,
                           "ML-based prediction of storage and compute needs", schedule="0 4 * * 0")

    async def run_cycle(self, context: dict = None) -> list[TaskResult]:
        """Execute one full performance monitoring cycle."""
        ctx = context or {}
        results = []

        project_id = ctx.get("project_id", "supply-chain-prod")
        branches = ctx.get("branches", ["production"])

        for branch_id in branches:
            result = await self.execute_tool(
                "persist_pg_stat_statements",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

            result = await self.execute_tool(
                "run_full_index_analysis",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

            result = await self.execute_tool(
                "identify_tables_needing_vacuum",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

            result = await self.execute_tool(
                "schedule_vacuum_analyze",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

            result = await self.execute_tool(
                "check_txid_wraparound_risk",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

            result = await self.execute_tool(
                "tune_autovacuum_parameters",
                project_id=project_id, branch_id=branch_id,
            )
            results.append(result)

        result = await self.execute_tool(
            "analyze_slow_queries_with_ai",
            project_id=project_id, branch_id=branches[0] if branches else "production",
        )
        results.append(result)

        result = await self.execute_tool(
            "forecast_capacity_needs",
            project_id=project_id,
        )
        results.append(result)

        return results
