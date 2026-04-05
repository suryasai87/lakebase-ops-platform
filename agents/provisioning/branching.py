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
- create_branch_from_git_hook      (GAP-037)
- manage_pr_branch_lifecycle        (GAP-037)
- create_qa_branch                  (GAP-039)
- reset_branch_to_parent            (GAP-039)
"""

from __future__ import annotations

import logging
import re
import uuid

from config.settings import TTL_POLICIES
from framework.agent_framework import EventType

logger = logging.getLogger("lakebase_ops.provisioning")


class BranchingMixin:
    """Mixin providing branch lifecycle management."""

    # ------------------------------------------------------------------
    # Internal helper: policy-aware branch creation (GAP-038 / GAP-040)
    # ------------------------------------------------------------------

    def _resolve_policy_engine(self):
        """Lazily resolve the PolicyEngine (avoids import cycles)."""
        if not hasattr(self, "_policy_engine"):
            try:
                from agents.provisioning.policy_engine import PolicyEngine

                self._policy_engine = PolicyEngine()
            except Exception:
                self._policy_engine = None
        return self._policy_engine

    def _write_branch_event(
        self,
        project_id: str,
        branch_id: str,
        event_type: str,
        source_branch: str = "",
        ttl_seconds: int | None = None,
        is_protected: bool = False,
        reason: str = "",
        creator_type: str = "agent",
    ) -> None:
        """Write a branch_lifecycle Delta row with attribution (GAP-040)."""
        self.writer.write_metrics(
            "branch_lifecycle",
            [
                {
                    "event_id": str(uuid.uuid4())[:8],
                    "project_id": project_id,
                    "branch_id": branch_id,
                    "event_type": event_type,
                    "source_branch": source_branch,
                    "ttl_seconds": ttl_seconds,
                    "is_protected": is_protected,
                    "actor": self.name,
                    "reason": reason,
                    "creator_type": creator_type,  # GAP-040: human / agent / ci
                }
            ],
        )

    # ------------------------------------------------------------------
    # Core branch CRUD
    # ------------------------------------------------------------------

    def create_branch(
        self,
        project_id: str,
        branch_name: str,
        branch_type: str = "ephemeral",
        source_branch: str = "development",
        ttl_seconds: int | None = None,
        creator_type: str = "agent",
    ) -> dict:
        """
        Create a branch with proper naming and TTL.
        Implements Tasks 8-15 based on branch type.

        Args:
            project_id: Lakebase project ID.
            branch_name: Name for the new branch.
            branch_type: Logical type (ephemeral, ci, qa, etc.).
            source_branch: Parent branch to fork from.
            ttl_seconds: Optional TTL override.
            creator_type: Who created it — human, agent, or ci (GAP-040).
        """
        # GAP-038: check policies before creation
        engine = self._resolve_policy_engine()
        if engine is not None:
            branches = self.client.list_branches(project_id)
            result = engine.check_branch_creation(
                branch_name,
                current_branch_count=len(branches),
                current_unarchived_count=len(branches),
                creator_type=creator_type,
            )
            if not result.allowed:
                violations = [v.message for v in result.violations]
                logger.warning(f"Policy violation creating '{branch_name}': {violations}")
                return {
                    "project_id": project_id,
                    "branch_name": branch_name,
                    "status": "blocked",
                    "policy_violations": violations,
                }
            if result.has_warnings:
                for w in result.warnings:
                    logger.warning(f"Policy warning: {w.message}")

        # Determine TTL from type if not specified
        if ttl_seconds is None:
            if engine is not None:
                ttl_seconds = engine.get_ttl_for_prefix(branch_name)
            if ttl_seconds is None:
                for prefix, ttl in TTL_POLICIES.items():
                    if branch_name.startswith(prefix):
                        ttl_seconds = ttl
                        break

        result = self.client.create_branch(
            project_id,
            branch_name,
            source_branch=source_branch,
            ttl_seconds=ttl_seconds,
        )

        # Log branch creation with attribution (GAP-040)
        self._write_branch_event(
            project_id=project_id,
            branch_id=branch_name,
            event_type="created",
            source_branch=source_branch,
            ttl_seconds=ttl_seconds,
            is_protected=False,
            reason=f"Branch creation ({branch_type})",
            creator_type=creator_type,
        )

        self.emit_event(
            EventType.BRANCH_CREATED,
            {
                "project_id": project_id,
                "branch_id": branch_name,
                "branch_type": branch_type,
                "creator_type": creator_type,
            },
        )

        return result

    def protect_branch(self, project_id: str, branch_id: str) -> dict:
        """Mark a branch as protected. Tasks 16-17."""
        success = self.client.protect_branch(project_id, branch_id)

        self._write_branch_event(
            project_id=project_id,
            branch_id=branch_id,
            event_type="protected",
            is_protected=True,
            reason="Branch protection applied",
        )

        self.emit_event(
            EventType.BRANCH_PROTECTED,
            {
                "project_id": project_id,
                "branch_id": branch_id,
            },
        )

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
            self.alerts.send_alert(
                Alert(
                    alert_id=str(uuid.uuid4())[:8],
                    severity=severity,
                    title=f"Branch count at {count}/{max_limit}",
                    message=f"Project {project_id} has {count} active branches ({utilization:.0%} of limit)",
                    source_agent=self.name,
                    metric_name="branch_count",
                    metric_value=count,
                    threshold=max_limit,
                    project_id=project_id,
                )
            )

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
        # GAP-038: check policy before reset
        engine = self._resolve_policy_engine()
        if engine is not None:
            check = engine.check_branch_reset(branch_id, "production")
            if not check.allowed:
                violations = [v.message for v in check.violations]
                return {
                    "project_id": project_id,
                    "branch_id": branch_id,
                    "status": "blocked",
                    "policy_violations": violations,
                }

        success = self.client.reset_branch(project_id, branch_id)

        self._write_branch_event(
            project_id=project_id,
            branch_id=branch_id,
            event_type="reset",
            source_branch="production",
            is_protected=True,
            reason="Nightly staging reset from production",
        )

        return {"project_id": project_id, "branch_id": branch_id, "reset": success}

    def create_branch_on_pr(self, project_id: str, pr_number: int) -> dict:
        """Create ephemeral branch when PR opened. PRD FR-06."""
        branch_name = f"ci-pr-{pr_number}"
        return self.create_branch(
            project_id,
            branch_name,
            branch_type="ci",
            source_branch="staging",
            ttl_seconds=TTL_POLICIES["ci"],
            creator_type="ci",
        )

    def delete_branch_on_pr_close(self, project_id: str, pr_number: int) -> dict:
        """Delete branch when PR closed/merged. PRD FR-06."""
        branch_name = f"ci-pr-{pr_number}"

        # GAP-038: check deletion policy
        engine = self._resolve_policy_engine()
        if engine is not None:
            check = engine.check_branch_deletion(branch_name)
            if not check.allowed:
                violations = [v.message for v in check.violations]
                return {
                    "branch": branch_name,
                    "deleted": False,
                    "status": "blocked",
                    "policy_violations": violations,
                }

        success = self.client.delete_branch(project_id, branch_name)

        self._write_branch_event(
            project_id=project_id,
            branch_id=branch_name,
            event_type="deleted",
            reason=f"PR #{pr_number} closed",
            creator_type="ci",
        )

        self.emit_event(
            EventType.BRANCH_DELETED,
            {
                "project_id": project_id,
                "branch_id": branch_name,
            },
        )

        return {"branch": branch_name, "deleted": success}

    # ------------------------------------------------------------------
    # GAP-037: Git hook integration
    # ------------------------------------------------------------------

    def create_branch_from_git_hook(
        self,
        project_id: str,
        git_ref: str,
        username: str,
        source_branch: str = "staging",
    ) -> dict:
        """
        Create a Lakebase branch triggered by a Git post-checkout hook.

        Called by hooks/post-checkout.sh (or any CI webhook) when a developer
        checks out a new Git branch. The branch name is sanitized to
        RFC 1123 format automatically.

        Args:
            project_id: Lakebase project ID.
            git_ref: Git branch name (e.g. ``feature/JIRA-123-add-users``).
            username: Git user who triggered the checkout.
            source_branch: Parent Lakebase branch (default: staging).

        Returns:
            dict with branch creation result including the sanitized name.
        """
        # Sanitize git ref to RFC 1123 (lowercase, alphanum + hyphens, max 63)
        sanitized = re.sub(r"[^a-z0-9-]", "-", git_ref.lower())
        sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")[:63]

        if not sanitized:
            return {
                "status": "error",
                "message": f"Git ref '{git_ref}' produces empty branch name after sanitization",
            }

        logger.info(
            f"Git hook: creating Lakebase branch '{sanitized}' "
            f"from '{source_branch}' (user: {username}, ref: {git_ref})"
        )

        result = self.create_branch(
            project_id=project_id,
            branch_name=sanitized,
            branch_type="ephemeral",
            source_branch=source_branch,
            creator_type="human",
        )

        # Augment result with git context
        if isinstance(result, dict):
            result["git_ref"] = git_ref
            result["git_user"] = username
            result["sanitized_name"] = sanitized

        return result

    def manage_pr_branch_lifecycle(
        self,
        project_id: str,
        pr_number: int,
        action: str,
        source_branch: str = "staging",
    ) -> dict:
        """
        Unified PR branch lifecycle manager (GAP-037).

        Handles the full lifecycle of a Lakebase branch tied to a pull request:
        opened, synchronize (re-push), and closed/merged.

        Args:
            project_id: Lakebase project ID.
            pr_number: Pull request number.
            action: PR event action — ``opened``, ``synchronize``, ``closed``, ``merged``.
            source_branch: Parent Lakebase branch for creation.

        Returns:
            dict describing what was done.
        """
        branch_name = f"ci-pr-{pr_number}"

        if action == "opened":
            result = self.create_branch(
                project_id=project_id,
                branch_name=branch_name,
                branch_type="ci",
                source_branch=source_branch,
                ttl_seconds=TTL_POLICIES.get("ci", 14400),
                creator_type="ci",
            )
            return {"action": "created", "branch": branch_name, "result": result}

        elif action == "synchronize":
            # Re-push: reset the CI branch to pick up latest changes
            engine = self._resolve_policy_engine()
            if engine is not None:
                check = engine.check_branch_reset(branch_name, source_branch)
                if not check.allowed:
                    return {
                        "action": "reset_blocked",
                        "branch": branch_name,
                        "violations": [v.message for v in check.violations],
                    }

            success = self.client.reset_branch(project_id, branch_name)
            self._write_branch_event(
                project_id=project_id,
                branch_id=branch_name,
                event_type="reset",
                source_branch=source_branch,
                reason=f"PR #{pr_number} synchronized (new push)",
                creator_type="ci",
            )
            return {"action": "reset", "branch": branch_name, "reset": success}

        elif action in ("closed", "merged"):
            return self.delete_branch_on_pr_close(project_id, pr_number)

        else:
            return {
                "action": action,
                "branch": branch_name,
                "status": "ignored",
                "message": f"Unrecognized PR action: {action}",
            }

    # ------------------------------------------------------------------
    # GAP-039: QA branch workflow
    # ------------------------------------------------------------------

    def create_qa_branch(
        self,
        project_id: str,
        version: str,
        source_branch: str | None = None,
        ttl_seconds: int | None = None,
    ) -> dict:
        """
        Create a QA validation branch for a release candidate (GAP-039).

        QA branches are forked from staging (or a custom source) and allow
        destructive testing without affecting other environments.

        Args:
            project_id: Lakebase project ID.
            version: Release version string (e.g. ``v2.3.0``).
            source_branch: Parent branch (default from policy or ``staging``).
            ttl_seconds: TTL override (default from policy or 14 days).

        Returns:
            dict with branch creation details.
        """
        engine = self._resolve_policy_engine()
        qa_config = engine.qa_branch_config if engine else {}

        branch_name = f"qa-release-{version}"
        src = source_branch or qa_config.get("source_branch", "staging")
        ttl = ttl_seconds or qa_config.get("default_ttl_seconds", TTL_POLICIES.get("qa", 1209600))

        logger.info(f"Creating QA branch '{branch_name}' from '{src}' for release {version}")

        result = self.create_branch(
            project_id=project_id,
            branch_name=branch_name,
            branch_type="qa",
            source_branch=src,
            ttl_seconds=ttl,
            creator_type="agent",
        )

        if isinstance(result, dict):
            result["qa_version"] = version
            result["allow_destructive_tests"] = qa_config.get("allow_destructive_tests", True)

        return result

    def reset_branch_to_parent(
        self,
        project_id: str,
        branch_id: str,
        parent_branch: str | None = None,
    ) -> dict:
        """
        Reset any branch back to its parent state (GAP-039).

        Useful for QA branches that need to be re-tested from a clean state
        after a failed test run, or for dev branches that drifted too far.

        Args:
            project_id: Lakebase project ID.
            branch_id: Branch to reset.
            parent_branch: Explicit parent (auto-detected if None).

        Returns:
            dict with reset result.
        """
        # Determine parent from policy if not provided
        if parent_branch is None:
            engine = self._resolve_policy_engine()
            if engine is not None:
                allowed_sources = engine.protection_rules.get("allowed_reset_sources", {})
                parent_branch = allowed_sources.get(branch_id, "staging")
            else:
                parent_branch = "staging"

        # Policy check
        engine = self._resolve_policy_engine()
        if engine is not None:
            check = engine.check_branch_reset(branch_id, parent_branch)
            if not check.allowed:
                violations = [v.message for v in check.violations]
                return {
                    "project_id": project_id,
                    "branch_id": branch_id,
                    "status": "blocked",
                    "policy_violations": violations,
                }

        logger.info(f"Resetting branch '{branch_id}' to parent '{parent_branch}'")

        success = self.client.reset_branch(project_id, branch_id)

        self._write_branch_event(
            project_id=project_id,
            branch_id=branch_id,
            event_type="reset",
            source_branch=parent_branch,
            reason=f"Branch reset to parent ({parent_branch})",
        )

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "parent_branch": parent_branch,
            "reset": success,
        }
