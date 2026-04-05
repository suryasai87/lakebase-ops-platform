"""Tests for AlertManager: routing, severity filtering, channel dispatch, DBSQL definitions."""

import pytest

from utils.alerting import Alert, AlertManager, AlertSeverity, AlertChannel


# ---------------------------------------------------------------------------
# Alert dataclass
# ---------------------------------------------------------------------------

class TestAlertDataclass:
    def test_alert_creation(self):
        alert = Alert(
            alert_id="test-001",
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Something happened",
            source_agent="TestAgent",
        )
        assert alert.alert_id == "test-001"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.channels_sent == []

    def test_alert_to_dict(self):
        alert = Alert(
            alert_id="test-002",
            severity=AlertSeverity.CRITICAL,
            title="Critical Issue",
            message="Fix immediately",
            source_agent="HealthAgent",
            metric_name="cache_hit_ratio",
            metric_value=0.85,
            threshold=0.95,
            project_id="proj-1",
            branch_id="production",
        )
        d = alert.to_dict()
        assert d["alert_id"] == "test-002"
        assert d["severity"] == "critical"
        assert d["metric_value"] == 0.85
        assert d["project_id"] == "proj-1"
        assert "timestamp" in d

    def test_alert_default_fields(self):
        alert = Alert(
            alert_id="x", severity=AlertSeverity.INFO,
            title="t", message="m", source_agent="a",
        )
        assert alert.metric_name == ""
        assert alert.metric_value == 0.0
        assert alert.auto_remediated is False
        assert alert.sop_action == ""


# ---------------------------------------------------------------------------
# AlertSeverity enum
# ---------------------------------------------------------------------------

class TestAlertSeverity:
    def test_enum_values(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"


# ---------------------------------------------------------------------------
# AlertChannel enum
# ---------------------------------------------------------------------------

class TestAlertChannel:
    def test_channel_values(self):
        assert AlertChannel.SLACK.value == "slack"
        assert AlertChannel.PAGERDUTY.value == "pagerduty"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.DBSQL.value == "dbsql"
        assert AlertChannel.LOG.value == "log"


# ---------------------------------------------------------------------------
# AlertManager routing
# ---------------------------------------------------------------------------

class TestAlertRouting:
    def test_info_routes_to_log_only(self, mock_alerts):
        channels = mock_alerts._get_channels_for_severity(AlertSeverity.INFO)
        assert channels == [AlertChannel.LOG]

    def test_warning_routes_to_slack_and_log(self, mock_alerts):
        channels = mock_alerts._get_channels_for_severity(AlertSeverity.WARNING)
        assert AlertChannel.SLACK in channels
        assert AlertChannel.LOG in channels
        assert AlertChannel.PAGERDUTY not in channels

    def test_critical_routes_to_slack_pagerduty_log(self, mock_alerts):
        channels = mock_alerts._get_channels_for_severity(AlertSeverity.CRITICAL)
        assert AlertChannel.SLACK in channels
        assert AlertChannel.PAGERDUTY in channels
        assert AlertChannel.LOG in channels


# ---------------------------------------------------------------------------
# Sending alerts
# ---------------------------------------------------------------------------

class TestSendAlert:
    def test_send_info_alert(self, mock_alerts):
        alert = Alert(
            alert_id="a1", severity=AlertSeverity.INFO,
            title="Info", message="FYI", source_agent="test",
        )
        returned = mock_alerts.send_alert(alert)
        assert returned is alert
        assert "log" in alert.channels_sent
        assert "slack" not in alert.channels_sent

    def test_send_warning_alert(self, mock_alerts):
        alert = Alert(
            alert_id="a2", severity=AlertSeverity.WARNING,
            title="Warning", message="Watch out", source_agent="test",
        )
        mock_alerts.send_alert(alert)
        assert "slack" in alert.channels_sent
        assert "log" in alert.channels_sent

    def test_send_critical_alert(self, mock_alerts):
        alert = Alert(
            alert_id="a3", severity=AlertSeverity.CRITICAL,
            title="Critical", message="Act now", source_agent="test",
        )
        mock_alerts.send_alert(alert)
        assert "slack" in alert.channels_sent
        assert "pagerduty" in alert.channels_sent
        assert "log" in alert.channels_sent

    def test_alert_added_to_history(self, mock_alerts):
        alert = Alert(
            alert_id="a4", severity=AlertSeverity.WARNING,
            title="W", message="m", source_agent="test",
        )
        mock_alerts.send_alert(alert)
        assert len(mock_alerts.get_alert_history()) == 1

    def test_multiple_alerts_in_history(self, mock_alerts):
        for i in range(5):
            mock_alerts.send_alert(Alert(
                alert_id=f"a{i}", severity=AlertSeverity.INFO,
                title=f"Alert {i}", message="m", source_agent="test",
            ))
        assert len(mock_alerts.get_alert_history()) == 5


# ---------------------------------------------------------------------------
# History filtering
# ---------------------------------------------------------------------------

class TestAlertHistory:
    def test_filter_by_severity(self, mock_alerts):
        mock_alerts.send_alert(Alert(
            alert_id="w1", severity=AlertSeverity.WARNING,
            title="W", message="m", source_agent="test",
        ))
        mock_alerts.send_alert(Alert(
            alert_id="c1", severity=AlertSeverity.CRITICAL,
            title="C", message="m", source_agent="test",
        ))
        mock_alerts.send_alert(Alert(
            alert_id="i1", severity=AlertSeverity.INFO,
            title="I", message="m", source_agent="test",
        ))
        warnings = mock_alerts.get_alert_history(severity=AlertSeverity.WARNING)
        assert len(warnings) == 1
        assert warnings[0].alert_id == "w1"

        criticals = mock_alerts.get_alert_history(severity=AlertSeverity.CRITICAL)
        assert len(criticals) == 1

    def test_get_all_history(self, mock_alerts):
        for sev in AlertSeverity:
            mock_alerts.send_alert(Alert(
                alert_id=sev.value, severity=sev,
                title=sev.value, message="m", source_agent="test",
            ))
        assert len(mock_alerts.get_alert_history()) == 3


# ---------------------------------------------------------------------------
# Alert summary
# ---------------------------------------------------------------------------

class TestAlertSummary:
    def test_summary_empty(self, mock_alerts):
        summary = mock_alerts.get_alert_summary()
        assert summary["total_alerts"] == 0
        assert summary["auto_remediation_rate"] == "N/A"

    def test_summary_with_alerts(self, mock_alerts):
        mock_alerts.send_alert(Alert(
            alert_id="1", severity=AlertSeverity.WARNING,
            title="W", message="m", source_agent="test",
        ))
        mock_alerts.send_alert(Alert(
            alert_id="2", severity=AlertSeverity.CRITICAL,
            title="C", message="m", source_agent="test", auto_remediated=True,
        ))
        summary = mock_alerts.get_alert_summary()
        assert summary["total_alerts"] == 2
        assert summary["by_severity"]["warning"] == 1
        assert summary["by_severity"]["critical"] == 1
        assert summary["auto_remediated"] == 1
        assert "50.0%" in summary["auto_remediation_rate"]


# ---------------------------------------------------------------------------
# Channel configuration
# ---------------------------------------------------------------------------

class TestChannelConfig:
    def test_configure_channel(self, mock_alerts):
        mock_alerts.configure_channel(AlertChannel.SLACK, {"webhook_url": "https://hooks.slack.com/xxx"})
        assert "slack" in mock_alerts._channel_configs
        assert mock_alerts._channel_configs["slack"]["webhook_url"] == "https://hooks.slack.com/xxx"


# ---------------------------------------------------------------------------
# DBSQL alert definitions
# ---------------------------------------------------------------------------

class TestDBSQLAlerts:
    def test_dbsql_definitions_generated(self, mock_alerts):
        defs = mock_alerts.create_dbsql_alert_definitions()
        assert isinstance(defs, list)
        assert len(defs) == 6
        names = [d["name"] for d in defs]
        assert "Lakebase Cache Hit Ratio Warning" in names
        assert "Lakebase Cache Hit Ratio Critical" in names
        assert "Lakebase Dead Tuple Ratio Critical" in names
        assert "Lakebase Connection Utilization Warning" in names
        assert "Lakebase TXID Wraparound Risk" in names
        assert "Lakebase Sync Freshness Alert" in names

    def test_dbsql_definitions_have_required_fields(self, mock_alerts):
        defs = mock_alerts.create_dbsql_alert_definitions()
        for defn in defs:
            assert "name" in defn
            assert "query" in defn
            assert "condition" in defn
            assert "severity" in defn
            assert defn["severity"] in ("warning", "critical")
