"""Backend router unit tests using FastAPI TestClient."""

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.backend.main import app

client = TestClient(app, raise_server_exceptions=False)

# Auth headers required by DatabricksProxyAuthMiddleware for non-health endpoints
_AUTH_HEADERS = {
    "X-Forwarded-User": "test-user",
    "X-Forwarded-Email": "test@databricks.com",
}


def _get(path, **kwargs):
    """GET with proxy auth headers."""
    headers = {**_AUTH_HEADERS, **kwargs.pop("headers", {})}
    return client.get(path, headers=headers, **kwargs)


def _post(path, **kwargs):
    """POST with proxy auth headers."""
    headers = {**_AUTH_HEADERS, **kwargs.pop("headers", {})}
    return client.post(path, headers=headers, **kwargs)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    @patch("app.backend.routers.health.execute_query")
    def test_health_ok(self, mock_exec):
        mock_exec.return_value = [{"ok": "1"}]
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @patch("app.backend.routers.health.execute_query")
    def test_health_degraded(self, mock_exec):
        mock_exec.return_value = []
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    @patch("app.backend.routers.health.execute_query")
    def test_health_exception(self, mock_exec):
        mock_exec.side_effect = Exception("connection refused")
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    @patch("app.backend.routers.metrics.get_cached")
    def test_overview(self, mock_cached):
        mock_cached.return_value = [
            {
                "project_id": "proj1",
                "branch_id": "production",
                "metric_name": "cache_hit_ratio",
                "metric_value": "0.99",
                "threshold_level": "normal",
                "snapshot_timestamp": "2026-03-01T00:00:00",
            }
        ]
        resp = _get("/api/metrics/overview")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @patch("app.backend.routers.metrics.get_cached")
    def test_trends_valid_metric(self, mock_cached):
        mock_cached.return_value = [
            {
                "metric_name": "cache_hit_ratio",
                "hour": "2026-03-01T00:00:00",
                "avg_value": "0.99",
                "min_value": "0.98",
                "max_value": "1.00",
            }
        ]
        resp = _get("/api/metrics/trends?metric=cache_hit_ratio&hours=24")
        assert resp.status_code == 200

    def test_trends_invalid_metric_returns_400(self):
        resp = _get("/api/metrics/trends?metric=DROP TABLE users")
        assert resp.status_code == 400
        body = resp.json()
        assert "Invalid metric" in body["detail"]

    def test_trends_sql_injection_blocked(self):
        resp = _get("/api/metrics/trends?metric=x' OR '1'='1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class TestAssessment:
    @patch("app.backend.routers.assessment._get_agent")
    def test_discover_mock(self, mock_agent_fn):
        agent = MagicMock()
        agent.connect_and_discover.return_value = {
            "profile_id": "test-123",
            "database_size_gb": 10.5,
            "table_count": 15,
            "_assessment": {"internal": True},
            "source_password": "secret",
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/discover", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert "profile_id" in body
        assert "source_password" not in body
        assert "_assessment" not in body

    @patch("app.backend.routers.assessment._get_agent")
    def test_profile_mock(self, mock_agent_fn):
        agent = MagicMock()
        agent.profile_workload.return_value = {
            "avg_qps": 2800,
            "avg_tps": 780,
            "connection_count_avg": 45,
            "connection_count_peak": 120,
            "reads_pct": 72,
            "writes_pct": 28,
            "p99_latency_ms": 45,
            "top_queries_count": 20,
            "hot_tables_count": 5,
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/profile", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["qps"] == 2800
        assert body["read_write_ratio"] == "72/28"

    @patch("app.backend.routers.assessment._get_agent")
    def test_readiness_mock(self, mock_agent_fn):
        agent = MagicMock()
        agent.assess_readiness.return_value = {
            "overall_score": 92,
            "category": "ready",
            "blocker_count": 0,
            "warning_count": 2,
            "dimensions": {
                "storage": {"score": 95, "status": "pass"},
                "compute": {"score": 90, "status": "pass"},
            },
            "blockers": [],
            "unsupported_extensions": ["pg_cron"],
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/readiness", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_score"] == 92
        assert body["dimension_scores"]["storage"] == 95

    @patch("app.backend.routers.assessment._get_agent")
    def test_blueprint_mock(self, mock_agent_fn):
        agent = MagicMock()
        agent.generate_migration_blueprint.return_value = {
            "strategy": "hybrid",
            "total_estimated_days": 16.5,
            "risk_level": "medium",
            "phases": [
                {"name": "Prep", "days": 3, "description": "Setup", "steps": ["step1"]},
            ],
            "prerequisite_count": 4,
            "report_markdown": "# Blueprint\n...",
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/blueprint", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["strategy"] == "hybrid"
        assert body["total_effort_days"] == 16.5
        assert body["markdown"].startswith("# Blueprint")
        assert body["phases"][0]["duration_days"] == 3


# ---------------------------------------------------------------------------
# Profile cache
# ---------------------------------------------------------------------------


class TestProfileCache:
    def test_cache_set_strips_sensitive(self):
        from app.backend.routers.assessment import _ProfileCache

        cache = _ProfileCache(ttl=60)
        cache.set("p1", {"name": "test", "source_password": "secret", "_token": "abc"})
        data = cache.get("p1")
        assert "name" in data
        assert "source_password" not in data
        assert "_token" not in data

    def test_cache_ttl_expiry(self):
        from app.backend.routers.assessment import _ProfileCache

        cache = _ProfileCache(ttl=1)
        cache.set("p1", {"name": "test"})
        assert cache.get("p1") == {"name": "test"}
        time.sleep(1.1)
        assert cache.get("p1") == {}

    def test_cache_eviction(self):
        from app.backend.routers.assessment import _ProfileCache

        cache = _ProfileCache(ttl=1)
        cache.set("p1", {"a": 1})
        cache.set("p2", {"b": 2})
        time.sleep(1.1)
        cache.set("p3", {"c": 3})
        assert cache.get("p1") == {}
        assert cache.get("p2") == {}
        assert cache.get("p3") == {"c": 3}


# ---------------------------------------------------------------------------
# Assessment: CosmosDB cost-estimate, extension-matrix, warnings
# ---------------------------------------------------------------------------


class TestAssessmentCosmosDB:
    def _seed_cosmosdb_profile(self):
        """Insert a mock CosmosDB profile into the assessment cache for testing."""
        from app.backend.routers.assessment import _profiles
        from config.migration_profiles import (
            DatabaseProfile,
            MigrationProfile,
            SourceEngine,
            WorkloadProfile,
        )

        db = DatabaseProfile(
            name="cosmos-test-db",
            size_bytes=50_000_000_000,
            size_gb=46.6,
            table_count=8,
            schema_count=1,
            schemas=["default"],
            extensions=[],
            functions=[],
            triggers=[],
            cosmos_throughput_mode="provisioned",
            cosmos_ru_per_sec=4000,
            cosmos_partition_key_paths=["/userId", "/orderId"],
            cosmos_consistency_level="Session",
            cosmos_change_feed_enabled=False,
            cosmos_change_feed_mode="LatestVersion",
            cosmos_multi_region_writes=True,
            cosmos_regions=["eastus", "westeurope"],
            cosmos_container_details=[
                {"name": "Users", "partition_key": "/userId", "ru_per_sec": 2000},
                {"name": "Orders", "partition_key": "/orderId", "ru_per_sec": 2000},
            ],
            cosmos_autoscale_max_ru=None,
            cosmos_backup_policy="periodic",
        )
        profile = MigrationProfile(
            profile_id="cosmos-test-001",
            source_engine=SourceEngine.COSMOSDB_NOSQL,
            source_endpoint="myaccount.documents.azure.com",
            source_version="CosmosDB",
            source_region="eastus",
            databases=[db],
            workload=WorkloadProfile(
                avg_qps=2800, avg_tps=700, connection_count_avg=60, connection_count_peak=200,
                workload_source="mock",
            ),
        )
        _profiles.set("cosmos-test-001", {"_profile": profile})
        return "cosmos-test-001"

    def test_cost_estimate_cosmosdb(self):
        pid = self._seed_cosmosdb_profile()
        resp = _get(f"/api/assessment/cost-estimate/{pid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["engine"] == "cosmosdb-nosql"
        assert body["source"]["total"] > 0
        assert body["lakebase"]["total"] > 0
        assert "pricing_source" in body
        assert body.get("tier") == "premium"
        assert body.get("tier_label") == "Premium"
        assert body["lakebase"]["rates"]["dbu_rate"] == 0.46
        assert body["lakebase"]["pricing_source"] == "static"
        assert "pricing_version" in body["lakebase"]
        assert body.get("workload_source") == "mock"
        assert "workload_caveat" in body
        detail = body.get("cosmos_cost_detail")
        assert detail is not None
        assert detail["multi_region_writes"] is True
        assert detail["num_regions"] == 2
        assert detail["region_multiplier"] == 2

    def test_cost_estimate_enterprise_tier(self):
        pid = self._seed_cosmosdb_profile()
        resp = _get(f"/api/assessment/cost-estimate/{pid}?tier=enterprise")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tier"] == "enterprise"
        assert body["tier_label"] == "Enterprise"
        assert body["lakebase"]["rates"]["dbu_rate"] == 0.60
        assert "sku_name" in body

    def test_extension_matrix_cosmosdb(self):
        pid = self._seed_cosmosdb_profile()
        resp = _get(f"/api/assessment/extension-matrix/{pid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["matrix_type"] == "feature"
        names = [e["name"] for e in body["extensions"]]
        assert "Partition keys" in names or "Change Feed" in names
        assert body["summary"]["supported"] > 0

    @patch("app.backend.routers.assessment._get_agent")
    def test_readiness_returns_warnings(self, mock_agent_fn):
        agent = MagicMock()
        agent.assess_readiness.return_value = {
            "overall_score": 65,
            "category": "ready_with_workarounds",
            "blocker_count": 1,
            "warning_count": 3,
            "dimensions": {},
            "blockers": [],
            "supported_extensions": [],
            "unsupported_extensions": ["Integrated cache"],
            "warnings": [
                "Provisioned throughput mode requires capacity planning for Lakebase CU sizing",
                "'Integrated cache' requires workaround: Use application-level caching",
                "Cosmos DB consistency level 'Strong' has no direct Lakebase equivalent",
            ],
            "sizing_by_env": [],
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/readiness", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["warnings"]) == 3
        assert any("capacity planning" in w for w in body["warnings"])
        assert any("Lakebase equivalent" in w for w in body["warnings"])
        assert "sizing_by_env" in body

    @patch("app.backend.routers.assessment._get_agent")
    def test_readiness_returns_sizing_by_env(self, mock_agent_fn):
        agent = MagicMock()
        agent.assess_readiness.return_value = {
            "overall_score": 85,
            "category": "ready",
            "blocker_count": 0,
            "warning_count": 0,
            "dimensions": {},
            "blockers": [],
            "supported_extensions": [],
            "unsupported_extensions": [],
            "warnings": [],
            "sizing_by_env": [
                {"env": "dev", "cu_min": 0.5, "cu_max": 2, "scale_to_zero": True, "autoscaling": True, "max_connections": 419, "ram_gb": 4, "notes": "Dev env"},
                {"env": "staging", "cu_min": 2, "cu_max": 4, "scale_to_zero": True, "autoscaling": True, "max_connections": 839, "ram_gb": 8, "notes": "Staging env"},
                {"env": "prod", "cu_min": 2, "cu_max": 8, "scale_to_zero": False, "autoscaling": True, "max_connections": 1678, "ram_gb": 16, "notes": "Prod env"},
            ],
        }
        mock_agent_fn.return_value = agent
        resp = _post("/api/assessment/readiness", json={"mock": True})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sizing_by_env"]) == 3
        envs = [e["env"] for e in body["sizing_by_env"]]
        assert envs == ["dev", "staging", "prod"]
        prod = body["sizing_by_env"][2]
        assert prod["scale_to_zero"] is False
        assert prod["max_connections"] == 1678


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


class TestGlobalErrorHandler:
    def test_404_on_unknown_api_route(self):
        resp = _get("/api/nonexistent")
        assert resp.status_code in (404, 200)


# ---------------------------------------------------------------------------
# Performance (GAP-022)
# ---------------------------------------------------------------------------


class TestPerformance:
    @patch("app.backend.routers.performance.get_cached")
    def test_slow_queries(self, mock_cached):
        mock_cached.return_value = [
            {
                "query": "SELECT 1",
                "queryid": "1",
                "total_calls": "100",
                "avg_exec_time_ms": "5.50",
                "total_time_ms": "550.00",
                "total_rows": "1000",
                "total_read_mb": "1.20",
                "last_seen": "2026-03-01",
            }
        ]
        resp = _get("/api/performance/queries?hours=24&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    @patch("app.backend.routers.performance.get_cached")
    def test_slow_queries_default_params(self, mock_cached):
        mock_cached.return_value = []
        resp = _get("/api/performance/queries")
        assert resp.status_code == 200

    @patch("app.backend.routers.performance.get_cached")
    def test_slow_queries_invalid_hours(self, mock_cached):
        """hours parameter has ge=1 le=168 validation."""
        resp = _get("/api/performance/queries?hours=0")
        assert resp.status_code == 422

    @patch("app.backend.routers.performance.get_cached")
    def test_regressions(self, mock_cached):
        mock_cached.return_value = [
            {"queryid": "1", "baseline_ms": "2.00", "recent_ms": "5.00", "pct_change": "150.0", "status": "REGRESSION"}
        ]
        resp = _get("/api/performance/regressions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @patch("app.backend.routers.performance.get_cached")
    def test_regressions_empty(self, mock_cached):
        mock_cached.return_value = []
        resp = _get("/api/performance/regressions")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Indexes (GAP-022)
# ---------------------------------------------------------------------------


class TestIndexes:
    @patch("app.backend.routers.indexes.get_cached")
    def test_recommendations(self, mock_cached):
        mock_cached.return_value = [
            {
                "recommendation_type": "drop_unused",
                "confidence": "high",
                "count": "5",
                "pending_review": "3",
                "approved": "1",
                "executed": "1",
                "rejected": "0",
            }
        ]
        resp = _get("/api/indexes/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["recommendation_type"] == "drop_unused"

    @patch("app.backend.routers.indexes.get_cached")
    def test_recommendations_empty(self, mock_cached):
        mock_cached.return_value = []
        resp = _get("/api/indexes/recommendations")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Operations (GAP-022)
# ---------------------------------------------------------------------------


class TestOperations:
    @patch("app.backend.routers.operations.get_cached")
    def test_vacuum_history(self, mock_cached):
        mock_cached.return_value = [
            {
                "vacuum_date": "2026-03-01",
                "operation_type": "VACUUM ANALYZE",
                "operations": "10",
                "successful": "9",
                "failed": "1",
                "avg_duration_s": "2.5",
            }
        ]
        resp = _get("/api/operations/vacuum?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @patch("app.backend.routers.operations.get_cached")
    def test_vacuum_history_default_days(self, mock_cached):
        mock_cached.return_value = []
        resp = _get("/api/operations/vacuum")
        assert resp.status_code == 200

    @patch("app.backend.routers.operations.get_cached")
    def test_vacuum_invalid_days(self, mock_cached):
        resp = _get("/api/operations/vacuum?days=0")
        assert resp.status_code == 422

    @patch("app.backend.routers.operations.get_cached")
    def test_sync_status(self, mock_cached):
        mock_cached.return_value = [
            {
                "source_table": "orders",
                "target_table": "orders_delta",
                "source_count": "5000000",
                "target_count": "4999850",
                "count_drift": "150",
                "lag_minutes": "15.0",
                "checksum_match": "true",
                "status": "healthy",
                "validated_at": "2026-03-01T12:00:00",
            }
        ]
        resp = _get("/api/operations/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @patch("app.backend.routers.operations.get_cached")
    def test_branch_activity(self, mock_cached):
        mock_cached.return_value = [
            {"event_date": "2026-03-01", "event_type": "created", "events": "5", "unique_branches": "3"}
        ]
        resp = _get("/api/operations/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @patch("app.backend.routers.operations.get_cached")
    def test_archival_summary(self, mock_cached):
        mock_cached.return_value = [
            {
                "archive_date": "2026-03-01",
                "source_table": "orders",
                "total_rows_archived": "50000",
                "total_bytes_reclaimed": "25000000",
                "mb_reclaimed": "23.84",
                "operations": "1",
            }
        ]
        resp = _get("/api/operations/archival")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Lakebase (GAP-022)
# ---------------------------------------------------------------------------


class TestLakebase:
    @patch("app.backend.routers.lakebase.get_realtime_stats")
    def test_realtime_stats(self, mock_stats):
        mock_stats.return_value = {
            "timestamp": 1709300000.0,
            "connections": 15,
            "cache_hit_ratio": 0.9988,
            "deadlocks": 1,
            "connection_states": {"active": 3, "idle": 10},
        }
        resp = _get("/api/lakebase/realtime")
        assert resp.status_code == 200
        data = resp.json()
        assert "connections" in data
        assert data["cache_hit_ratio"] > 0

    @patch("app.backend.routers.lakebase.get_realtime_stats")
    def test_realtime_stats_error(self, mock_stats):
        mock_stats.return_value = {"error": "No Lakebase credential available"}
        resp = _get("/api/lakebase/realtime")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---------------------------------------------------------------------------
# Jobs (GAP-022)
# ---------------------------------------------------------------------------


class TestJobs:
    @patch("app.backend.routers.jobs.get_client")
    def test_list_jobs_no_client(self, mock_get_client):
        mock_get_client.side_effect = Exception("no auth")
        resp = _get("/api/jobs/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body

    @patch("app.backend.routers.jobs.get_client")
    def test_list_jobs_success(self, mock_get_client):
        mock_client_obj = MagicMock()
        mock_client_obj.jobs.get.side_effect = Exception("not found")
        mock_get_client.return_value = mock_client_obj
        resp = _get("/api/jobs/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body
        # All jobs should show as not_found since mock raises
        for job in body["jobs"]:
            assert job["status"] == "not_found"

    @patch("app.backend.routers.jobs.get_client")
    def test_trigger_sync_no_client(self, mock_get_client):
        mock_get_client.side_effect = Exception("no auth")
        resp = _post("/api/jobs/sync")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"

    @patch("app.backend.routers.jobs.get_client")
    def test_trigger_sync_partial_success(self, mock_get_client):
        mock_run = MagicMock()
        mock_run.run_id = 12345
        mock_client_obj = MagicMock()
        mock_client_obj.jobs.run_now.return_value = mock_run
        mock_get_client.return_value = mock_client_obj
        resp = _post("/api/jobs/sync")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "triggered"
        assert body["triggered_count"] == len(body["triggered"])

    def test_poll_sync_status_no_ids(self):
        resp = _get("/api/jobs/sync/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall"] == "no_runs"

    def test_poll_sync_status_empty_string(self):
        resp = _get("/api/jobs/sync/status?run_ids=")
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall"] == "no_runs"
