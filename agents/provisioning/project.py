"""
ProjectMixin — Project Setup (Tasks 1-4) + Read Replicas & HA (GAP-041)

Contains:
- provision_lakebase_project
- create_ops_catalog
- manage_read_replicas      (GAP-041)
- configure_ha              (GAP-041)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from framework.agent_framework import EventType
from config.settings import TTL_POLICIES

logger = logging.getLogger("lakebase_ops.provisioning")


class ProjectMixin:
    """Mixin providing Lakebase project creation and ops catalog setup."""

    def provision_lakebase_project(self, project_name: str, domain: str,
                                   environment: str = "production",
                                   branching_pattern: str = "multi_env_pipeline",
                                   tags: dict[str, str] | None = None,
                                   budget_policy_id: str | None = None) -> dict:
        """
        Create a Lakebase project with full branch hierarchy.
        Implements Setup Guide Tasks 1-15.
        GAP-033: Applies custom tags and budget policy on creation.

        Args:
            project_name: Project identifier (RFC 1123).
            domain: Business domain (e.g. "supply-chain").
            environment: Target environment.
            branching_pattern: Branching strategy.
            tags: Custom key-value tags for cost attribution.
            budget_policy_id: Optional budget policy to attach.
        """
        logger.info(f"Provisioning project: {project_name}")

        # Build default tags + user-supplied tags
        default_tags = {
            "domain": domain,
            "environment": environment,
            "managed_by": "lakebase-ops-platform",
        }
        if tags:
            default_tags.update(tags)

        # Task 1: Create project with domain-env naming
        project_spec = {}
        if budget_policy_id:
            project_spec["budget_policy_id"] = budget_policy_id
        project_result = self.client.create_project(project_name, spec=project_spec)

        # Apply tags via PATCH
        self.client.update_project_tags(project_name, default_tags)

        # Tasks 5-7: Create core branches
        branches_created = []

        # Production branch (Task 5)
        prod = self.client.create_branch(project_name, "production", is_protected=True)
        branches_created.append({"branch": "production", "type": "protected", "ttl": None})

        # Staging branch (Task 6)
        staging = self.client.create_branch(project_name, "staging",
                                            source_branch="production", is_protected=True)
        branches_created.append({"branch": "staging", "type": "protected", "ttl": None})

        # Development branch (Task 7)
        dev = self.client.create_branch(project_name, "development",
                                        source_branch="staging",
                                        ttl_seconds=TTL_POLICIES.get("dev"))
        branches_created.append({"branch": "development", "type": "ephemeral", "ttl": TTL_POLICIES.get("dev")})

        # Tasks 16-17: Protect production and staging
        self.client.protect_branch(project_name, "production")
        self.client.protect_branch(project_name, "staging")

        # Log to Delta
        for branch in branches_created:
            self.writer.write_metrics("branch_lifecycle", [{
                "event_id": str(uuid.uuid4())[:8],
                "project_id": project_name,
                "branch_id": branch["branch"],
                "event_type": "created",
                "source_branch": "production" if branch["branch"] != "production" else "",
                "ttl_seconds": branch["ttl"],
                "is_protected": branch["type"] == "protected",
                "actor": "ProvisioningAgent",
                "reason": "Initial project setup",
            }])

        # Emit event for other agents
        self.emit_event(EventType.PROVISIONING_COMPLETE, {
            "project_id": project_name,
            "branches": [b["branch"] for b in branches_created],
        })

        return {
            "project": project_name,
            "domain": domain,
            "environment": environment,
            "branching_pattern": branching_pattern,
            "branches_created": branches_created,
            "tags": default_tags,
            "budget_policy_id": budget_policy_id,
            "status": "provisioned",
        }

    def create_ops_catalog(self) -> dict:
        """
        Create ops_catalog, schemas, and all Delta tables.
        PRD Phase 1, Task 1.1.
        """
        return self.writer.create_ops_catalog_and_schemas()

    # ------------------------------------------------------------------
    # GAP-041: Read Replica Management
    # ------------------------------------------------------------------

    def manage_read_replicas(
        self,
        project_id: str,
        branch_id: str,
        action: str = "list",
        replica_count: Optional[int] = None,
        min_cu: Optional[float] = None,
        max_cu: Optional[float] = None,
    ) -> dict:
        """
        Manage read replicas for a Lakebase branch (GAP-041).

        Read replicas share copy-on-write storage with the primary compute
        and provide horizontal read scaling. Up to 6 replicas per branch.

        Uses the Endpoints API:
            POST   /projects/{id}/branches/{id}/endpoints  (create)
            GET    /projects/{id}/branches/{id}/endpoints   (list)
            DELETE /projects/{id}/branches/{id}/endpoints/{id} (delete)

        Args:
            project_id: Lakebase project ID.
            branch_id: Branch ID (e.g. ``production``).
            action: One of ``list``, ``add``, ``remove``, ``scale``.
            replica_count: Number of replicas to add/remove.
            min_cu: Minimum compute units for autoscaling.
            max_cu: Maximum compute units for autoscaling.

        Returns:
            dict with action result and current replica state.
        """
        MAX_REPLICAS_PER_BRANCH = 6

        base_path = f"projects/{project_id}/branches/{branch_id}/endpoints"

        if action == "list":
            endpoints = self.client.api_get(base_path)
            replicas = [
                ep for ep in endpoints.get("endpoints", [])
                if ep.get("spec", {}).get("type", "").upper() == "READ_REPLICA"
            ]
            return {
                "project_id": project_id,
                "branch_id": branch_id,
                "replica_count": len(replicas),
                "max_replicas": MAX_REPLICAS_PER_BRANCH,
                "replicas": [
                    {
                        "endpoint_id": r.get("name", "").split("/")[-1],
                        "state": r.get("status", {}).get("state", "UNKNOWN"),
                        "min_cu": r.get("spec", {}).get("autoscaling", {}).get("min_cu"),
                        "max_cu": r.get("spec", {}).get("autoscaling", {}).get("max_cu"),
                    }
                    for r in replicas
                ],
            }

        elif action == "add":
            count = replica_count or 1
            current = self.manage_read_replicas(project_id, branch_id, action="list")
            current_count = current["replica_count"]

            if current_count + count > MAX_REPLICAS_PER_BRANCH:
                return {
                    "status": "error",
                    "message": (
                        f"Cannot add {count} replica(s): already have "
                        f"{current_count}/{MAX_REPLICAS_PER_BRANCH}"
                    ),
                }

            created = []
            for i in range(count):
                replica_spec = {
                    "endpoint": {
                        "spec": {
                            "type": "READ_REPLICA",
                            "autoscaling": {
                                "min_cu": min_cu or 0.5,
                                "max_cu": max_cu or 4,
                            },
                        },
                    },
                }
                result = self.client.api_post(base_path, json=replica_spec)
                created.append(result)
                logger.info(
                    f"Created read replica {i+1}/{count} on "
                    f"{project_id}/{branch_id}"
                )

            self.writer.write_metrics("branch_lifecycle", [{
                "event_id": str(uuid.uuid4())[:8],
                "project_id": project_id,
                "branch_id": branch_id,
                "event_type": "replica_added",
                "source_branch": "",
                "ttl_seconds": None,
                "is_protected": False,
                "actor": self.name,
                "reason": f"Added {count} read replica(s)",
                "creator_type": "agent",
            }])

            return {
                "project_id": project_id,
                "branch_id": branch_id,
                "action": "add",
                "replicas_created": count,
                "total_replicas": current_count + count,
                "results": created,
            }

        elif action == "remove":
            current = self.manage_read_replicas(project_id, branch_id, action="list")
            replicas = current.get("replicas", [])

            if not replicas:
                return {"status": "no_replicas", "message": "No read replicas to remove"}

            count = replica_count or 1
            removed = []
            for replica in replicas[:count]:
                ep_id = replica["endpoint_id"]
                self.client.api_delete(f"{base_path}/{ep_id}")
                removed.append(ep_id)
                logger.info(f"Removed read replica {ep_id} from {project_id}/{branch_id}")

            self.writer.write_metrics("branch_lifecycle", [{
                "event_id": str(uuid.uuid4())[:8],
                "project_id": project_id,
                "branch_id": branch_id,
                "event_type": "replica_removed",
                "source_branch": "",
                "ttl_seconds": None,
                "is_protected": False,
                "actor": self.name,
                "reason": f"Removed {len(removed)} read replica(s)",
                "creator_type": "agent",
            }])

            return {
                "project_id": project_id,
                "branch_id": branch_id,
                "action": "remove",
                "replicas_removed": removed,
                "remaining_replicas": len(replicas) - len(removed),
            }

        elif action == "scale":
            if min_cu is None and max_cu is None:
                return {"status": "error", "message": "Provide min_cu and/or max_cu for scale action"}

            current = self.manage_read_replicas(project_id, branch_id, action="list")
            replicas = current.get("replicas", [])
            scaled = []

            for replica in replicas:
                ep_id = replica["endpoint_id"]
                patch_body = {
                    "endpoint": {
                        "spec": {
                            "autoscaling": {
                                "min_cu": min_cu or replica.get("min_cu", 0.5),
                                "max_cu": max_cu or replica.get("max_cu", 4),
                            },
                        },
                    },
                    "update_mask": "spec.autoscaling",
                }
                self.client.api_patch(f"{base_path}/{ep_id}", json=patch_body)
                scaled.append(ep_id)
                logger.info(f"Scaled replica {ep_id} to {min_cu}-{max_cu} CU")

            return {
                "project_id": project_id,
                "branch_id": branch_id,
                "action": "scale",
                "replicas_scaled": scaled,
                "new_min_cu": min_cu,
                "new_max_cu": max_cu,
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    # ------------------------------------------------------------------
    # GAP-041: High Availability Configuration
    # ------------------------------------------------------------------

    def configure_ha(
        self,
        project_id: str,
        branch_id: str,
        enabled: bool = True,
        min_cu: Optional[float] = None,
        max_cu: Optional[float] = None,
    ) -> dict:
        """
        Configure high availability (HA) for a Lakebase branch (GAP-041).

        HA provides automatic failover across availability zones. When HA
        is enabled, a standby compute is maintained in a different AZ.

        Constraints:
            - Scale-to-zero is not available with HA enabled.
            - Secondaries cannot scale below the primary's current CU.

        Uses the Endpoints API to update the primary compute:
            PATCH /projects/{id}/branches/{id}/endpoints/{id}

        Args:
            project_id: Lakebase project ID.
            branch_id: Branch ID (e.g. ``production``).
            enabled: Whether to enable or disable HA.
            min_cu: Optional CU floor (HA disables scale-to-zero).
            max_cu: Optional CU ceiling.

        Returns:
            dict describing the HA configuration.
        """
        base_path = f"projects/{project_id}/branches/{branch_id}/endpoints"

        # Find the primary (read-write) endpoint
        endpoints_resp = self.client.api_get(base_path)
        endpoints = endpoints_resp.get("endpoints", [])
        primary = None
        for ep in endpoints:
            ep_type = ep.get("spec", {}).get("type", "").upper()
            if ep_type in ("PRIMARY", "READ_WRITE", ""):
                primary = ep
                break

        if primary is None:
            return {
                "status": "error",
                "message": f"No primary endpoint found on {project_id}/{branch_id}",
            }

        primary_id = primary.get("name", "").split("/")[-1]
        ep_path = f"{base_path}/{primary_id}"

        # Build the HA patch
        autoscaling_spec = {}
        if min_cu is not None:
            autoscaling_spec["min_cu"] = min_cu
        if max_cu is not None:
            autoscaling_spec["max_cu"] = max_cu
        if enabled:
            autoscaling_spec["scale_to_zero_enabled"] = False

        patch_body = {
            "endpoint": {
                "spec": {
                    "high_availability": enabled,
                },
            },
            "update_mask": "spec.high_availability",
        }

        if autoscaling_spec:
            patch_body["endpoint"]["spec"]["autoscaling"] = autoscaling_spec
            patch_body["update_mask"] += ",spec.autoscaling"

        result = self.client.api_patch(ep_path, json=patch_body)

        action_str = "enabled" if enabled else "disabled"
        logger.info(f"HA {action_str} on {project_id}/{branch_id} (primary: {primary_id})")

        self.writer.write_metrics("branch_lifecycle", [{
            "event_id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "branch_id": branch_id,
            "event_type": f"ha_{action_str}",
            "source_branch": "",
            "ttl_seconds": None,
            "is_protected": True,
            "actor": self.name,
            "reason": f"High availability {action_str}",
            "creator_type": "agent",
        }])

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "high_availability": enabled,
            "primary_endpoint": primary_id,
            "scale_to_zero": not enabled,
            "autoscaling": autoscaling_spec or "unchanged",
            "status": action_str,
        }
