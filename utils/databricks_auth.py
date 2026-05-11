"""Shared Databricks authentication and SQL execution utilities.

Consolidates token acquisition and Statement Execution API calls that were
previously duplicated across lakebase_client.py, delta_writer.py, and
deploy_and_test.py.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time

logger = logging.getLogger("lakebase_ops.auth")

# ---------------------------------------------------------------------------
# Token Management
# ---------------------------------------------------------------------------

_cached_token: str = ""
_token_time: float = 0.0
_TOKEN_TTL_SECONDS: int = 3000  # 50 min (tokens expire at 60 min)


def get_databricks_token(workspace_host: str = "") -> str:
    """Get a Databricks OAuth token, cached for 50 minutes.

    Resolution order:
    1. Cached token (if still valid)
    2. Databricks SDK (works in Apps and notebooks)
    3. Databricks CLI fallback (local development)
    """
    global _cached_token, _token_time

    if _cached_token and (time.time() - _token_time) < _TOKEN_TTL_SECONDS:
        return _cached_token

    # Method 1: Databricks SDK
    token = _token_from_sdk()
    if token:
        _cached_token = token
        _token_time = time.time()
        return _cached_token

    # Method 2: CLI fallback
    token = _token_from_cli(workspace_host)
    if token:
        _cached_token = token
        _token_time = time.time()
        return _cached_token

    logger.error("All token acquisition methods failed")
    return ""


def invalidate_token_cache() -> None:
    """Force re-acquisition on next call."""
    global _cached_token, _token_time
    _cached_token = ""
    _token_time = 0.0


def _token_from_sdk() -> str:
    """Extract token from Databricks SDK WorkspaceClient."""
    try:
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient()
        token = getattr(client.config, "token", None)
        if not token:
            auth_header = client.api_client.default_headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if token:
            logger.debug("Token acquired via Databricks SDK")
            return token
    except Exception as e:
        logger.debug(f"SDK token extraction failed: {e}")
    return ""


def _token_from_cli(workspace_host: str = "") -> str:
    """Extract token from Databricks CLI."""
    try:
        cmd = ["databricks", "auth", "token", "--profile", "DEFAULT"]
        if workspace_host:
            host = workspace_host if workspace_host.startswith("https://") else f"https://{workspace_host}"
            cmd.extend(["--host", host])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # noqa: S603
        if result.returncode == 0:
            data = json.loads(result.stdout)
            token = data.get("access_token", data.get("token_value", ""))
            if token:
                logger.debug("Token acquired via Databricks CLI")
                return token
    except Exception as e:
        logger.debug(f"CLI token extraction failed: {e}")
    return ""


# ---------------------------------------------------------------------------
# SQL Statement Execution API
# ---------------------------------------------------------------------------


def sql_execute(
    workspace_host: str,
    warehouse_id: str,
    statement: str,
    token: str | None = None,
    wait_timeout: str = "30s",
) -> dict:
    """Execute a SQL statement via the Databricks Statement Execution API.

    Args:
        workspace_host: Databricks workspace hostname (no https:// prefix).
        warehouse_id: SQL warehouse ID.
        statement: SQL to execute.
        token: Bearer token. If None, auto-acquires via get_databricks_token().
        wait_timeout: How long the API should wait for results.

    Returns:
        Raw API response dict.
    """
    import requests

    if not token:
        token = get_databricks_token(workspace_host)

    host = workspace_host.rstrip("/")
    if not host.startswith("https://"):
        host = f"https://{host}"

    url = f"{host}/api/2.0/sql/statements"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "warehouse_id": warehouse_id,
        "statement": statement,
        "wait_timeout": wait_timeout,
        "disposition": "INLINE",
        "format": "JSON_ARRAY",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    status = result.get("status", {}).get("state", "")
    if status == "FAILED":
        error = result.get("status", {}).get("error", {})
        logger.error(f"SQL execution failed: {error.get('message', '')}")
    return result


def sql_execute_and_wait(
    workspace_host: str,
    warehouse_id: str,
    statement: str,
    token: str | None = None,
    max_wait: int = 120,
) -> dict:
    """Execute SQL and poll until completion.

    Args:
        workspace_host: Databricks workspace hostname.
        warehouse_id: SQL warehouse ID.
        statement: SQL to execute.
        token: Bearer token. If None, auto-acquires.
        max_wait: Maximum seconds to poll.

    Returns:
        Final API response dict.
    """
    import requests

    result = sql_execute(workspace_host, warehouse_id, statement, token)
    state = result.get("status", {}).get("state", "")
    statement_id = result.get("statement_id", "")

    if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
        return result

    # Poll for completion
    if not token:
        token = get_databricks_token(workspace_host)
    host = workspace_host if workspace_host.startswith("https://") else f"https://{workspace_host}"
    url = f"{host}/api/2.0/sql/statements/{statement_id}"
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + max_wait

    while time.time() < deadline:
        time.sleep(2)
        resp = requests.get(url, headers=headers, timeout=30)
        result = resp.json()
        state = result.get("status", {}).get("state", "")
        if state in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
            return result

    logger.warning(f"SQL statement {statement_id} timed out after {max_wait}s")
    return result


def parse_sql_result(result: dict) -> list[dict]:
    """Parse Statement Execution API response into list of row dicts.

    Args:
        result: Raw API response from sql_execute or sql_execute_and_wait.

    Returns:
        List of dicts keyed by column name.
    """
    state = result.get("status", {}).get("state", "")
    if state != "SUCCEEDED":
        return []

    manifest = result.get("manifest", {})
    columns = [col["name"] for col in manifest.get("schema", {}).get("columns", [])]
    rows = result.get("result", {}).get("data_array", [])
    return [dict(zip(columns, row, strict=False)) for row in rows]
