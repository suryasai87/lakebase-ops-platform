"""Shared fixtures for LakebaseOps test suite.

Provides mock instances of LakebaseClient, DeltaWriter, and AlertManager
that all agent and utility tests can reuse. Every fixture uses mock_mode=True
so no real Databricks or Lakebase connections are attempted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that "from framework..." etc. work.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import AlertThresholds  # noqa: E402
from framework.agent_framework import AgentFramework  # noqa: E402
from utils.alerting import AlertManager  # noqa: E402
from utils.delta_writer import DeltaWriter  # noqa: E402
from utils.lakebase_client import LakebaseClient  # noqa: E402

# ---------------------------------------------------------------------------
# Core mock objects
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """LakebaseClient in mock mode -- no real PG connections."""
    return LakebaseClient(workspace_host="test-host", mock_mode=True)


@pytest.fixture
def mock_writer():
    """DeltaWriter in mock mode -- logs writes but does not execute."""
    return DeltaWriter(mock_mode=True)


@pytest.fixture
def mock_alerts():
    """AlertManager in mock mode -- records alerts without sending."""
    return AlertManager(mock_mode=True)


@pytest.fixture
def alert_thresholds():
    """Default AlertThresholds from settings."""
    return AlertThresholds()


# ---------------------------------------------------------------------------
# Agent framework fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def framework():
    """AgentFramework in mock mode."""
    return AgentFramework(workspace_host="test-host", mock_mode=True)


# ---------------------------------------------------------------------------
# Concrete agent fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provisioning_agent(mock_client, mock_writer, mock_alerts):
    from agents.provisioning.agent import ProvisioningAgent

    return ProvisioningAgent(mock_client, mock_writer, mock_alerts)


@pytest.fixture
def performance_agent(mock_client, mock_writer, mock_alerts):
    from agents.performance.agent import PerformanceAgent

    return PerformanceAgent(mock_client, mock_writer, mock_alerts)


@pytest.fixture
def health_agent(mock_client, mock_writer, mock_alerts):
    from agents.health.agent import HealthAgent

    return HealthAgent(mock_client, mock_writer, mock_alerts)


# ---------------------------------------------------------------------------
# Helper: registered agent (tools available)
# ---------------------------------------------------------------------------


@pytest.fixture
def registered_provisioning_agent(provisioning_agent, framework):
    framework.register_agent(provisioning_agent)
    return provisioning_agent


@pytest.fixture
def registered_performance_agent(performance_agent, framework):
    framework.register_agent(performance_agent)
    return performance_agent


@pytest.fixture
def registered_health_agent(health_agent, framework):
    framework.register_agent(health_agent)
    return health_agent
