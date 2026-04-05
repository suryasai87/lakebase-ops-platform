"""GAP-023: Migration workflow integration test -- full 9-step flow in mock mode."""

import pytest

from agents.provisioning.agent import ProvisioningAgent
from framework.agent_framework import AgentFramework, EventType
from utils.alerting import AlertManager
from utils.delta_writer import DeltaWriter
from utils.lakebase_client import LakebaseClient


@pytest.fixture
def migration_env():
    """Stand up a full mock environment for migration testing."""
    client = LakebaseClient(workspace_host="test", mock_mode=True)
    writer = DeltaWriter(mock_mode=True)
    alerts = AlertManager(mock_mode=True)
    framework = AgentFramework(workspace_host="test", mock_mode=True)

    agent = ProvisioningAgent(client, writer, alerts)
    framework.register_agent(agent)
    return agent, client, writer, alerts, framework


# ---------------------------------------------------------------------------
# Full 9-step migration workflow
# ---------------------------------------------------------------------------


class TestMigrationWorkflow:
    """Test the 9-step migration testing workflow (PRD FR-08)."""

    def test_full_workflow_passes(self, migration_env):
        agent, _client, _writer, _alerts, _fw = migration_env
        result = agent.test_migration_on_branch(project_id="proj1", pr_number=42)

        # Verify all 9 steps are present
        assert len(result["steps"]) == 9
        assert result["overall_status"] == "pass"
        assert result["branch_name"] == "ci-pr-42"

    def test_step_1_migration_files_received(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step1 = result["steps"][0]
        assert step1["step"] == 1
        assert step1["status"] == "ok"

    def test_step_2_pipeline_triggered(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step2 = result["steps"][1]
        assert step2["step"] == 2
        assert "pipeline" in step2["action"].lower()

    def test_step_3_branch_created(self, migration_env):
        agent, _client, _writer, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 55)
        step3 = result["steps"][2]
        assert step3["step"] == 3
        assert "ci-pr-55" in step3["action"]
        assert "TTL" in step3["action"]

    def test_step_4_migrations_applied(self, migration_env):
        agent, *_ = migration_env
        # Default migration files are all idempotent
        result = agent.test_migration_on_branch("proj1", 1)
        step4 = result["steps"][3]
        assert step4["step"] == 4
        assert step4["status"] == "ok"
        assert "3 success" in step4["action"] or "applied" in step4["action"].lower()

    def test_step_4_with_custom_migrations(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch(
            "proj1",
            1,
            migration_files=[
                "CREATE TABLE IF NOT EXISTS audit_log (id SERIAL);",
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;",
            ],
        )
        step4 = result["steps"][3]
        assert "2 success" in step4["action"]

    def test_step_4_with_rejected_migration(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch(
            "proj1",
            1,
            migration_files=[
                "CREATE TABLE IF NOT EXISTS safe_table (id INT);",
                "DROP TABLE dangerous_table;",  # non-idempotent -> rejected
            ],
        )
        step4 = result["steps"][3]
        assert step4["status"] == "warning"
        assert "1 rejected" in step4["action"]

    def test_step_5_schema_diff(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step5 = result["steps"][4]
        assert step5["step"] == 5
        assert "diff" in step5["action"].lower()

    def test_step_6_integration_tests(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step6 = result["steps"][5]
        assert step6["step"] == 6
        assert step6["status"] == "ok"

    def test_step_7_code_review(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step7 = result["steps"][6]
        assert step7["step"] == 7
        assert "review" in step7["action"].lower()

    def test_steps_8_9_pending(self, migration_env):
        agent, *_ = migration_env
        result = agent.test_migration_on_branch("proj1", 1)
        step8 = result["steps"][7]
        step9 = result["steps"][8]
        assert step8["step"] == 8
        assert step8["status"] == "pending"
        assert step9["step"] == 9
        assert step9["status"] == "pending"


# ---------------------------------------------------------------------------
# Workflow side-effects
# ---------------------------------------------------------------------------


class TestMigrationSideEffects:
    def test_branch_lifecycle_written(self, migration_env):
        agent, _client, writer, *_ = migration_env
        agent.test_migration_on_branch("proj1", 77)
        log = writer.get_write_log()
        lifecycle = [w for w in log if "branch_lifecycle" in w["table"]]
        assert len(lifecycle) >= 1

    def test_schema_migrated_event_dispatched(self, migration_env):
        agent, _client, _writer, _alerts, fw = migration_env
        events_received = []
        fw.subscribe(EventType.SCHEMA_MIGRATED, lambda e: events_received.append(e))
        agent.test_migration_on_branch("proj1", 88)
        assert len(events_received) >= 1
        assert events_received[0].data["project_id"] == "proj1"

    def test_branch_created_event_dispatched(self, migration_env):
        agent, _client, _writer, _alerts, fw = migration_env
        events_received = []
        fw.subscribe(EventType.BRANCH_CREATED, lambda e: events_received.append(e))
        agent.test_migration_on_branch("proj1", 99)
        assert len(events_received) >= 1


# ---------------------------------------------------------------------------
# End-to-end: run_cycle with pending_migrations
# ---------------------------------------------------------------------------


class TestRunCycleWithMigrations:
    @pytest.mark.asyncio
    async def test_cycle_processes_migration(self, migration_env):
        agent, *_ = migration_env
        results = await agent.run_cycle(
            {
                "project_id": "proj1",
                "is_new_project": False,
                "pending_migrations": [{"pr_number": 123}],
            }
        )
        # Should have: enforce_ttl + monitor_branch_count + migration
        assert len(results) >= 3
        migration_result = results[-1]
        assert migration_result.status.value == "success"

    @pytest.mark.asyncio
    async def test_cycle_multiple_migrations(self, migration_env):
        agent, *_ = migration_env
        results = await agent.run_cycle(
            {
                "project_id": "proj1",
                "is_new_project": False,
                "pending_migrations": [
                    {"pr_number": 10},
                    {"pr_number": 11},
                    {"pr_number": 12},
                ],
            }
        )
        # 2 maintenance + 3 migrations
        assert len(results) >= 5


# ---------------------------------------------------------------------------
# Idempotent DDL edge cases
# ---------------------------------------------------------------------------


class TestIdempotentDDLEdgeCases:
    @pytest.fixture
    def agent(self, migration_env):
        return migration_env[0]

    def test_create_without_if_not_exists_rejected(self, agent):
        assert agent._is_idempotent_ddl("CREATE TABLE t (id INT);") is False

    def test_create_with_if_not_exists_accepted(self, agent):
        assert agent._is_idempotent_ddl("CREATE TABLE IF NOT EXISTS t (id INT);") is True

    def test_drop_without_if_exists_rejected(self, agent):
        assert agent._is_idempotent_ddl("DROP TABLE users;") is False

    def test_drop_with_if_exists_accepted(self, agent):
        assert agent._is_idempotent_ddl("DROP TABLE IF EXISTS users;") is True

    def test_drop_index_without_if_exists_rejected(self, agent):
        assert agent._is_idempotent_ddl("DROP INDEX idx_old;") is False

    def test_truncate_rejected(self, agent):
        assert agent._is_idempotent_ddl("TRUNCATE orders;") is False

    def test_or_replace_accepted(self, agent):
        assert agent._is_idempotent_ddl("CREATE OR REPLACE VIEW v AS SELECT 1;") is True

    def test_alter_add_column_if_not_exists_accepted(self, agent):
        assert agent._is_idempotent_ddl("ALTER TABLE t ADD COLUMN IF NOT EXISTS c INT;") is True

    def test_insert_accepted(self, agent):
        assert agent._is_idempotent_ddl("INSERT INTO t VALUES (1);") is True

    def test_update_accepted(self, agent):
        assert agent._is_idempotent_ddl("UPDATE t SET x = 1 WHERE id = 2;") is True

    def test_select_accepted(self, agent):
        assert agent._is_idempotent_ddl("SELECT 1;") is True
