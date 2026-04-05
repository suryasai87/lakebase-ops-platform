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
import os
import smtplib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

import requests

_OPS_CATALOG = os.getenv("OPS_CATALOG", "ops_catalog")
_OPS_SCHEMA = os.getenv("OPS_SCHEMA", "lakebase_ops")

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
        logger.info(f"[ALERT {alert.severity.value.upper()}] {alert.title} -> {', '.join(alert.channels_sent)}")
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
        """Send Slack notification via incoming webhook.

        Requires channel config: {"webhook_url": "https://hooks.slack.com/services/..."}
        """
        config = self._channel_configs.get("slack", {})
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            logger.warning("Slack webhook_url not configured; skipping Slack alert")
            return

        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}  # noqa: RUF001
        emoji = severity_emoji.get(alert.severity.value, "📋")
        payload = {
            "text": f"{emoji} *[{alert.severity.value.upper()}]* {alert.title}\n{alert.message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{emoji} *{alert.title}*\n{alert.message}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Project: `{alert.project_id}` | Branch: `{alert.branch_id}` | Agent: `{alert.source_agent}`",
                        }
                    ],
                },
            ],
        }
        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"Slack alert sent: {alert.title}")
        except requests.RequestException as exc:
            logger.error(f"Slack alert failed for '{alert.title}': {exc}")

    def _send_pagerduty(self, alert: Alert) -> None:
        """Send PagerDuty alert via Events API v2.

        Requires channel config: {"routing_key": "<integration-key>"}
        See: https://developer.pagerduty.com/docs/events-api-v2/trigger-events/
        """
        config = self._channel_configs.get("pagerduty", {})
        routing_key = config.get("routing_key", "")
        if not routing_key:
            logger.warning("PagerDuty routing_key not configured; skipping PagerDuty alert")
            return

        severity_map = {
            "info": "info",
            "warning": "warning",
            "critical": "critical",
        }
        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": alert.alert_id,
            "payload": {
                "summary": f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}",
                "source": f"lakebase-ops/{alert.source_agent}",
                "severity": severity_map.get(alert.severity.value, "error"),
                "component": alert.source_agent,
                "group": alert.project_id or "lakebase-ops",
                "class": alert.metric_name or "general",
                "custom_details": {
                    "project_id": alert.project_id,
                    "branch_id": alert.branch_id,
                    "metric_name": alert.metric_name,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "sop_action": alert.sop_action,
                },
            },
        }
        try:
            resp = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"PagerDuty incident created: {alert.title} (dedup_key={alert.alert_id})")
        except requests.RequestException as exc:
            logger.error(f"PagerDuty alert failed for '{alert.title}': {exc}")

    def _send_email(self, alert: Alert) -> None:
        """Send email notification via SMTP.

        Requires channel config: {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "password",
            "from_addr": "alerts@lakebase-ops.com",
            "to_addrs": ["team@example.com"]
        }
        """
        config = self._channel_configs.get("email", {})
        smtp_host = config.get("smtp_host", "")
        if not smtp_host:
            logger.warning("Email smtp_host not configured; skipping email alert")
            return

        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user", "")
        smtp_password = config.get("smtp_password", "")
        from_addr = config.get("from_addr", smtp_user)
        to_addrs = config.get("to_addrs", [])
        if not to_addrs:
            logger.warning("Email to_addrs not configured; skipping email alert")
            return

        subject = f"[LakebaseOps {alert.severity.value.upper()}] {alert.title}"
        body = (
            f"Alert: {alert.title}\n"
            f"Severity: {alert.severity.value}\n"
            f"Message: {alert.message}\n\n"
            f"Project: {alert.project_id}\n"
            f"Branch: {alert.branch_id}\n"
            f"Agent: {alert.source_agent}\n"
            f"Metric: {alert.metric_name} = {alert.metric_value} (threshold: {alert.threshold})\n"
            f"SOP Action: {alert.sop_action}\n"
            f"Timestamp: {alert.timestamp.isoformat()}\n"
        )

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                if smtp_port != 25:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_addr, to_addrs, msg.as_string())
            logger.info(f"Email sent: {alert.title} -> {to_addrs}")
        except Exception as exc:
            logger.error(f"Email alert failed for '{alert.title}': {exc}")

    def get_alert_history(self, severity: AlertSeverity | None = None) -> list[Alert]:
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
                "query": f"""
                    SELECT project_id, branch_id, metric_value
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.lakebase_metrics
                    WHERE metric_name = 'cache_hit_ratio'
                      AND metric_value < 0.99
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
            {
                "name": "Lakebase Cache Hit Ratio Critical",
                "query": f"""
                    SELECT project_id, branch_id, metric_value
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.lakebase_metrics
                    WHERE metric_name = 'cache_hit_ratio'
                      AND metric_value < 0.95
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Dead Tuple Ratio Critical",
                "query": f"""
                    SELECT project_id, branch_id, metric_value
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.lakebase_metrics
                    WHERE metric_name = 'dead_tuple_ratio'
                      AND metric_value > 0.25
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Connection Utilization Warning",
                "query": f"""
                    SELECT project_id, branch_id, metric_value
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.lakebase_metrics
                    WHERE metric_name = 'connection_utilization'
                      AND metric_value > 0.70
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
            {
                "name": "Lakebase TXID Wraparound Risk",
                "query": f"""
                    SELECT project_id, branch_id, metric_value
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.lakebase_metrics
                    WHERE metric_name = 'txid_age'
                      AND metric_value > 500000000
                      AND snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 10 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "critical",
            },
            {
                "name": "Lakebase Sync Freshness Alert",
                "query": f"""
                    SELECT source_table, target_table, freshness_lag_seconds
                    FROM {_OPS_CATALOG}.{_OPS_SCHEMA}.sync_validation_history
                    WHERE freshness_lag_seconds > 3600
                      AND validated_at > CURRENT_TIMESTAMP - INTERVAL 30 MINUTES
                """,
                "condition": "rows > 0",
                "severity": "warning",
            },
        ]
