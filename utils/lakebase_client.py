"""
LakebaseClient: OAuth-aware PostgreSQL client for Lakebase connections.

Handles:
- OAuth token generation and automatic refresh (50 min / 1h expiry)
- Scale-to-zero graceful degradation
- Connection pooling with recycle at 3600s
- Branch endpoint resolution
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("lakebase_ops.client")


@dataclass
class OAuthToken:
    """OAuth token with expiry tracking."""
    token: str
    issued_at: float = field(default_factory=time.time)
    ttl_seconds: int = 3600  # 1 hour
    refresh_at_seconds: int = 3000  # Refresh at 50 min

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.issued_at) >= self.ttl_seconds

    @property
    def needs_refresh(self) -> bool:
        return (time.time() - self.issued_at) >= self.refresh_at_seconds


@dataclass
class BranchEndpoint:
    """Lakebase branch connection endpoint."""
    project_id: str
    branch_id: str
    endpoint_id: str
    host: str
    port: int = 5432
    dbname: str = "databricks_postgres"
    sslmode: str = "require"


class LakebaseClient:
    """
    Mock-capable client for Lakebase operations.
    Wraps Databricks SDK postgres operations with OAuth token management.
    """

    def __init__(self, workspace_host: str = "", mock_mode: bool = True):
        self.workspace_host = workspace_host
        self.mock_mode = mock_mode
        self._tokens: dict[str, OAuthToken] = {}
        self._connections: dict[str, Any] = {}
        self._workspace_client = None

        if not mock_mode:
            try:
                from databricks.sdk import WorkspaceClient
                self._workspace_client = WorkspaceClient()
            except ImportError:
                logger.warning("databricks-sdk not available, falling back to mock mode")
                self.mock_mode = True

    def _get_token(self, endpoint_name: str) -> str:
        """Get or refresh OAuth token for an endpoint."""
        if endpoint_name in self._tokens:
            token = self._tokens[endpoint_name]
            if not token.needs_refresh:
                return token.token

        if self.mock_mode:
            token = OAuthToken(token=f"mock_token_{int(time.time())}")
        else:
            cred = self._workspace_client.postgres.generate_database_credential(
                endpoint=endpoint_name
            )
            token = OAuthToken(token=cred.token)

        self._tokens[endpoint_name] = token
        logger.debug(f"Token refreshed for {endpoint_name}")
        return token.token

    def get_connection(self, project_id: str, branch_id: str) -> Any:
        """
        Get a database connection to a Lakebase branch.
        Handles OAuth refresh and scale-to-zero gracefully.
        """
        endpoint_name = f"projects/{project_id}/branches/{branch_id}/endpoints/default"
        conn_key = f"{project_id}/{branch_id}"

        if conn_key in self._connections:
            existing = self._connections[conn_key]
            token = self._tokens.get(endpoint_name)
            if token and not token.needs_refresh:
                return existing

        if self.mock_mode:
            conn = MockConnection(project_id=project_id, branch_id=branch_id)
            self._connections[conn_key] = conn
            self._get_token(endpoint_name)
            return conn

        try:
            token = self._get_token(endpoint_name)
            endpoint = self._workspace_client.postgres.get_endpoint(name=endpoint_name)
            import psycopg
            conn = psycopg.connect(
                host=endpoint.status.hosts.host,
                port=5432,
                dbname="databricks_postgres",
                user="databricks",
                password=token,
                sslmode="require",
                options="-c statement_timeout=300000",
            )
            self._connections[conn_key] = conn
            return conn
        except Exception as e:
            if "scale-to-zero" in str(e).lower() or "unavailable" in str(e).lower():
                logger.warning(f"Branch {branch_id} is scaled to zero, skipping")
                return None
            raise

    def execute_query(self, project_id: str, branch_id: str, query: str, params: tuple = None) -> list[dict]:
        """Execute a query against a Lakebase branch and return results as dicts."""
        conn = self.get_connection(project_id, branch_id)
        if conn is None:
            return []

        if self.mock_mode:
            return conn.execute_mock(query)

        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def execute_statement(self, project_id: str, branch_id: str, statement: str, params: tuple = None) -> int:
        """Execute a DDL/DML statement. Returns affected row count."""
        conn = self.get_connection(project_id, branch_id)
        if conn is None:
            return 0

        if self.mock_mode:
            logger.info(f"[MOCK] Executing: {statement[:100]}...")
            return 1

        with conn.cursor() as cur:
            cur.execute(statement, params)
            conn.commit()
            return cur.rowcount

    # --- Lakebase Project/Branch Management ---

    def create_project(self, project_id: str, spec: dict = None) -> dict:
        """Create a new Lakebase project."""
        if self.mock_mode:
            logger.info(f"[MOCK] Creating project: {project_id}")
            return {"name": f"projects/{project_id}", "status": "ACTIVE", "spec": spec or {}}

        result = self._workspace_client.postgres.create_project(
            project_id=project_id, spec=spec
        )
        return {"name": result.name, "status": str(result.status)}

    def create_branch(self, project_id: str, branch_id: str, source_branch: str = "production",
                      ttl_seconds: Optional[int] = None, is_protected: bool = False) -> dict:
        """Create a Lakebase branch with naming conventions and TTL."""
        if self.mock_mode:
            logger.info(f"[MOCK] Creating branch: {branch_id} from {source_branch} (TTL: {ttl_seconds}s)")
            return {
                "name": f"projects/{project_id}/branches/{branch_id}",
                "status": "ACTIVE",
                "source": source_branch,
                "ttl": ttl_seconds,
                "is_protected": is_protected,
            }

        parent = f"projects/{project_id}"
        spec = {"source_branch": f"{parent}/branches/{source_branch}"}
        if ttl_seconds:
            spec["ttl"] = f"{ttl_seconds}s"
        if is_protected:
            spec["is_protected"] = True

        result = self._workspace_client.postgres.create_branch(
            parent=parent, branch_id=branch_id, branch={"spec": spec}
        )
        return {"name": result.name, "status": str(result.status)}

    def list_branches(self, project_id: str) -> list[dict]:
        """List all branches in a project."""
        if self.mock_mode:
            return [
                {"name": f"projects/{project_id}/branches/production", "is_protected": True, "status": "ACTIVE"},
                {"name": f"projects/{project_id}/branches/staging", "is_protected": True, "status": "ACTIVE"},
                {"name": f"projects/{project_id}/branches/development", "is_protected": False, "status": "ACTIVE"},
            ]

        results = self._workspace_client.postgres.list_branches(parent=f"projects/{project_id}")
        return [{"name": b.name, "status": str(b.status)} for b in results]

    def delete_branch(self, project_id: str, branch_id: str) -> bool:
        """Delete a branch. Returns True if successful."""
        if self.mock_mode:
            logger.info(f"[MOCK] Deleting branch: {branch_id}")
            return True

        try:
            self._workspace_client.postgres.delete_branch(
                name=f"projects/{project_id}/branches/{branch_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_id}: {e}")
            return False

    def protect_branch(self, project_id: str, branch_id: str) -> bool:
        """Mark a branch as protected."""
        if self.mock_mode:
            logger.info(f"[MOCK] Protecting branch: {branch_id}")
            return True

        self._workspace_client.postgres.update_branch(
            name=f"projects/{project_id}/branches/{branch_id}",
            update_mask="spec.is_protected",
            spec={"is_protected": True},
        )
        return True

    def reset_branch(self, project_id: str, branch_id: str) -> bool:
        """Reset a branch from its parent (e.g., nightly staging reset)."""
        if self.mock_mode:
            logger.info(f"[MOCK] Resetting branch: {branch_id}")
            return True

        self._workspace_client.postgres.reset_branch(
            name=f"projects/{project_id}/branches/{branch_id}"
        )
        return True

    def close_all(self):
        """Close all connections."""
        for key, conn in self._connections.items():
            try:
                if hasattr(conn, 'close'):
                    conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._tokens.clear()


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self, project_id: str, branch_id: str):
        self.project_id = project_id
        self.branch_id = branch_id
        self._mock_data = self._generate_mock_data()

    def _generate_mock_data(self) -> dict:
        """Generate realistic mock data for all pg_stat views."""
        return {
            "pg_stat_statements": [
                {
                    "queryid": 1001, "query": "SELECT * FROM orders WHERE customer_id = $1",
                    "calls": 15000, "total_exec_time": 45000.0, "mean_exec_time": 3.0,
                    "rows": 75000, "shared_blks_hit": 500000, "shared_blks_read": 5000,
                    "temp_blks_written": 0,
                },
                {
                    "queryid": 1002, "query": "INSERT INTO events (type, data) VALUES ($1, $2)",
                    "calls": 50000, "total_exec_time": 25000.0, "mean_exec_time": 0.5,
                    "rows": 50000, "shared_blks_hit": 200000, "shared_blks_read": 1000,
                    "temp_blks_written": 100,
                },
                {
                    "queryid": 1003, "query": "SELECT o.*, p.name FROM orders o JOIN products p ON o.product_id = p.id WHERE o.status = $1",
                    "calls": 8000, "total_exec_time": 160000.0, "mean_exec_time": 20.0,
                    "rows": 40000, "shared_blks_hit": 300000, "shared_blks_read": 50000,
                    "temp_blks_written": 5000,
                },
            ],
            "pg_stat_user_tables": [
                {
                    "schemaname": "public", "relname": "orders", "n_live_tup": 5000000,
                    "n_dead_tup": 800000, "seq_scan": 150, "idx_scan": 45000,
                    "last_vacuum": "2026-02-20 02:00:00", "last_autovacuum": "2026-02-20 14:00:00",
                    "last_analyze": "2026-02-20 02:00:00", "last_autoanalyze": "2026-02-20 14:00:00",
                },
                {
                    "schemaname": "public", "relname": "events", "n_live_tup": 20000000,
                    "n_dead_tup": 5000000, "seq_scan": 500, "idx_scan": 1000,
                    "last_vacuum": "2026-02-19 02:00:00", "last_autovacuum": "2026-02-19 08:00:00",
                    "last_analyze": "2026-02-19 02:00:00", "last_autoanalyze": "2026-02-19 08:00:00",
                },
                {
                    "schemaname": "public", "relname": "users", "n_live_tup": 100000,
                    "n_dead_tup": 500, "seq_scan": 10, "idx_scan": 80000,
                    "last_vacuum": "2026-02-21 02:00:00", "last_autovacuum": "2026-02-21 06:00:00",
                    "last_analyze": "2026-02-21 02:00:00", "last_autoanalyze": "2026-02-21 06:00:00",
                },
            ],
            "pg_stat_user_indexes": [
                {
                    "schemaname": "public", "relname": "orders", "indexrelname": "idx_orders_customer_id",
                    "idx_scan": 45000, "idx_tup_read": 90000, "index_size_bytes": 104857600,
                    "indisunique": False, "indisprimary": False,
                },
                {
                    "schemaname": "public", "relname": "orders", "indexrelname": "idx_orders_old_status",
                    "idx_scan": 0, "idx_tup_read": 0, "index_size_bytes": 52428800,
                    "indisunique": False, "indisprimary": False,
                },
                {
                    "schemaname": "public", "relname": "events", "indexrelname": "idx_events_type",
                    "idx_scan": 1000, "idx_tup_read": 5000000, "index_size_bytes": 209715200,
                    "indisunique": False, "indisprimary": False,
                },
            ],
            "pg_stat_activity": [
                {"pid": 101, "state": "active", "query": "SELECT 1", "wait_event_type": None, "backend_start": "2026-02-21 10:00:00"},
                {"pid": 102, "state": "idle", "query": "", "wait_event_type": None, "backend_start": "2026-02-21 08:00:00"},
                {"pid": 103, "state": "idle in transaction", "query": "UPDATE orders SET ...", "wait_event_type": "Lock", "backend_start": "2026-02-21 09:30:00"},
            ],
            "pg_stat_database": [
                {
                    "datname": "databricks_postgres", "numbackends": 15, "xact_commit": 500000,
                    "xact_rollback": 50, "blks_read": 100000, "blks_hit": 9900000,
                    "deadlocks": 1, "temp_files": 10, "temp_bytes": 1048576,
                    "datfrozenxid_age": 300000000,
                },
            ],
            "pg_locks": [
                {"pid": 103, "locktype": "relation", "mode": "RowExclusiveLock", "granted": True, "waitstart": None},
            ],
            "row_counts": {"orders": 5000000, "events": 20000000, "users": 100000},
            "max_timestamps": {"orders": "2026-02-21 14:30:00", "events": "2026-02-21 14:31:00"},
        }

    def execute_mock(self, query: str) -> list[dict]:
        """Return mock data based on the query pattern."""
        q = query.lower()
        if "pg_stat_statements" in q:
            return self._mock_data["pg_stat_statements"]
        elif "pg_stat_user_indexes" in q:
            return self._mock_data["pg_stat_user_indexes"]
        elif "pg_stat_user_tables" in q:
            return self._mock_data["pg_stat_user_tables"]
        elif "pg_stat_activity" in q:
            return self._mock_data["pg_stat_activity"]
        elif "pg_stat_database" in q or "pg_database" in q:
            return self._mock_data["pg_stat_database"]
        elif "pg_locks" in q:
            return self._mock_data["pg_locks"]
        elif "count" in q:
            table = "orders"
            for t in ["orders", "events", "users"]:
                if t in q:
                    table = t
                    break
            count = self._mock_data["row_counts"].get(table, 0)
            max_ts = self._mock_data["max_timestamps"].get(table, "2026-02-21 00:00:00")
            return [{"count": count, "max_updated_at": max_ts}]
        else:
            return [{"result": "mock_ok"}]

    def close(self):
        pass
