"""
ProjectMixin — Project Setup (Tasks 1-4)

Contains:
- provision_lakebase_project
- create_ops_catalog
"""

from __future__ import annotations

import logging
import uuid

from framework.agent_framework import EventType
from config.settings import TTL_POLICIES

logger = logging.getLogger("lakebase_ops.provisioning")


class ProjectMixin:
    """Mixin providing Lakebase project creation and ops catalog setup."""

    def provision_lakebase_project(self, project_name: str, domain: str,
                                   environment: str = "production",
                                   branching_pattern: str = "multi_env_pipeline") -> dict:
        """
        Create a Lakebase project with full branch hierarchy.
        Implements Setup Guide Tasks 1-15.
        """
        logger.info(f"Provisioning project: {project_name}")

        # Task 1: Create project with domain-env naming
        project_result = self.client.create_project(project_name)

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
            "status": "provisioned",
        }

    def create_ops_catalog(self) -> dict:
        """
        Create ops_catalog, schemas, and all Delta tables.
        PRD Phase 1, Task 1.1.
        """
        return self.writer.create_ops_catalog_and_schemas()
