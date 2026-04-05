"""Tests for ProvisioningAgent: all provisioning tools in mock_mode."""

import pytest

from framework.agent_framework import TaskStatus

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_all_tools_registered(self, registered_provisioning_agent):
        agent = registered_provisioning_agent
        expected_tools = [
            "provision_lakebase_project",
            "create_ops_catalog",
            "create_branch",
            "protect_branch",
            "enforce_ttl_policies",
            "monitor_branch_count",
            "reset_branch_from_parent",
            "apply_schema_migration",
            "capture_schema_diff",
            "test_migration_on_branch",
            "setup_cicd_pipeline",
            "create_branch_on_pr",
            "delete_branch_on_pr_close",
            "configure_rls",
            "setup_unity_catalog_integration",
            "setup_ai_agent_branching",
            "provision_with_governance",
            "connect_and_discover",
            "profile_workload",
            "assess_readiness",
            "generate_migration_blueprint",
        ]
        for tool_name in expected_tools:
            assert tool_name in agent.tools, f"Missing tool: {tool_name}"

    def test_high_risk_tools_flagged(self, registered_provisioning_agent):
        agent = registered_provisioning_agent
        assert agent.tools["configure_rls"].requires_approval is True
        assert agent.tools["configure_rls"].risk_level == "high"
        assert agent.tools["apply_schema_migration"].risk_level == "medium"


# ---------------------------------------------------------------------------
# ProjectMixin tools
# ---------------------------------------------------------------------------


class TestProjectMixin:
    def test_provision_lakebase_project(self, registered_provisioning_agent):
        result = registered_provisioning_agent.provision_lakebase_project(project_name="test-proj", domain="healthcare")
        assert result["status"] == "provisioned"
        assert result["project"] == "test-proj"
        assert result["domain"] == "healthcare"
        # Should create 3 branches: production, staging, development
        branch_names = [b["branch"] for b in result["branches_created"]]
        assert "production" in branch_names
        assert "staging" in branch_names
        assert "development" in branch_names

    def test_provision_writes_branch_lifecycle(self, registered_provisioning_agent, mock_writer):
        registered_provisioning_agent.provision_lakebase_project(project_name="test-proj", domain="retail")
        # Should have written lifecycle records for 3 branches
        log = mock_writer.get_write_log()
        lifecycle_writes = [w for w in log if "branch_lifecycle" in w["table"]]
        assert len(lifecycle_writes) == 3

    def test_create_ops_catalog(self, registered_provisioning_agent):
        result = registered_provisioning_agent.create_ops_catalog()
        assert "tables" in result
        assert "catalog" in result
        assert result["status"].startswith("created")


# ---------------------------------------------------------------------------
# BranchingMixin tools
# ---------------------------------------------------------------------------


class TestBranchingMixin:
    def test_create_branch_default(self, registered_provisioning_agent):
        result = registered_provisioning_agent.create_branch(project_id="proj1", branch_name="feat-login")
        assert "name" in result
        assert result["status"] == "ACTIVE"

    def test_create_branch_with_ttl(self, registered_provisioning_agent):
        result = registered_provisioning_agent.create_branch(
            project_id="proj1",
            branch_name="ci-pr-42",
            branch_type="ci",
            source_branch="staging",
            ttl_seconds=14400,
        )
        assert result["ttl"] == 14400

    def test_create_branch_infers_ttl_from_prefix(self, registered_provisioning_agent):
        # Branch name starts with "ci" -> should pick TTL from TTL_POLICIES
        result = registered_provisioning_agent.create_branch(project_id="proj1", branch_name="ci-pr-99")
        assert result["ttl"] == 14400  # TTL_POLICIES["ci"]

    def test_protect_branch(self, registered_provisioning_agent):
        result = registered_provisioning_agent.protect_branch(project_id="proj1", branch_id="staging")
        assert result["protected"] is True

    def test_enforce_ttl_policies(self, registered_provisioning_agent):
        result = registered_provisioning_agent.enforce_ttl_policies(project_id="proj1")
        assert "branches_deleted" in result
        assert "branches_kept" in result
        assert result["total_active"] > 0

    def test_monitor_branch_count_no_alert(self, registered_provisioning_agent, mock_alerts):
        result = registered_provisioning_agent.monitor_branch_count(project_id="proj1", max_limit=10)
        # Mock returns 3 branches, utilization = 30% -> no alert
        assert result["branch_count"] == 3
        assert result["alert_triggered"] is False

    def test_monitor_branch_count_alert(self, registered_provisioning_agent, mock_alerts):
        result = registered_provisioning_agent.monitor_branch_count(project_id="proj1", max_limit=3)
        # 3 branches / 3 limit = 100% -> alert triggered
        assert result["alert_triggered"] is True
        assert len(mock_alerts.get_alert_history()) > 0

    def test_reset_branch_from_parent(self, registered_provisioning_agent):
        result = registered_provisioning_agent.reset_branch_from_parent(project_id="proj1", branch_id="staging")
        assert result["reset"] is True

    def test_create_branch_on_pr(self, registered_provisioning_agent):
        result = registered_provisioning_agent.create_branch_on_pr(project_id="proj1", pr_number=42)
        assert "ci-pr-42" in str(result.get("name", ""))

    def test_delete_branch_on_pr_close(self, registered_provisioning_agent):
        result = registered_provisioning_agent.delete_branch_on_pr_close(project_id="proj1", pr_number=42)
        assert result["deleted"] is True
        assert result["branch"] == "ci-pr-42"


# ---------------------------------------------------------------------------
# MigrationMixin tools
# ---------------------------------------------------------------------------


class TestMigrationMixin:
    def test_apply_schema_migration_default(self, registered_provisioning_agent):
        result = registered_provisioning_agent.apply_schema_migration(project_id="proj1", branch_id="ci-pr-1")
        assert result["total_applied"] > 0
        assert result["total_rejected"] == 0

    def test_apply_schema_migration_rejects_non_idempotent(self, registered_provisioning_agent):
        result = registered_provisioning_agent.apply_schema_migration(
            project_id="proj1",
            branch_id="ci-pr-1",
            migration_files=[
                "DROP TABLE users;",
                "CREATE TABLE IF NOT EXISTS safe_table (id INT);",
            ],
        )
        assert result["total_rejected"] == 1
        assert result["total_applied"] == 1

    def test_idempotent_ddl_validation(self, registered_provisioning_agent):
        agent = registered_provisioning_agent
        assert agent._is_idempotent_ddl("CREATE TABLE IF NOT EXISTS t (id INT);") is True
        assert agent._is_idempotent_ddl("DROP TABLE users;") is False
        assert agent._is_idempotent_ddl("DROP TABLE IF EXISTS users;") is True
        assert agent._is_idempotent_ddl("CREATE OR REPLACE FUNCTION f() RETURNS void AS $$ $$ LANGUAGE sql;") is True
        assert agent._is_idempotent_ddl("ALTER TABLE t ADD COLUMN IF NOT EXISTS c INT;") is True
        assert agent._is_idempotent_ddl("CREATE TABLE t (id INT);") is False
        assert agent._is_idempotent_ddl("INSERT INTO t VALUES (1);") is True
        assert agent._is_idempotent_ddl("TRUNCATE orders;") is False

    def test_capture_schema_diff(self, registered_provisioning_agent):
        result = registered_provisioning_agent.capture_schema_diff(
            project_id="proj1", source_branch="staging", target_branch="ci-pr-1"
        )
        assert "diff" in result
        assert result["has_changes"] is True

    def test_test_migration_on_branch_9_steps(self, registered_provisioning_agent):
        result = registered_provisioning_agent.test_migration_on_branch(project_id="proj1", pr_number=100)
        assert len(result["steps"]) == 9
        assert result["overall_status"] == "pass"
        assert result["branch_name"] == "ci-pr-100"


# ---------------------------------------------------------------------------
# run_cycle
# ---------------------------------------------------------------------------


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_run_cycle_new_project(self, registered_provisioning_agent):
        results = await registered_provisioning_agent.run_cycle(
            {"project_id": "test-proj", "domain": "test", "is_new_project": True}
        )
        assert len(results) >= 1
        assert all(isinstance(r, TaskStatus) or hasattr(r, "status") for r in results)

    @pytest.mark.asyncio
    async def test_run_cycle_maintenance(self, registered_provisioning_agent):
        results = await registered_provisioning_agent.run_cycle({"project_id": "proj1", "is_new_project": False})
        assert len(results) >= 2  # enforce_ttl + monitor_branch_count

    @pytest.mark.asyncio
    async def test_run_cycle_with_prs(self, registered_provisioning_agent):
        results = await registered_provisioning_agent.run_cycle(
            {
                "project_id": "proj1",
                "is_new_project": False,
                "pending_prs": [
                    {"action": "opened", "number": 10},
                    {"action": "closed", "number": 5},
                ],
            }
        )
        # 2 maintenance + 2 PR actions
        assert len(results) >= 4

    @pytest.mark.asyncio
    async def test_run_cycle_with_migrations(self, registered_provisioning_agent):
        results = await registered_provisioning_agent.run_cycle(
            {
                "project_id": "proj1",
                "is_new_project": False,
                "pending_migrations": [{"pr_number": 77}],
            }
        )
        assert len(results) >= 3  # 2 maintenance + 1 migration
