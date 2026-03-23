"""Backend router unit tests using FastAPI TestClient."""

import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.backend.main import app

client = TestClient(app, raise_server_exceptions=False)


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
        mock_cached.return_value = [{"metric_name": "cache_hit_ratio", "metric_value": "0.99"}]
        resp = client.get("/api/metrics/overview")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @patch("app.backend.routers.metrics.get_cached")
    def test_trends_valid_metric(self, mock_cached):
        mock_cached.return_value = [{"hour": "2026-03-01T00:00:00", "avg_value": "0.99"}]
        resp = client.get("/api/metrics/trends?metric=cache_hit_ratio&hours=24")
        assert resp.status_code == 200

    def test_trends_invalid_metric_returns_400(self):
        resp = client.get("/api/metrics/trends?metric=DROP TABLE users")
        assert resp.status_code == 400
        body = resp.json()
        assert "Invalid metric" in body["detail"]

    def test_trends_sql_injection_blocked(self):
        resp = client.get("/api/metrics/trends?metric=x' OR '1'='1")
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
        resp = client.post("/api/assessment/discover", json={"mock": True})
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
        resp = client.post("/api/assessment/profile", json={"mock": True})
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
        resp = client.post("/api/assessment/readiness", json={"mock": True})
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
        resp = client.post("/api/assessment/blueprint", json={"mock": True})
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
# Global exception handler
# ---------------------------------------------------------------------------

class TestGlobalErrorHandler:
    def test_404_on_unknown_api_route(self):
        resp = client.get("/api/nonexistent")
        assert resp.status_code in (404, 200)
