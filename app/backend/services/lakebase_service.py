"""Lakebase Service: Direct psycopg connection for real-time PG stats."""

import os
import time
import logging

logger = logging.getLogger("lakebase_ops_app.lakebase")

PROJECT_ID = os.getenv("LAKEBASE_PROJECT_ID", "83eb266d-27f8-4467-a7df-2b048eff09d7")
ENDPOINT_HOST = os.getenv(
    "LAKEBASE_ENDPOINT_HOST",
    "ep-hidden-haze-d2v9brhq.database.us-east-1.cloud.databricks.com",
)

_credential_cache: dict = {"token": None, "user": None, "timestamp": 0.0}


def _get_db_credential() -> tuple:
    """Get Lakebase credential (password, user). Tries multiple methods."""
    now = time.time()
    if _credential_cache["token"] and (now - _credential_cache["timestamp"]) < 3000:
        return _credential_cache["token"], _credential_cache["user"]

    # Method 1: Explicit env var override (highest priority when set in app.yaml)
    token = os.getenv("LAKEBASE_OAUTH_TOKEN", "")
    user = os.getenv("LAKEBASE_DB_USER", "databricks")
    if token:
        logger.info("Using LAKEBASE_OAUTH_TOKEN env var (explicit override)")
        _credential_cache.update({"token": token, "user": user, "timestamp": now})
        return token, user

    # Method 2: generate-db-credential API (works for provisioned Lakebase)
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient()
        resp = client.api_client.do(
            "POST",
            "/api/2.0/lakebase/credentials/generate-db-credential",
            body={"project_id": PROJECT_ID},
        )
        token = resp.get("credential", {}).get("password", "")
        user = resp.get("credential", {}).get("username", "databricks")
        if token:
            logger.info("Credential obtained via generate-db-credential API")
            _credential_cache.update({"token": token, "user": user, "timestamp": now})
            return token, user
    except Exception as e:
        logger.warning(f"generate-db-credential API failed: {e}")

    # Method 3: Use SP's own OAuth token (works for autoscaling Lakebase)
    try:
        from databricks.sdk import WorkspaceClient
        client = WorkspaceClient()
        token = None
        try:
            token = client.config.token
        except Exception:
            pass
        if not token:
            try:
                headers = client.api_client.default_headers
                auth = headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    token = auth[7:]
            except Exception:
                pass
        if not token:
            try:
                resp = client.current_user.me()
                token = getattr(client.config, '_token', None)
                if not token and hasattr(client.config, '_header_factory'):
                    hdr = client.config._header_factory()
                    auth = hdr.get("Authorization", "")
                    if auth.startswith("Bearer "):
                        token = auth[7:]
            except Exception:
                pass
        if token:
            sp_id = os.getenv("DATABRICKS_CLIENT_ID", "")
            user = sp_id if sp_id else "databricks"
            logger.info(f"Using SP OAuth token for Lakebase auth (user={user}, token_len={len(token)})")
            _credential_cache.update({"token": token, "user": user, "timestamp": now})
            return token, user
        else:
            logger.warning("SP OAuth token: all extraction methods returned empty")
    except Exception as e:
        logger.warning(f"SP OAuth token extraction failed: {e}")

    return "", "databricks"


def get_realtime_stats() -> dict:
    """Query pg_stat views directly from Lakebase for real-time metrics."""
    stats: dict = {"timestamp": time.time()}
    try:
        import psycopg

        token, user = _get_db_credential()
        if not token:
            return {"error": "No Lakebase credential available"}

        logger.info(f"Connecting to Lakebase: host={ENDPOINT_HOST}, user={user}")

        with psycopg.connect(
            host=ENDPOINT_HOST,
            port=5432,
            dbname="databricks_postgres",
            user=user,
            password=token,
            sslmode="require",
            options="-c statement_timeout=30000",
        ) as conn:
            with conn.cursor() as cur:
                # pg_stat_database
                cur.execute(
                    "SELECT numbackends, blks_read, blks_hit, deadlocks, temp_files "
                    "FROM pg_stat_database WHERE datname = 'databricks_postgres'"
                )
                row = cur.fetchone()
                if row:
                    stats["connections"] = row[0]
                    blks_hit, blks_read = row[2], row[1]
                    total = blks_hit + blks_read
                    stats["cache_hit_ratio"] = round(blks_hit / total, 4) if total > 0 else 1.0
                    stats["deadlocks"] = row[3]
                    stats["temp_files"] = row[4]

                # pg_stat_activity summary
                cur.execute(
                    "SELECT state, count(*) FROM pg_stat_activity "
                    "WHERE backend_type = 'client backend' GROUP BY state"
                )
                stats["connection_states"] = {
                    (r[0] or "null"): r[1] for r in cur.fetchall()
                }

                # pg_stat_wal
                try:
                    cur.execute("SELECT wal_bytes, wal_buffers_full FROM pg_stat_wal")
                    wal = cur.fetchone()
                    if wal:
                        stats["wal_bytes"] = wal[0]
                        stats["wal_buffers_full"] = wal[1]
                except Exception:
                    stats["wal_bytes"] = 0
                    stats["wal_buffers_full"] = 0

                # Top dead tuple tables
                cur.execute(
                    "SELECT relname, n_dead_tup, n_live_tup "
                    "FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 5"
                )
                stats["top_dead_tuple_tables"] = [
                    {"table": r[0], "dead": r[1], "live": r[2]} for r in cur.fetchall()
                ]

    except Exception as e:
        logger.error(f"Lakebase connection failed: {e}")
        stats["error"] = str(e)
    return stats
