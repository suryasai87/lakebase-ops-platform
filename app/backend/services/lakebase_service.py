"""Lakebase Service: Direct psycopg connection for real-time PG stats."""

import logging
import os
import time

logger = logging.getLogger("lakebase_ops_app.lakebase")

PROJECT_ID = os.getenv("LAKEBASE_PROJECT_ID", "")
ENDPOINT_HOST = os.getenv("LAKEBASE_ENDPOINT_HOST", "")
LAKEBASE_ENDPOINT_NAME = os.getenv("LAKEBASE_ENDPOINT_NAME", "")

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

    # Method 2: Autoscaling Lakebase credential API (/api/2.0/postgres/credentials)
    if LAKEBASE_ENDPOINT_NAME:
        try:
            from databricks.sdk import WorkspaceClient

            client = WorkspaceClient()
            resp = client.api_client.do(
                "POST",
                "/api/2.0/postgres/credentials",
                body={"endpoint": LAKEBASE_ENDPOINT_NAME},
            )
            token = resp.get("token", "")
            if token:
                me = client.current_user.me()
                user = me.user_name if me and me.user_name else "databricks"
                logger.info("Credential obtained via Autoscaling postgres/credentials API")
                _credential_cache.update({"token": token, "user": user, "timestamp": now})
                return token, user
        except Exception as e:
            logger.warning(f"Autoscaling credentials API failed: {e}")

    # Method 3: Provisioned Lakebase credential API (legacy)
    if PROJECT_ID:
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
                logger.info("Credential obtained via Provisioned generate-db-credential API")
                _credential_cache.update({"token": token, "user": user, "timestamp": now})
                return token, user
        except Exception as e:
            logger.warning(f"Provisioned credentials API failed: {e}")

    # Method 4: Generate credential via public SDK postgres API
    # (Replaces private attribute access — uses only public SDK methods)
    try:
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient()
        cred = client.postgres.generate_database_credential()
        token = getattr(cred, "password", "") or getattr(cred, "token", "")
        user = getattr(cred, "username", "databricks") or "databricks"
        if token:
            logger.info("Credential obtained via public SDK postgres.generate_database_credential()")
            _credential_cache.update({"token": token, "user": user, "timestamp": now})
            return token, user
        else:
            logger.warning("Public SDK postgres credential returned empty token")
    except AttributeError:
        logger.warning(
            "SDK does not have postgres.generate_database_credential() — upgrade databricks-sdk to >= 0.81.0"
        )
    except Exception as e:
        logger.warning(f"Public SDK postgres credential failed: {e}")

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

        with (
            psycopg.connect(
                host=ENDPOINT_HOST,
                port=5432,
                dbname="databricks_postgres",
                user=user,
                password=token,
                sslmode="require",
                options="-c statement_timeout=30000",
            ) as conn,
            conn.cursor() as cur,
        ):
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
                "SELECT state, count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' GROUP BY state"
            )
            stats["connection_states"] = {(r[0] or "null"): r[1] for r in cur.fetchall()}

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
                "SELECT relname, n_dead_tup, n_live_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 5"
            )
            stats["top_dead_tuple_tables"] = [{"table": r[0], "dead": r[1], "live": r[2]} for r in cur.fetchall()]

    except Exception as e:
        logger.error(f"Lakebase connection failed: {e}")
        stats["error"] = str(e)
    return stats
