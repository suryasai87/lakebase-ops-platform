"""
GovernanceMixin — RLS, Unity Catalog, AI Agent Branching, Full Provisioning

Contains:
- configure_rls
- setup_unity_catalog_integration
- setup_ai_agent_branching
- provision_with_governance
"""

from __future__ import annotations

import logging

from config.settings import TTL_POLICIES

logger = logging.getLogger("lakebase_ops.provisioning")


class GovernanceMixin:
    """Mixin providing governance, RLS, Unity Catalog, and combined provisioning workflows."""

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
