"""SQL Service: Execute queries via Databricks SDK Statement Execution API."""

import os
import time
import logging

logger = logging.getLogger("lakebase_ops_app.sql")

WAREHOUSE_ID = os.getenv("SQL_WAREHOUSE_ID", "8e4258d7fe74671b")
CATALOG = os.getenv("OPS_CATALOG", "hls_amer_catalog")
SCHEMA = os.getenv("OPS_SCHEMA", "lakebase_ops")

_client = None

# Simple TTL cache
_cache: dict = {}
_cache_time: dict = {}


def get_client():
    global _client
    if _client is None:
        from databricks.sdk import WorkspaceClient
        _client = WorkspaceClient()
        logger.info("Databricks SDK client initialized (auto-auth)")
    return _client


def execute_query(sql: str) -> list[dict]:
    """Execute SQL via Statement Execution API, return rows as dicts."""
    try:
        client = get_client()
        result = client.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=sql,
            wait_timeout="50s",
        )
        state = result.status.state.value if result.status and result.status.state else "UNKNOWN"
        if state == "SUCCEEDED":
            columns = [c.name for c in result.manifest.schema.columns]
            rows = result.result.data_array if result.result and result.result.data_array else []
            return [dict(zip(columns, row)) for row in rows]
        logger.warning(f"SQL state={state}: {sql[:80]}")
        return []
    except Exception as e:
        logger.error(f"SQL error: {e}")
        return []


def fqn(table: str) -> str:
    """Return fully-qualified table name."""
    return f"{CATALOG}.{SCHEMA}.{table}"


def get_cached(key: str, fetch_func, ttl: int = 60):
    """Simple TTL cache wrapper."""
    now = time.time()
    if key in _cache and (now - _cache_time.get(key, 0)) < ttl:
        return _cache[key]
    data = fetch_func()
    _cache[key] = data
    _cache_time[key] = now
    return data
