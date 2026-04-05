"""Shared fixtures for LakebaseOps test suite.

Provides mock instances of LakebaseClient, DeltaWriter, and AlertManager
that all agent and utility tests can reuse. Every fixture uses mock_mode=True
so no real Databricks or Lakebase connections are attempted.
"""

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that "from framework..." etc. work.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Patch config/settings.py if AlertSeverity was removed from it
# (GAP-014: duplicate enum was deleted but config/__init__.py still references it).
# We must inject the symbol BEFORE config package __init__.py is loaded.
import importlib
import importlib.util
import importlib.machinery
import types

# Load config.settings DIRECTLY (bypassing config/__init__.py) using file path.
_settings_path = str(Path(__file__).resolve().parent.parent / "config" / "settings.py")
_spec = importlib.util.spec_from_file_location("config.settings", _settings_path)
_settings_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_settings_mod)

if not hasattr(_settings_mod, "AlertSeverity"):
    from enum import Enum

    class _AlertSeverityShim(Enum):
        INFO = "info"
        WARNING = "warning"
        CRITICAL = "critical"

    _settings_mod.AlertSeverity = _AlertSeverityShim

# Register in sys.modules BEFORE config/__init__.py tries to import it.
sys.modules["config.settings"] = _settings_mod
# Also register the config package as a namespace so subsequent imports work.
if "config" not in sys.modules:
    _config_pkg = types.ModuleType("config")
    _config_pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "config")]
    _config_pkg.__package__ = "config"
    sys.modules["config"] = _config_pkg

# Now safe to import everything else.
from utils.lakebase_client import LakebaseClient
from utils.delta_writer import DeltaWriter
from utils.alerting import AlertManager, Alert, AlertSeverity, AlertChannel
from framework.agent_framework import (
    AgentFramework,
    BaseAgent,
    TaskResult,
    TaskStatus,
    EventType,
    Event,
)
from config.settings import AlertThresholds


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
    agent = ProvisioningAgent(mock_client, mock_writer, mock_alerts)
    return agent


@pytest.fixture
def performance_agent(mock_client, mock_writer, mock_alerts):
    from agents.performance.agent import PerformanceAgent
    agent = PerformanceAgent(mock_client, mock_writer, mock_alerts)
    return agent


@pytest.fixture
def health_agent(mock_client, mock_writer, mock_alerts):
    from agents.health.agent import HealthAgent
    agent = HealthAgent(mock_client, mock_writer, mock_alerts)
    return agent


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
