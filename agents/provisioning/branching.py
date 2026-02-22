"""
BranchingMixin — Branch Management (Tasks 5-15, 16-21, 37-43)

Contains:
- create_branch
- protect_branch
- enforce_ttl_policies
- monitor_branch_count
- reset_branch_from_parent
- create_branch_on_pr
- delete_branch_on_pr_close
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from framework.agent_framework import EventType
from config.settings import TTL_POLICIES

logger = logging.getLogger("lakebase_ops.provisioning")


class BranchingMixin:
    """Mixin providing branch lifecycle management."""

    def create_branch(self, project_id: str, branch_name: str,
                      branch_type: str = "ephemeral",
                      source_branch: str = "development",
                      ttl_seconds: Optional[int] = None) -> dict:
        """
        Create a branch with proper naming and TTL.
        Implements Tasks 8-15 based on branch type.
        """
        # Determine TTL from type if not specified
        if ttl_seconds is None:
            for prefix, ttl in TTL_POLICIES.items():
                if branch_name.startswith(prefix):
                    ttl_seconds = ttl
                    break

        result = self.client.create_branch(
            project_id, branch_name,
            source_branch=source_branch,
            ttl_seconds=ttl_seconds,
        )

        # Log branch creation
        self.writer.write_metrics("branch_lifecycle", [{
            "event_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_name,
            "event_type": "created",
            "source_branch": source_branch,
            "ttl_seconds": ttl_seconds,
            "is_protected": False,
            "actor": "ProvisioningAgent",
            "reason": f"Branch creation ({branch_type})",
        }])

        self.emit_event(EventType.BRANCH_CREATED, {
            "project_id": project_id,
            "branch_id": branch_name,
            "branch_type": branch_type,
        })

        return result

    def protect_branch(self, project_id: str, branch_id: str) -> dict:
        """Mark a branch as protected. Tasks 16-17."""
        success = self.client.protect_branch(project_id, branch_id)

        self.writer.write_metrics("branch_lifecycle", [{
            "event_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "event_type": "protected",
            "source_branch": "",
            "ttl_seconds": None,
            "is_protected": True,
            "actor": "ProvisioningAgent",
            "reason": "Branch protection applied",
        }])

        self.emit_event(EventType.BRANCH_PROTECTED, {
            "project_id": project_id,
            "branch_id": branch_id,
        })

        return {"project_id": project_id, "branch_id": branch_id, "protected": success}

    def enforce_ttl_policies(self, project_id: str) -> dict:
        """
        Scan branches and delete any exceeding TTL.
        Task 18 + PRD FR-06 TTL enforcement.
        """
        branches = self.client.list_branches(project_id)
        deleted = []
        kept = []

        for branch in branches:
            branch_name = branch.get("name", "").split("/")[-1]
            is_protected = branch.get("is_protected", False)

            if is_protected:
                kept.append(branch_name)
                continue

            # In production: check creation time vs TTL
            # Mock: demonstrate the logic
            kept.append(branch_name)

        logger.info(f"TTL enforcement: {len(deleted)} deleted, {len(kept)} kept")

        return {
            "project_id": project_id,
            "branches_deleted": deleted,
            "branches_kept": kept,
            "total_active": len(kept),
        }

    def monitor_branch_count(self, project_id: str, max_limit: int = 10) -> dict:
        """
        Alert when branch count approaches limit (max 10 unarchived).
        Task 19 + PRD FR-06.
        """
        branches = self.client.list_branches(project_id)
        count = len(branches)
        utilization = count / max_limit

        if utilization >= 0.8:
            from utils.alerting import Alert, AlertSeverity
            severity = AlertSeverity.CRITICAL if utilization >= 0.9 else AlertSeverity.WARNING
            self.alerts.send_alert(Alert(
                alert_id=str(uuid.uuid4())[:8],
                severity=severity,
                title=f"Branch count at {count}/{max_limit}",
                message=f"Project {project_id} has {count} active branches ({utilization:.0%} of limit)",
                source_agent=self.name,
                metric_name="branch_count",
                metric_value=count,
                threshold=max_limit,
                project_id=project_id,
            ))

        return {
            "project_id": project_id,
            "branch_count": count,
            "max_limit": max_limit,
            "utilization": f"{utilization:.0%}",
            "alert_triggered": utilization >= 0.8,
        }

    def reset_branch_from_parent(self, project_id: str, branch_id: str = "staging") -> dict:
        """
        Reset branch from parent (nightly staging reset).
        Task 40 + PRD scheduled nightly reset.
        """
        success = self.client.reset_branch(project_id, branch_id)

        self.writer.write_metrics("branch_lifecycle", [{
            "event_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "event_type": "reset",
            "source_branch": "production",
            "ttl_seconds": None,
            "is_protected": True,
            "actor": "ProvisioningAgent",
            "reason": "Nightly staging reset from production",
        }])

        return {"project_id": project_id, "branch_id": branch_id, "reset": success}

    def create_branch_on_pr(self, project_id: str, pr_number: int) -> dict:
        """Create ephemeral branch when PR opened. PRD FR-06."""
        branch_name = f"ci-pr-{pr_number}"
        return self.create_branch(
            project_id, branch_name,
            branch_type="ci",
            source_branch="staging",
            ttl_seconds=TTL_POLICIES["ci"],
        )

    def delete_branch_on_pr_close(self, project_id: str, pr_number: int) -> dict:
        """Delete branch when PR closed/merged. PRD FR-06."""
        branch_name = f"ci-pr-{pr_number}"
        success = self.client.delete_branch(project_id, branch_name)

        self.writer.write_metrics("branch_lifecycle", [{
            "event_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_name,
            "event_type": "deleted",
            "source_branch": "",
            "ttl_seconds": None,
            "is_protected": False,
            "actor": "ProvisioningAgent",
            "reason": f"PR #{pr_number} closed",
        }])

        self.emit_event(EventType.BRANCH_DELETED, {
            "project_id": project_id,
            "branch_id": branch_name,
        })

        return {"branch": branch_name, "deleted": success}
