"""
OperationsMixin — UC-11, UC-13, UC-14: Cost attribution, self-healing, and NL DBA.

- UC-11: Cost attribution and scale-to-zero optimization
- UC-13: Self-healing incident response (root cause diagnosis + auto-remediation)
- UC-14: Natural language DBA operations (LLM-powered Q&A)
"""

from __future__ import annotations

import logging

from framework.agent_framework import EventType

logger = logging.getLogger("lakebase_ops.health")


class OperationsMixin:
    """UC-11: Cost attribution, UC-13: Self-healing, UC-14: Natural language DBA."""

    # -----------------------------------------------------------------------
    # UC-11: Cost Attribution & Optimization
    # -----------------------------------------------------------------------

    def track_cost_attribution(self, project_id: str) -> dict:
        """
        Track Lakebase costs from system.billing.usage.
        UC-11: Daily.
        """
        # In production: query system.billing.usage via Spark
        # Mock cost data
        return {
            "project_id": project_id,
            "period": "last_7_days",
            "total_dbus": 1250.5,
            "cost_breakdown": {
                "production": {"dbus": 800.0, "pct": 64.0},
                "staging": {"dbus": 200.0, "pct": 16.0},
                "development": {"dbus": 150.0, "pct": 12.0},
                "ci_branches": {"dbus": 100.5, "pct": 8.0},
            },
            "recommendations": [
                "CI branches consumed 8% of DBUs — ensure TTL policies are enforced",
                "Development branch idle 40% of time — verify scale-to-zero is working",
            ],
        }

    def recommend_scale_to_zero_timeout(self, project_id: str, branch_id: str) -> dict:
        """
        Analyze activity patterns and recommend optimal idle timeout.
        UC-11: Weekly.
        """
        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "current_timeout": "5 minutes",
            "recommended_timeout": "10 minutes",
            "reason": "Branch has bursty traffic with 8-12 minute gaps between requests. "
                      "Increasing timeout to 10 minutes reduces cold starts by 40%.",
            "estimated_savings": "15% reduction in total CU-hours (fewer cold start overhead)",
        }

    # -----------------------------------------------------------------------
    # UC-13: Self-Healing Incident Response (V2)
    # -----------------------------------------------------------------------

    def diagnose_root_cause(self, anomaly_report: dict) -> dict:
        """
        Correlate metrics across multiple dimensions to determine root cause.
        UC-13: Triggered on anomaly detection.
        """
        # In production: correlate pg_stat_statements, pg_locks, pg_stat_activity
        metric = anomaly_report.get("metric", "unknown")
        value = anomaly_report.get("value", 0)

        diagnosis = {
            "anomaly": metric,
            "value": value,
            "probable_causes": [],
            "recommended_actions": [],
            "auto_fixable": False,
        }

        if metric == "cache_hit_ratio" and value < 0.95:
            diagnosis["probable_causes"] = [
                "Working set exceeds available shared_buffers",
                "Full table scans on large tables without proper indexes",
                "Recent restart causing cold cache",
            ]
            diagnosis["recommended_actions"] = [
                "Increase CU (compute units) to get more shared_buffers",
                "Add indexes for frequently scanned tables (see index recommendations)",
                "Use pg_prewarm to warm cache after restart",
            ]
        elif metric == "dead_tuple_ratio" and value > 0.25:
            diagnosis["probable_causes"] = [
                "Autovacuum not keeping up with high-churn tables",
                "Long-running transactions preventing vacuum from reclaiming space",
            ]
            diagnosis["recommended_actions"] = [
                "Execute manual VACUUM ANALYZE on affected tables",
                "Tune autovacuum parameters for high-churn tables",
                "Investigate and terminate long-running transactions",
            ]
            diagnosis["auto_fixable"] = True

        return diagnosis

    def self_heal(self, issue_id: str, remediation_plan: dict) -> dict:
        """
        Execute approved auto-remediation.
        UC-13: Only for low-risk actions.
        """
        action = remediation_plan.get("action", "")
        risk = remediation_plan.get("risk_level", "high")

        if risk != "low":
            return {
                "issue_id": issue_id,
                "status": "escalated",
                "reason": f"Risk level '{risk}' requires human approval",
                "recommended_action": action,
            }

        # Execute low-risk remediation
        project_id = remediation_plan.get("project_id", "")
        branch_id = remediation_plan.get("branch_id", "")

        if "vacuum" in action.lower():
            table = remediation_plan.get("table", "")
            self.client.execute_statement(project_id, branch_id, f"VACUUM ANALYZE {table}")
            status = "remediated"
        elif "terminate" in action.lower():
            self.terminate_idle_connections(project_id, branch_id)
            status = "remediated"
        else:
            status = "unknown_action"

        self.emit_event(EventType.SELF_HEAL_EXECUTED, {
            "issue_id": issue_id,
            "action": action,
            "status": status,
        })

        return {"issue_id": issue_id, "action": action, "status": status}

    # -----------------------------------------------------------------------
    # UC-14: Natural Language DBA Operations (V2)
    # -----------------------------------------------------------------------

    def natural_language_dba(self, question: str, project_id: str = "",
                              branch_id: str = "") -> dict:
        """
        LLM-powered DBA Q&A for developers.
        UC-14: "Why is my query slow?" -> actionable answer.
        """
        # In production: use Foundation Model API (Llama 4)
        # Mock response
        q_lower = question.lower()

        if "slow" in q_lower or "performance" in q_lower:
            answer = {
                "question": question,
                "analysis": "Based on pg_stat_statements data, your most expensive query is a JOIN between orders and products with a sequential scan on orders.",
                "root_cause": "Missing index on orders.product_id causing sequential scan of 5M rows",
                "recommendation": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_product_id ON orders(product_id);",
                "estimated_improvement": "Expected 95% reduction in query execution time (from 20ms to ~1ms mean)",
                "confidence": "high",
            }
        elif "connection" in q_lower:
            answer = {
                "question": question,
                "analysis": "Current connection utilization is at 15% with 3 idle-in-transaction sessions.",
                "root_cause": "Application not properly closing connections after transactions",
                "recommendation": "Add connection.commit() and connection.close() in your application code, or use a connection pool with idle timeout",
                "confidence": "medium",
            }
        else:
            answer = {
                "question": question,
                "analysis": "I can help with query performance, connection issues, vacuum management, and index recommendations. Please provide more context about your question.",
                "confidence": "low",
            }

        return answer
