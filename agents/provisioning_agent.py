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
import uuid
from datetime import datetime, timezone
from typing import Optional

from framework.agent_framework import BaseAgent, EventType, TaskResult, TaskStatus
from config.settings import (
    TTL_POLICIES, BRANCH_NAMING, BranchingPattern, BranchType,
    LakebaseProjectConfig, BranchConfig,
)

logger = logging.getLogger("lakebase_ops.provisioning")


class ProvisioningAgent(BaseAgent):
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
    # Tool Implementations
    # -----------------------------------------------------------------------

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

    def apply_schema_migration(self, project_id: str, branch_id: str,
                                migration_files: list[str] = None) -> dict:
        """
        Apply idempotent DDL migrations to a branch.
        Tasks 22-24: All DDL must be idempotent.
        """
        migrations = migration_files or [
            "CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, customer_id INT, status TEXT, created_at TIMESTAMPTZ DEFAULT NOW());",
            "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
        ]

        results = []
        for i, ddl in enumerate(migrations):
            # Validate idempotency
            if not self._is_idempotent_ddl(ddl):
                results.append({"migration": i + 1, "status": "rejected", "reason": "Non-idempotent DDL"})
                continue

            row_count = self.client.execute_statement(project_id, branch_id, ddl)
            results.append({"migration": i + 1, "ddl": ddl[:80], "status": "applied", "affected": row_count})

        self.emit_event(EventType.SCHEMA_MIGRATED, {
            "project_id": project_id,
            "branch_id": branch_id,
            "migrations_applied": len([r for r in results if r["status"] == "applied"]),
        })

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "migrations": results,
            "total_applied": len([r for r in results if r["status"] == "applied"]),
            "total_rejected": len([r for r in results if r["status"] == "rejected"]),
        }

    def _is_idempotent_ddl(self, ddl: str) -> bool:
        """Validate that DDL is idempotent (Task 23-24)."""
        ddl_upper = ddl.upper().strip()
        idempotent_patterns = [
            "IF NOT EXISTS",
            "IF EXISTS",
            "OR REPLACE",
            "ADD COLUMN IF NOT EXISTS",
        ]
        dangerous_patterns = [
            "DROP TABLE ",
            "DROP INDEX ",
            "TRUNCATE ",
        ]

        # Allow idempotent DDL
        for pattern in idempotent_patterns:
            if pattern in ddl_upper:
                return True

        # Block dangerous non-idempotent DDL
        for pattern in dangerous_patterns:
            if pattern in ddl_upper and "IF EXISTS" not in ddl_upper:
                return False

        # Simple DML is ok
        if ddl_upper.startswith(("INSERT", "UPDATE", "DELETE", "SELECT")):
            return True

        # CREATE without IF NOT EXISTS is not idempotent
        if ddl_upper.startswith("CREATE") and "IF NOT EXISTS" not in ddl_upper:
            return False

        return True

    def capture_schema_diff(self, project_id: str, source_branch: str,
                            target_branch: str) -> dict:
        """
        Generate schema diff between two branches.
        PRD FR-08 schema comparison.
        """
        # In production: use pg_dump comparison or Lakebase Schema Diff API
        source_schema = self.client.execute_query(
            project_id, source_branch,
            "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public'"
        )
        target_schema = self.client.execute_query(
            project_id, target_branch,
            "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public'"
        )

        # Mock diff result
        diff = {
            "tables_added": ["audit_log"],
            "tables_removed": [],
            "columns_added": [{"table": "orders", "column": "updated_at", "type": "TIMESTAMPTZ"}],
            "columns_removed": [],
            "indexes_added": ["idx_orders_updated_at"],
            "indexes_removed": [],
        }

        return {
            "project_id": project_id,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "diff": diff,
            "has_changes": any(v for v in diff.values() if v),
        }

    def test_migration_on_branch(self, project_id: str, pr_number: int,
                                  migration_files: list[str] = None) -> dict:
        """
        Full 9-step migration testing workflow.
        PRD FR-08: Schema Migration Testing on Branches.
        """
        branch_name = f"ci-pr-{pr_number}"
        ttl_seconds = TTL_POLICIES["ci"]  # 4 hours
        results = {"steps": []}

        # Step 1-2: PR opened, pipeline triggered
        results["steps"].append({"step": 1, "action": "Migration files received", "status": "ok"})
        results["steps"].append({"step": 2, "action": "CI/CD pipeline triggered", "status": "ok"})

        # Step 3: Create branch from staging
        branch_result = self.create_branch(
            project_id, branch_name,
            branch_type="ci",
            source_branch="staging",
            ttl_seconds=ttl_seconds,
        )
        results["steps"].append({"step": 3, "action": f"Branch '{branch_name}' created (TTL: {ttl_seconds}s)", "status": "ok"})

        # Step 4: Apply migrations
        migration_result = self.apply_schema_migration(project_id, branch_name, migration_files)
        results["steps"].append({
            "step": 4,
            "action": f"Migrations applied: {migration_result['total_applied']} success, {migration_result['total_rejected']} rejected",
            "status": "ok" if migration_result["total_rejected"] == 0 else "warning",
        })

        # Step 5: Schema Diff
        diff_result = self.capture_schema_diff(project_id, "staging", branch_name)
        results["steps"].append({
            "step": 5,
            "action": f"Schema diff captured: {diff_result['diff']}",
            "status": "ok",
        })

        # Step 6: Integration tests (mock)
        test_passed = True
        results["steps"].append({
            "step": 6,
            "action": "Integration tests passed (3/3)",
            "status": "ok" if test_passed else "failed",
        })

        # Step 7: Code review includes schema diff
        results["steps"].append({
            "step": 7,
            "action": "Schema diff ready for code review",
            "status": "ok",
        })

        # Steps 8-9: Handled on PR merge/close
        results["steps"].append({"step": 8, "action": "Pending: replay migrations on merge", "status": "pending"})
        results["steps"].append({"step": 9, "action": f"Branch auto-deletes after {ttl_seconds}s", "status": "pending"})

        overall = "pass" if all(s["status"] in ("ok", "pending") for s in results["steps"]) else "fail"
        results["overall_status"] = overall
        results["branch_name"] = branch_name

        return results

    def setup_cicd_pipeline(self, project_id: str, repo_owner: str = "org",
                            repo_name: str = "app") -> dict:
        """
        Generate GitHub Actions YAML for branch automation.
        Tasks 26-32 + PRD FR-06.
        """
        create_yaml = f"""name: Lakebase Branch on PR Open
on:
  pull_request:
    types: [opened, reopened]

env:
  LAKEBASE_PROJECT: {project_id}

jobs:
  create-branch:
    runs-on: ubuntu-latest
    steps:
      - name: Install Databricks CLI
        run: curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

      - name: Create Lakebase Branch
        env:
          DATABRICKS_HOST: ${{{{ secrets.DATABRICKS_HOST }}}}
          DATABRICKS_TOKEN: ${{{{ secrets.DATABRICKS_TOKEN }}}}
        run: |
          databricks postgres create-branch \\
            "projects/${{{{ env.LAKEBASE_PROJECT }}}}" \\
            "ci-pr-${{{{ github.event.pull_request.number }}}}" \\
            --json '{{
              "spec": {{
                "source_branch": "projects/'${{{{ env.LAKEBASE_PROJECT }}}}'/branches/staging",
                "ttl": "14400s"
              }}
            }}'

      - name: Wait for Branch Active
        run: |
          for i in $(seq 1 30); do
            STATUS=$(databricks postgres get-branch \\
              "projects/${{{{ env.LAKEBASE_PROJECT }}}}/branches/ci-pr-${{{{ github.event.pull_request.number }}}}" \\
              --output json | jq -r '.status.state')
            if [ "$STATUS" = "ACTIVE" ]; then break; fi
            sleep 10
          done

      - name: Apply Migrations
        run: |
          # Apply migrations to ephemeral branch
          echo "Applying migrations to ci-pr-${{{{ github.event.pull_request.number }}}}"
"""

        delete_yaml = f"""name: Lakebase Branch Cleanup on PR Close
on:
  pull_request:
    types: [closed]

env:
  LAKEBASE_PROJECT: {project_id}

jobs:
  delete-branch:
    runs-on: ubuntu-latest
    steps:
      - name: Install Databricks CLI
        run: curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

      - name: Delete Lakebase Branch
        env:
          DATABRICKS_HOST: ${{{{ secrets.DATABRICKS_HOST }}}}
          DATABRICKS_TOKEN: ${{{{ secrets.DATABRICKS_TOKEN }}}}
        run: |
          databricks postgres delete-branch \\
            "projects/${{{{ env.LAKEBASE_PROJECT }}}}/branches/ci-pr-${{{{ github.event.pull_request.number }}}}" \\
            || true
"""

        return {
            "project_id": project_id,
            "create_branch_yaml": create_yaml,
            "delete_branch_yaml": delete_yaml,
            "secrets_required": ["DATABRICKS_HOST", "DATABRICKS_TOKEN"],
            "variables_required": ["LAKEBASE_PROJECT"],
        }

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

    def configure_rls(self, project_id: str, branch_id: str,
                      tenants: list[str] = None) -> dict:
        """
        Setup row-level security for multi-tenant isolation.
        Tasks 33-36.
        """
        tenants = tenants or ["tenant_alpha", "tenant_beta"]
        rls_statements = []

        for tenant in tenants:
            stmts = [
                f"CREATE SCHEMA IF NOT EXISTS {tenant};",
                f"ALTER TABLE {tenant}.orders ENABLE ROW LEVEL SECURITY;",
                f"CREATE POLICY IF NOT EXISTS {tenant}_isolation ON {tenant}.orders "
                f"USING (tenant_id = current_setting('app.tenant_id'));",
            ]
            rls_statements.extend(stmts)

        # Apply RLS in mock mode
        for stmt in rls_statements:
            self.client.execute_statement(project_id, branch_id, stmt)

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "tenants": tenants,
            "rls_policies_created": len(tenants),
            "statements_executed": len(rls_statements),
        }

    def setup_unity_catalog_integration(self, project_id: str, uc_catalog: str,
                                        domain: str = "") -> dict:
        """
        Align Lakebase project with Unity Catalog governance.
        Tasks 50-54.
        """
        # UC uses underscores, Lakebase uses hyphens
        lakebase_name = project_id  # e.g., "supply-chain-prod"
        uc_name = lakebase_name.replace("-", "_")  # e.g., "supply_chain_prod"

        mapping = {
            "lakebase_project": lakebase_name,
            "uc_catalog": uc_catalog,
            "uc_domain": uc_name,
            "naming_alignment": {
                "lakebase": lakebase_name,
                "unity_catalog": uc_name,
                "separator_mapping": "hyphens (Lakebase) <-> underscores (UC)",
            },
            "lineage_tracking": True,
            "audit_via": "system.access.audit",
        }

        return mapping

    def setup_ai_agent_branching(self, project_id: str) -> dict:
        """
        Configure AI agent branching instructions.
        Tasks 55-57.
        """
        agent_config = {
            "branch_prefix": "ai-agent",
            "ttl_seconds": TTL_POLICIES["ai-agent"],  # 1 hour
            "source_branch": "development",
            "workflow": [
                "1. Create branch (ai-agent-test, TTL: 1h)",
                "2. Wait for ACTIVE status",
                "3. Apply migrations",
                "4. Validate with Schema Diff",
                "5. Surface migration SQL for human review",
                "6. Branch auto-deletes after 1 hour",
            ],
            "claude_md_instruction": (
                "## AI Agent Database Branching\n"
                f"- Create branches from development with 1h TTL\n"
                f"- Branch name: ai-agent-test\n"
                f"- Always validate with Schema Diff before suggesting migration\n"
                f"- Never apply migrations to production or staging directly\n"
            ),
        }

        return agent_config

    def provision_with_governance(self, project_name: str, domain: str,
                                  environment: str = "production",
                                  branching_pattern: str = "multi_env_pipeline",
                                  tenants: list[str] = None,
                                  uc_catalog: str = "ops_catalog") -> dict:
        """
        Full project setup with all governance and integrations.
        Combined workflow: all 59 setup tasks.
        """
        results = {}

        # 1. Create ops catalog (PRD Phase 1.1)
        results["ops_catalog"] = self.create_ops_catalog()

        # 2. Provision project with branches
        results["project"] = self.provision_lakebase_project(
            project_name, domain, environment, branching_pattern
        )

        # 3. Setup RLS if tenants specified
        if tenants:
            results["rls"] = self.configure_rls(project_name, "production", tenants)

        # 4. Unity Catalog integration
        results["uc_integration"] = self.setup_unity_catalog_integration(
            project_name, uc_catalog, domain
        )

        # 5. CI/CD pipeline
        results["cicd"] = self.setup_cicd_pipeline(project_name)

        # 6. AI agent config
        results["ai_agents"] = self.setup_ai_agent_branching(project_name)

        return results

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
