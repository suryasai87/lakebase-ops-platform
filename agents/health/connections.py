"""
ConnectionMixin — UC-10: Connection pool monitoring and idle session cleanup.

Tracks active/idle/idle-in-transaction connections and auto-terminates
sessions idle for more than 30 minutes.
"""

from __future__ import annotations

import logging

from framework.agent_framework import EventType
from sql import queries

logger = logging.getLogger("lakebase_ops.health")


class ConnectionMixin:
    """UC-10: Connection pool monitoring and idle session cleanup."""

    def monitor_connections(self, project_id: str, branch_id: str) -> dict:
        """
        Track active/idle/idle-in-transaction connections.
        UC-10: Every minute.
        """
        activity = self.client.execute_query(project_id, branch_id, queries.CONNECTION_DETAILS)

        states = {"active": 0, "idle": 0, "idle in transaction": 0, "other": 0}
        long_idle = []

        for conn in activity:
            state = conn.get("state", "other")
            states[state] = states.get(state, 0) + 1

            idle_sec = conn.get("idle_seconds", 0)
            if isinstance(idle_sec, str):
                idle_sec = float(idle_sec)
            if state == "idle" and idle_sec > 1800:  # 30 min
                long_idle.append({
                    "pid": conn.get("pid"),
                    "idle_seconds": idle_sec,
                    "backend_start": conn.get("backend_start"),
                })

        return {
            "total_connections": sum(states.values()),
            "states": states,
            "long_idle_sessions": len(long_idle),
            "long_idle_details": long_idle,
        }

    def terminate_idle_connections(self, project_id: str, branch_id: str,
                                    max_idle_minutes: int = 30) -> dict:
        """
        Kill sessions idle > threshold.
        UC-10: Auto-terminate on high connection utilization.
        """
        conn_info = self.monitor_connections(project_id, branch_id)
        terminated = []

        for session in conn_info.get("long_idle_details", []):
            pid = session.get("pid")
            self.client.execute_statement(
                project_id, branch_id,
                f"SELECT pg_terminate_backend({pid})"
            )
            terminated.append(pid)

        if terminated:
            self.emit_event(EventType.SELF_HEAL_EXECUTED, {
                "action": "terminate_idle_connections",
                "pids_terminated": terminated,
            })

        return {
            "sessions_terminated": len(terminated),
            "pids": terminated,
        }
