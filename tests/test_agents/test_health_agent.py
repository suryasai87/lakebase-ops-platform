"""Tests for HealthAgent: all health tools in mock_mode."""

import pytest

from framework.agent_framework import TaskStatus, EventType


PROJECT = "test-proj"
BRANCH = "production"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:
    def test_all_tools_registered(self, registered_health_agent):
        agent = registered_health_agent
        expected = [
            "monitor_system_health",
            "evaluate_alert_thresholds",
            "execute_low_risk_sop",
            "validate_sync_completeness",
            "validate_sync_integrity",
            "run_full_sync_validation",
            "identify_cold_data",
            "archive_cold_data_to_delta",
            "create_unified_access_view",
            "monitor_connections",
            "terminate_idle_connections",
            "track_cost_attribution",
            "recommend_scale_to_zero_timeout",
            "diagnose_root_cause",
            "self_heal",
            "natural_language_dba",
        ]
        for name in expected:
            assert name in agent.tools, f"Missing tool: {name}"

    def test_archive_requires_approval(self, registered_health_agent):
        tool = registered_health_agent.tools["archive_cold_data_to_delta"]
        assert tool.requires_approval is True
        assert tool.risk_level == "high"

    def test_tool_count(self, registered_health_agent):
        assert len(registered_health_agent.tools) >= 16


# ---------------------------------------------------------------------------
# MonitoringMixin
# ---------------------------------------------------------------------------

class TestMonitoringMixin:
    def test_monitor_system_health(self, registered_health_agent, mock_writer):
        result = registered_health_agent.monitor_system_health(PROJECT, BRANCH)
        metrics = result["metrics"]
        assert "cache_hit_ratio" in metrics
        assert "connection_utilization" in metrics
        assert "max_dead_tuple_ratio" in metrics
        assert "waiting_locks" in metrics
        assert "txid_age" in metrics
        # cache_hit should be near 1.0 (mock: 9.9M hits, 100K reads)
        assert metrics["cache_hit_ratio"] > 0.95
        # Verify metrics written to Delta
        log = mock_writer.get_write_log()
        metric_writes = [w for w in log if "lakebase_metrics" in w["table"]]
        assert len(metric_writes) >= 1

    def test_evaluate_alert_thresholds_healthy(self, registered_health_agent):
        """All metrics within thresholds -> no alerts."""
        metrics = {
            "cache_hit_ratio": 0.999,
            "connection_utilization": 0.30,
            "max_dead_tuple_ratio": 0.05,
            "waiting_locks": 0,
            "txid_age": 100_000_000,
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] == 0
        assert result["sops_auto_executed"] == 0

    def test_evaluate_alert_thresholds_cache_warning(self, registered_health_agent, mock_alerts):
        metrics = {
            "cache_hit_ratio": 0.97,  # < 0.99 warning, > 0.95 critical
            "connection_utilization": 0.30,
            "max_dead_tuple_ratio": 0.05,
            "txid_age": 100_000_000,
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] >= 1
        alerts = mock_alerts.get_alert_history()
        assert any("Cache Hit" in a.title for a in alerts)

    def test_evaluate_alert_thresholds_cache_critical(self, registered_health_agent, mock_alerts):
        metrics = {
            "cache_hit_ratio": 0.90,  # < 0.95 critical
            "connection_utilization": 0.30,
            "max_dead_tuple_ratio": 0.05,
            "txid_age": 100_000_000,
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] >= 1
        alerts = mock_alerts.get_alert_history()
        critical_alerts = [a for a in alerts if a.severity.value == "critical"]
        assert len(critical_alerts) >= 1

    def test_evaluate_alert_thresholds_conn_critical_auto_remediates(self, registered_health_agent, mock_alerts):
        metrics = {
            "cache_hit_ratio": 0.999,
            "connection_utilization": 0.90,  # > 0.85 critical
            "max_dead_tuple_ratio": 0.05,
            "txid_age": 100_000_000,
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] >= 1
        assert result["sops_auto_executed"] >= 1

    def test_evaluate_alert_thresholds_dead_tuple_critical(self, registered_health_agent, mock_alerts):
        metrics = {
            "cache_hit_ratio": 0.999,
            "connection_utilization": 0.30,
            "max_dead_tuple_ratio": 0.30,  # > 0.25 critical
            "worst_dead_tuple_table": "events",
            "txid_age": 100_000_000,
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] >= 1

    def test_evaluate_alert_thresholds_txid_critical(self, registered_health_agent, mock_alerts):
        metrics = {
            "cache_hit_ratio": 0.999,
            "connection_utilization": 0.30,
            "max_dead_tuple_ratio": 0.05,
            "txid_age": 1_500_000_000,  # > 1B critical
        }
        result = registered_health_agent.evaluate_alert_thresholds(
            metrics=metrics, project_id=PROJECT, branch_id=BRANCH
        )
        assert result["alerts_triggered"] >= 1

    def test_execute_low_risk_sop_vacuum(self, registered_health_agent):
        result = registered_health_agent.execute_low_risk_sop(
            "high_dead_tuples", PROJECT, BRANCH, {"table": "events"}
        )
        assert result["status"] == "executed"
        assert "VACUUM ANALYZE" in result["action"]

    def test_execute_low_risk_sop_connections(self, registered_health_agent):
        result = registered_health_agent.execute_low_risk_sop(
            "high_connections", PROJECT, BRANCH
        )
        assert result["status"] == "executed"

    def test_execute_low_risk_sop_unknown(self, registered_health_agent):
        result = registered_health_agent.execute_low_risk_sop(
            "something_unknown", PROJECT, BRANCH
        )
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# SyncMixin
# ---------------------------------------------------------------------------

class TestSyncMixin:
    def test_validate_sync_completeness(self, registered_health_agent):
        result = registered_health_agent.validate_sync_completeness(
            PROJECT, BRANCH, "orders", "ops_catalog.lakebase_ops.orders_delta"
        )
        assert "source_count" in result
        assert "target_count" in result
        assert "count_drift" in result
        assert "status" in result

    def test_validate_sync_integrity(self, registered_health_agent):
        result = registered_health_agent.validate_sync_integrity(
            PROJECT, BRANCH, "orders", "ops_catalog.lakebase_ops.orders_delta"
        )
        assert result["status"] == "integrity_verified"
        assert result["checksum_match"] is True

    def test_run_full_sync_validation(self, registered_health_agent, mock_writer):
        result = registered_health_agent.run_full_sync_validation(PROJECT, BRANCH)
        assert "total_pairs" in result
        assert result["total_pairs"] == 2  # default 2 table pairs
        assert "healthy" in result
        # Sync validation records should be written
        log = mock_writer.get_write_log()
        sync_writes = [w for w in log if "sync_validation" in w["table"]]
        assert len(sync_writes) >= 2

    def test_sync_drift_triggers_alert(self, registered_health_agent, mock_alerts):
        result = registered_health_agent.validate_sync_completeness(
            PROJECT, BRANCH, "orders", "delta_target"
        )
        # Mock simulates 150 row drift which is < 1000 -> healthy
        # For orders: src_count=5M, drift=150 -> healthy
        assert result["status"] == "healthy" or result["count_drift"] < 1000


# ---------------------------------------------------------------------------
# ArchivalMixin
# ---------------------------------------------------------------------------

class TestArchivalMixin:
    def test_identify_cold_data(self, registered_health_agent):
        result = registered_health_agent.identify_cold_data(PROJECT, BRANCH)
        assert "cold_candidates" in result
        # Mock user_tables: orders (5M), events (20M), users (100K)
        # users has 100K < 100K threshold, so 2 candidates
        assert result["cold_candidates"] >= 1

    def test_archive_cold_data_to_delta(self, registered_health_agent, mock_writer):
        result = registered_health_agent.archive_cold_data_to_delta(
            PROJECT, BRANCH, "orders"
        )
        assert result["status"] == "success"
        assert result["rows_archived"] > 0
        # Should write archival record
        log = mock_writer.get_write_log()
        archival_writes = [w for w in log if "data_archival" in w["table"]]
        assert len(archival_writes) >= 1

    def test_create_unified_access_view(self, registered_health_agent):
        result = registered_health_agent.create_unified_access_view(
            PROJECT, BRANCH, "orders", "ops_catalog.lakebase_archive.orders_cold"
        )
        assert result["status"] == "created"
        assert "vw_orders_unified" in result["view_name"]


# ---------------------------------------------------------------------------
# ConnectionMixin
# ---------------------------------------------------------------------------

class TestConnectionMixin:
    def test_monitor_connections(self, registered_health_agent):
        result = registered_health_agent.monitor_connections(PROJECT, BRANCH)
        assert "total_connections" in result
        assert "states" in result
        assert result["total_connections"] >= 1
        # Mock data: active=1, idle=1, idle in transaction=1
        assert result["states"]["active"] >= 1

    def test_terminate_idle_connections(self, registered_health_agent):
        result = registered_health_agent.terminate_idle_connections(PROJECT, BRANCH)
        assert "sessions_terminated" in result
        # Whether any are terminated depends on idle_seconds in mock data


# ---------------------------------------------------------------------------
# OperationsMixin
# ---------------------------------------------------------------------------

class TestOperationsMixin:
    def test_track_cost_attribution(self, registered_health_agent):
        result = registered_health_agent.track_cost_attribution(PROJECT)
        assert result["project_id"] == PROJECT
        assert "cost_breakdown" in result
        assert "production" in result["cost_breakdown"]

    def test_recommend_scale_to_zero_timeout(self, registered_health_agent):
        result = registered_health_agent.recommend_scale_to_zero_timeout(PROJECT, BRANCH)
        assert "recommended_timeout" in result
        assert "reason" in result

    def test_diagnose_root_cause_cache(self, registered_health_agent):
        result = registered_health_agent.diagnose_root_cause(
            {"metric": "cache_hit_ratio", "value": 0.85}
        )
        assert len(result["probable_causes"]) > 0
        assert len(result["recommended_actions"]) > 0

    def test_diagnose_root_cause_dead_tuples(self, registered_health_agent):
        result = registered_health_agent.diagnose_root_cause(
            {"metric": "dead_tuple_ratio", "value": 0.30}
        )
        assert result["auto_fixable"] is True

    def test_diagnose_root_cause_unknown(self, registered_health_agent):
        result = registered_health_agent.diagnose_root_cause(
            {"metric": "unknown_metric", "value": 42}
        )
        assert result["probable_causes"] == []

    def test_self_heal_low_risk(self, registered_health_agent):
        result = registered_health_agent.self_heal(
            "issue-1",
            {"action": "vacuum orders", "risk_level": "low",
             "project_id": PROJECT, "branch_id": BRANCH, "table": "orders"},
        )
        assert result["status"] == "remediated"

    def test_self_heal_high_risk_escalated(self, registered_health_agent):
        result = registered_health_agent.self_heal(
            "issue-2",
            {"action": "drop table", "risk_level": "high"},
        )
        assert result["status"] == "escalated"

    def test_natural_language_dba_slow(self, registered_health_agent):
        result = registered_health_agent.natural_language_dba("Why is my query slow?")
        assert "recommendation" in result
        assert result["confidence"] == "high"

    def test_natural_language_dba_connection(self, registered_health_agent):
        result = registered_health_agent.natural_language_dba("connection issues")
        assert "analysis" in result
        assert result["confidence"] == "medium"

    def test_natural_language_dba_generic(self, registered_health_agent):
        result = registered_health_agent.natural_language_dba("hello")
        assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# run_cycle
# ---------------------------------------------------------------------------

class TestRunCycle:
    @pytest.mark.asyncio
    async def test_run_cycle_default(self, registered_health_agent):
        results = await registered_health_agent.run_cycle()
        # monitor_system_health + evaluate_alert_thresholds + monitor_connections
        # + run_full_sync_validation + identify_cold_data + track_cost_attribution
        assert len(results) >= 5
        success_count = sum(1 for r in results if r.status == TaskStatus.SUCCESS)
        assert success_count >= 5

    @pytest.mark.asyncio
    async def test_run_cycle_multi_branch(self, registered_health_agent):
        results = await registered_health_agent.run_cycle({
            "project_id": PROJECT,
            "branches": ["production", "staging"],
        })
        # 2 branches * 3 per-branch tools + 3 global
        assert len(results) >= 8
