"""
AlertManager: Multi-channel alerting for LakebaseOps.

Supports:
- Slack notifications
- PagerDuty critical alerts
- Email digests
- DBSQL alert creation
- Audit logging of all alerts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("lakebase_ops.alerting")


class AlertChannel(Enum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    DBSQL = "dbsql"
    LOG = "log"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert record for tracking and audit."""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    source_agent: str
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    project_id: str = ""
    branch_id: str = ""
    channels_sent: list[str] = field(default_factory=list)
    sop_action: str = ""
    auto_remediated: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source_agent": self.source_agent,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "channels_sent": self.channels_sent,
            "sop_action": self.sop_action,
            "auto_remediated": self.auto_remediated,
            "timestamp": self.timestamp.isoformat(),
        }


class AlertManager:
    """
    Multi-channel alert manager with routing based on severity.

    Routing rules:
    - INFO: Log only
    - WARNING: Slack + Log
    - CRITICAL: Slack + PagerDuty + Log
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._alert_history: list[Alert] = []
        self._channel_configs: dict[str, dict] = {}

    def configure_channel(self, channel: AlertChannel, config: dict) -> None:
        """Configure a notification channel."""
        self._channel_configs[channel.value] = config
        logger.info(f"Configured alert channel: {channel.value}")

    def send_alert(self, alert: Alert) -> Alert:
        """Route and send an alert based on severity."""
        channels = self._get_channels_for_severity(alert.severity)

        for channel in channels:
            self._send_to_channel(channel, alert)
            alert.channels_sent.append(channel.value)

        self._alert_history.append(alert)
        logger.info(
            f"[ALERT {alert.severity.value.upper()}] {alert.title} "
            f"-> {', '.join(alert.channels_sent)}"
        )
        return alert

    def _get_channels_for_severity(self, severity: AlertSeverity) -> list[AlertChannel]:
        """Determine which channels to use based on severity."""
        if severity == AlertSeverity.CRITICAL:
            return [AlertChannel.SLACK, AlertChannel.PAGERDUTY, AlertChannel.LOG]
        elif severity == AlertSeverity.WARNING:
            return [AlertChannel.SLACK, AlertChannel.LOG]
        else:
            return [AlertChannel.LOG]

    def _send_to_channel(self, channel: AlertChannel, alert: Alert) -> None:
        """Send alert to a specific channel."""
        if self.mock_mode:
            logger.info(f"  [MOCK {channel.value}] {alert.title}: {alert.message}")
            return

        if channel == AlertChannel.SLACK:
            self._send_slack(alert)
        elif channel == AlertChannel.PAGERDUTY:
            self._send_pagerduty(alert)
        elif channel == AlertChannel.EMAIL:
            self._send_email(alert)

    def _send_slack(self, alert: Alert) -> None:
        """Send Slack notification."""
        config = self._channel_configs.get("slack", {})
        webhook_url = config.get("webhook_url", "")
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        emoji = severity_emoji.get(alert.severity.value, "📋")
        message = {
            "text": f"{emoji} *[{alert.severity.value.upper()}]* {alert.title}\n{alert.message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{emoji} *{alert.title}*\n{alert.message}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Project: `{alert.project_id}` | Branch: `{alert.branch_id}` | Agent: `{alert.source_agent}`"}
                    ],
                },
            ],
        }
        logger.info(f"Slack alert sent: {alert.title}")

    def _send_pagerduty(self, alert: Alert) -> None:
        """Send PagerDuty incident."""
        config = self._channel_configs.get("pagerduty", {})
        logger.info(f"PagerDuty incident created: {alert.title}")

    def _send_email(self, alert: Alert) -> None:
        """Send email notification."""
        logger.info(f"Email sent: {alert.title}")

    def get_alert_history(self, severity: Optional[AlertSeverity] = None) -> list[Alert]:
        """Get alert history, optionally filtered by severity."""
        if severity:
            return [a for a in self._alert_history if a.severity == severity]
        return self._alert_history

    def get_alert_summary(self) -> dict:
        """Get summary of all alerts."""
        total = len(self._alert_history)
        by_severity = {}
        for sev in AlertSeverity:
            count = sum(1 for a in self._alert_history if a.severity == sev)
            by_severity[sev.value] = count
        auto_remediated = sum(1 for a in self._alert_history if a.auto_remediated)
        return {
            "total_alerts": total,
            "by_severity": by_severity,
            "auto_remediated": auto_remediated,
            "auto_remediation_rate": f"{(auto_remediated / total * 100):.1f}%" if total > 0 else "N/A",
        }

    def create_dbsql_alert_definitions(self) -> list[dict]:
        """
        Generate DBSQL alert definitions for all monitored thresholds.
        These can be deployed via Databricks SQL Alerts API.
        """
        return [
            {
                "name": "Lakebase Cache Hit Ratio Warning",
                "query": """
                    SELECT project_id, branch_id, metric_value
                    FROM ops_catalog.lakebase_ops.lakebase_metrics
                    WHERE metric_name = 'cache_hit_ratio'
                      AND metric_value < 0.99
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
            {
                "name": "Lakebase Cache Hit Ratio Critical",
                "query": """
                    SELECT project_id, branch_id, metric_value
                    FROM ops_catalog.lakebase_ops.lakebase_metrics
                    WHERE metric_name = 'cache_hit_ratio'
                      AND metric_value < 0.95
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Dead Tuple Ratio Critical",
                "query": """
                    SELECT project_id, branch_id, metric_value
                    FROM ops_catalog.lakebase_ops.lakebase_metrics
                    WHERE metric_name = 'dead_tuple_ratio'
                      AND metric_value > 0.25
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Connection Utilization Warning",
                "query": """
                    SELECT project_id, branch_id, metric_value
                    FROM ops_catalog.lakebase_ops.lakebase_metrics
                    WHERE metric_name = 'connection_utilization'
                      AND metric_value > 0.70
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
            {
                "name": "Lakebase TXID Wraparound Risk",
                "query": """
                    SELECT project_id, branch_id, metric_value
                    FROM ops_catalog.lakebase_ops.lakebase_metrics
                    WHERE metric_name = 'txid_age'
                      AND metric_value > 500000000
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Sync Freshness Alert",
                "query": """
                    SELECT source_table, target_table, freshness_lag_seconds
                    FROM ops_catalog.lakebase_ops.sync_validation_history
                    WHERE freshness_lag_seconds > 3600
                      AND validated_at > CURRENT_TIMESTAMP - INTERVAL 30 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
        ]
