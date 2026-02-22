"""
Provisioning & DevOps Agent

Automates "Day 0" and "Day 1" tasks:
- Lakebase project creation with full branch hierarchy
- Branch lifecycle management (create, protect, TTL enforce, delete)
- Schema migration workflows (idempotent DDL, 9-step testing)
- CI/CD pipeline generation (GitHub Actions)
- Row-level security setup
- Unity Catalog integration
- Ops catalog and schema creation (PRD Phase 1.1)

Sources:
- Enterprise Lakebase Design Guide: 59 tasks across 12 categories
- PRD: FR-06 (Branch Lifecycle), FR-08 (Schema Migration Testing)
"""

from __future__ import annotations

import logging

from framework.agent_framework import BaseAgent, TaskResult

from .project import ProjectMixin
from .branching import BranchingMixin
from .migration import MigrationMixin
from .cicd import CICDMixin
from .governance import GovernanceMixin

logger = logging.getLogger("lakebase_ops.provisioning")


class ProvisioningAgent(ProjectMixin, BranchingMixin, MigrationMixin, CICDMixin, GovernanceMixin, BaseAgent):
    """
    Provisioning & DevOps Agent — manages Day 0/Day 1 operations.

    Implements all 59 setup tasks from the Enterprise Design Guide
    plus PRD FR-06 and FR-08.
    """

    def __init__(self, lakebase_client, delta_writer, alert_manager):
        super().__init__(
            name="ProvisioningAgent",
            description="Automates Day 0/Day 1 database setup, branching, schema management, CI/CD, and governance",
        )
        self.client = lakebase_client
        self.writer = delta_writer
        self.alerts = alert_manager

    def register_tools(self) -> None:
        """Register all provisioning tools (59 setup tasks + PRD FR-06/FR-08)."""

        # Project Setup (Tasks 1-4)
        self.register_tool("provision_lakebase_project", self.provision_lakebase_project,
                           "Create a new Lakebase project with full branch hierarchy")
        self.register_tool("create_ops_catalog", self.create_ops_catalog,
                           "Create ops_catalog and all operational Delta tables (PRD Phase 1.1)")

        # Branch Management (Tasks 5-15, 16-21, 37-43)
        self.register_tool("create_branch", self.create_branch,
                           "Create a branch with naming conventions and TTL")
        self.register_tool("protect_branch", self.protect_branch,
                           "Mark a branch as protected", risk_level="medium")
        self.register_tool("enforce_ttl_policies", self.enforce_ttl_policies,
                           "Scan and delete branches exceeding TTL", schedule="0 */6 * * *")
        self.register_tool("monitor_branch_count", self.monitor_branch_count,
                           "Alert on branch count approaching limit", schedule="0 */6 * * *")
        self.register_tool("reset_branch_from_parent", self.reset_branch_from_parent,
                           "Sync branch from parent (nightly staging reset)", schedule="0 2 * * *")

        # Schema Migration (Tasks 22-25)
        self.register_tool("apply_schema_migration", self.apply_schema_migration,
                           "Apply idempotent DDL migrations to a branch", risk_level="medium")
        self.register_tool("capture_schema_diff", self.capture_schema_diff,
                           "Generate schema diff between branches")
        self.register_tool("test_migration_on_branch", self.test_migration_on_branch,
                           "Full 9-step migration testing workflow (PRD FR-08)")

        # CI/CD (Tasks 26-32)
        self.register_tool("setup_cicd_pipeline", self.setup_cicd_pipeline,
                           "Generate GitHub Actions YAML for branch automation")
        self.register_tool("create_branch_on_pr", self.create_branch_on_pr,
                           "Create ephemeral branch when PR opened (FR-06)")
        self.register_tool("delete_branch_on_pr_close", self.delete_branch_on_pr_close,
                           "Delete branch when PR closed/merged (FR-06)")

        # RLS (Tasks 33-36)
        self.register_tool("configure_rls", self.configure_rls,
                           "Setup row-level security for multi-tenant isolation", risk_level="high",
                           requires_approval=True)

        # Unity Catalog Integration (Tasks 50-54)
        self.register_tool("setup_unity_catalog_integration", self.setup_unity_catalog_integration,
                           "Align Lakebase with UC governance framework")

        # AI Agent Integration (Tasks 55-57)
        self.register_tool("setup_ai_agent_branching", self.setup_ai_agent_branching,
                           "Configure AI agent branching instructions")

        # Full Provisioning Workflow
        self.register_tool("provision_with_governance", self.provision_with_governance,
                           "Full project setup with all governance and integrations")

    # -----------------------------------------------------------------------
    # Automation Cycle
    # -----------------------------------------------------------------------

    async def run_cycle(self, context: dict = None) -> list[TaskResult]:
        """Execute one full provisioning automation cycle."""
        ctx = context or {}
        results = []

        project_id = ctx.get("project_id", "supply-chain-prod")
        domain = ctx.get("domain", "supply-chain")
        is_new_project = ctx.get("is_new_project", True)

        if is_new_project:
            # Full provisioning workflow
            result = await self.execute_tool(
                "provision_with_governance",
                project_name=project_id,
                domain=domain,
                uc_catalog=ctx.get("catalog", "ops_catalog"),
            )
            results.append(result)
        else:
            # Maintenance cycle: enforce TTLs, monitor branches, reset staging
            result = await self.execute_tool("enforce_ttl_policies", project_id=project_id)
            results.append(result)

            result = await self.execute_tool("monitor_branch_count", project_id=project_id)
            results.append(result)

        # Handle any pending PRs
        pending_prs = ctx.get("pending_prs", [])
        for pr in pending_prs:
            if pr.get("action") == "opened":
                result = await self.execute_tool(
                    "create_branch_on_pr", project_id=project_id, pr_number=pr["number"]
                )
                results.append(result)
            elif pr.get("action") == "closed":
                result = await self.execute_tool(
                    "delete_branch_on_pr_close", project_id=project_id, pr_number=pr["number"]
                )
                results.append(result)

        # Handle pending migrations
        pending_migrations = ctx.get("pending_migrations", [])
        for migration in pending_migrations:
            result = await self.execute_tool(
                "test_migration_on_branch",
                project_id=project_id,
                pr_number=migration.get("pr_number", 999),
                migration_files=migration.get("files"),
            )
            results.append(result)

        return results
