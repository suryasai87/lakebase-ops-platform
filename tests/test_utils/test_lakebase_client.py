"""Tests for LakebaseClient: mock_mode data generation, connection handling, API methods."""

import time

from utils.lakebase_client import BranchEndpoint, MockConnection, OAuthToken

PROJECT = "test-project-id"
BRANCH = "production"


# ---------------------------------------------------------------------------
# OAuthToken
# ---------------------------------------------------------------------------


class TestOAuthToken:
    def test_new_token_not_expired(self):
        token = OAuthToken(token="abc")
        assert token.is_expired is False
        assert token.needs_refresh is False

    def test_token_expired(self):
        token = OAuthToken(token="abc", issued_at=time.time() - 4000, ttl_seconds=3600)
        assert token.is_expired is True

    def test_token_needs_refresh(self):
        token = OAuthToken(token="abc", issued_at=time.time() - 3100, refresh_at_seconds=3000)
        assert token.needs_refresh is True
        assert token.is_expired is False  # still within TTL


# ---------------------------------------------------------------------------
# BranchEndpoint dataclass
# ---------------------------------------------------------------------------


class TestBranchEndpoint:
    def test_defaults(self):
        ep = BranchEndpoint(project_id="p1", branch_id="b1", endpoint_id="e1", host="host.example.com")
        assert ep.port == 5432
        assert ep.dbname == "databricks_postgres"
        assert ep.sslmode == "require"


# ---------------------------------------------------------------------------
# LakebaseClient mock mode
# ---------------------------------------------------------------------------


class TestClientMockMode:
    def test_init_mock_mode(self, mock_client):
        assert mock_client.mock_mode is True

    def test_get_mock_connection(self, mock_client):
        conn = mock_client.get_connection(PROJECT, BRANCH)
        assert isinstance(conn, MockConnection)

    def test_get_connection_returns_cached(self, mock_client):
        conn1 = mock_client.get_connection(PROJECT, BRANCH)
        conn2 = mock_client.get_connection(PROJECT, BRANCH)
        assert conn1 is conn2

    def test_get_connection_different_branches(self, mock_client):
        conn1 = mock_client.get_connection(PROJECT, "production")
        conn2 = mock_client.get_connection(PROJECT, "staging")
        assert conn1 is not conn2

    def test_execute_query_returns_list(self, mock_client):
        result = mock_client.execute_query(PROJECT, BRANCH, "SELECT * FROM pg_stat_statements")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_execute_statement_returns_rowcount(self, mock_client):
        count = mock_client.execute_statement(PROJECT, BRANCH, "VACUUM ANALYZE orders")
        assert count == 1

    def test_close_all(self, mock_client):
        mock_client.get_connection(PROJECT, BRANCH)
        assert len(mock_client._connections) > 0
        mock_client.close_all()
        assert len(mock_client._connections) == 0
        assert len(mock_client._tokens) == 0

    def test_mock_token_generation(self, mock_client):
        token = mock_client._get_token("test_endpoint")
        assert token.startswith("mock_token_")
        # Second call should return cached
        token2 = mock_client._get_token("test_endpoint")
        assert token == token2


# ---------------------------------------------------------------------------
# Project / Branch management (mock)
# ---------------------------------------------------------------------------


class TestProjectBranchMock:
    def test_create_project(self, mock_client):
        result = mock_client.create_project("my-project")
        assert result["status"] == "ACTIVE"
        assert "my-project" in result["name"]

    def test_create_branch(self, mock_client):
        result = mock_client.create_branch(PROJECT, "dev-branch", source_branch="production")
        assert result["status"] == "ACTIVE"
        assert "dev-branch" in result["name"]

    def test_create_branch_with_ttl(self, mock_client):
        result = mock_client.create_branch(PROJECT, "ci-pr-1", ttl_seconds=14400)
        assert result["ttl"] == 14400

    def test_list_branches(self, mock_client):
        branches = mock_client.list_branches(PROJECT)
        assert isinstance(branches, list)
        assert len(branches) == 3  # production, staging, development
        names = [b["name"] for b in branches]
        assert any("production" in n for n in names)

    def test_delete_branch(self, mock_client):
        assert mock_client.delete_branch(PROJECT, "dev-branch") is True

    def test_protect_branch(self, mock_client):
        assert mock_client.protect_branch(PROJECT, "staging") is True

    def test_reset_branch(self, mock_client):
        assert mock_client.reset_branch(PROJECT, "staging") is True


# ---------------------------------------------------------------------------
# REST API methods (mock)
# ---------------------------------------------------------------------------


class TestAPIMethodsMock:
    def test_api_list_branches(self, mock_client):
        branches = mock_client.api_list_branches(PROJECT)
        assert isinstance(branches, list)
        assert len(branches) == 3

    def test_api_create_branch(self, mock_client):
        result = mock_client.api_create_branch(PROJECT, "api-branch", "production")
        assert result["status"] == "ACTIVE"

    def test_api_delete_branch(self, mock_client):
        result = mock_client.api_delete_branch(PROJECT, "api-branch")
        assert result["deleted"] is True

    def test_api_get_branch(self, mock_client):
        result = mock_client.api_get_branch(PROJECT, "production")
        assert result["status"] == "ACTIVE"

    def test_api_generate_db_credential(self, mock_client):
        cred = mock_client.api_generate_db_credential("projects/p/branches/b/endpoints/e")
        assert cred.startswith("mock_db_cred_")


# ---------------------------------------------------------------------------
# MockConnection data generation
# ---------------------------------------------------------------------------


class TestMockConnection:
    def test_mock_data_generated(self):
        conn = MockConnection(project_id="p", branch_id="b")
        assert "pg_stat_statements" in conn._mock_data
        assert "pg_stat_user_tables" in conn._mock_data
        assert "pg_stat_activity" in conn._mock_data
        assert "pg_stat_database" in conn._mock_data

    def test_execute_mock_pg_stat_statements(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_statements ORDER BY total_exec_time")
        assert len(rows) == 3
        assert "queryid" in rows[0]
        assert "calls" in rows[0]

    def test_execute_mock_pg_stat_statements_info(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_statements_info")
        assert len(rows) == 1
        assert rows[0]["dealloc"] == 42

    def test_execute_mock_pg_stat_user_tables(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_user_tables")
        assert len(rows) == 3
        assert any(r["relname"] == "orders" for r in rows)

    def test_execute_mock_pg_stat_user_indexes(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_user_indexes")
        assert len(rows) == 3

    def test_execute_mock_pg_stat_activity(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_activity")
        assert len(rows) == 3
        states = [r["state"] for r in rows]
        assert "active" in states
        assert "idle" in states

    def test_execute_mock_pg_stat_database(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_database WHERE datname = 'databricks_postgres'")
        assert len(rows) == 1
        assert rows[0]["numbackends"] == 15

    def test_execute_mock_pg_stat_io(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_io")
        assert len(rows) == 2

    def test_execute_mock_pg_stat_wal(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_stat_wal")
        assert len(rows) == 1
        assert rows[0]["wal_bytes"] == 6400000000

    def test_execute_mock_pg_locks(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_locks")
        assert len(rows) == 1

    def test_execute_mock_count_query(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT COUNT(*) FROM orders")
        assert rows[0]["count"] == 5000000

    def test_execute_mock_count_events(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT COUNT(*) FROM events")
        assert rows[0]["count"] == 20000000

    def test_execute_mock_unknown_query(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT something_random FROM somewhere")
        assert rows == [{"result": "mock_ok"}]

    def test_execute_mock_pg_constraint(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_catalog.pg_constraint")
        assert len(rows) == 1
        assert rows[0]["table_name"] == "orders"

    def test_execute_mock_pg_class(self):
        conn = MockConnection(project_id="p", branch_id="b")
        rows = conn.execute_mock("SELECT * FROM pg_catalog.pg_class JOIN pg_attribute")
        assert len(rows) == 10  # 5 orders + 3 events + 2 users columns

    def test_close_noop(self):
        conn = MockConnection(project_id="p", branch_id="b")
        conn.close()  # Should not raise
