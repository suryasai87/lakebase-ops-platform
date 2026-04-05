"""
Masking Compliance Job — Scheduled validation of UC masking policy propagation.

Iterates over all active Lakebase branches and verifies that masking policies
from the parent branch (typically ``main``) are present on each child branch.
Results are written to the ``masking_compliance_results`` Delta table.

Intended to run as a scheduled Databricks job (e.g., every 6 hours).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger("lakebase_ops.masking_compliance")

CATALOG = os.getenv("OPS_CATALOG", "ops_catalog")
SCHEMA = os.getenv("OPS_SCHEMA", "lakebase_ops")
PROJECT_ID = os.getenv("LAKEBASE_PROJECT_ID", "")


def _get_active_branches(client) -> list[dict]:
    """Retrieve all active branches for the configured project."""
    try:
        resp = client.api_client.do(
            "GET",
            f"/api/2.0/lakebase/projects/{PROJECT_ID}/branches",
        )
        branches = resp.get("branches", [])
        return [b for b in branches if b.get("status", "").upper() == "ACTIVE" and b.get("branch_id") != "main"]
    except Exception as e:
        logger.error(f"Failed to list branches: {e}")
        return []


def _write_results(client, results: list[dict], warehouse_id: str) -> None:
    """Insert compliance results into the Delta table."""
    if not results:
        return

    fqn = f"{CATALOG}.{SCHEMA}.masking_compliance_results"
    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    values_rows = []
    for r in results:
        missing_str = str(r.get("missing_policies", [])).replace("'", "\\'")
        values_rows.append(
            f"('{run_id}', '{r['project_id']}', '{r['branch_id']}', "
            f"'{r['parent_branch_id']}', {r['compliant']}, "
            f"{r['parent_policy_count']}, {r['branch_policy_count']}, "
            f"'{missing_str}', CURRENT_TIMESTAMP)"
        )

    sql = f"""
    INSERT INTO {fqn}
        (run_id, project_id, branch_id, parent_branch_id, compliant,
         parent_policy_count, branch_policy_count, missing_policies,
         validated_at)
    VALUES {", ".join(values_rows)}
    """
    try:
        client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
            wait_timeout="30s",
        )
        logger.info(f"Wrote {len(results)} compliance results (run={run_id})")
    except Exception as e:
        logger.error(f"Failed to write compliance results: {e}")


def run_masking_compliance_check() -> list[dict]:
    """Main entry point: check masking compliance across all active branches.

    Returns:
        List of compliance result dicts, one per branch.
    """
    from databricks.sdk import WorkspaceClient

    # Import governance mixin — we instantiate a minimal wrapper
    from agents.provisioning.governance import GovernanceMixin

    client = WorkspaceClient()
    warehouse_id = os.getenv("SQL_WAREHOUSE_ID", "")

    branches = _get_active_branches(client)
    logger.info(f"Checking masking compliance for {len(branches)} active branches")

    # GovernanceMixin expects self.client — create a lightweight adapter
    class _GovernanceRunner(GovernanceMixin):
        def __init__(self, lakebase_client):
            self.client = lakebase_client

    # Build a simple client adapter that delegates execute_statement
    # to the Lakebase branch endpoint
    class _LakebaseAdapter:
        def __init__(self, ws_client):
            self._ws = ws_client

        def execute_statement(self, project_id: str, branch_id: str, sql: str) -> list[dict]:
            """Execute SQL against a Lakebase branch via the API."""
            try:
                resp = self._ws.api_client.do(
                    "POST",
                    f"/api/2.0/lakebase/projects/{project_id}/branches/{branch_id}/execute",
                    body={"statement": sql},
                )
                return resp.get("results", [])
            except Exception as e:
                logger.warning(f"execute_statement failed on {project_id}/{branch_id}: {e}")
                return []

    adapter = _LakebaseAdapter(client)
    runner = _GovernanceRunner(adapter)

    results = []
    for branch in branches:
        branch_id = branch.get("branch_id", "")
        parent_id = branch.get("parent_branch_id", "main")
        try:
            result = runner.validate_branch_masking(
                project_id=PROJECT_ID,
                branch_id=branch_id,
                parent_branch_id=parent_id,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Compliance check failed for branch {branch_id}: {e}")
            results.append(
                {
                    "project_id": PROJECT_ID,
                    "branch_id": branch_id,
                    "parent_branch_id": parent_id,
                    "compliant": False,
                    "parent_policy_count": -1,
                    "branch_policy_count": -1,
                    "missing_policies": [{"error": str(e)}],
                    "extra_policies": [],
                }
            )

    # Persist results
    if warehouse_id:
        _write_results(client, results, warehouse_id)

    non_compliant = [r for r in results if not r.get("compliant")]
    logger.info(f"Masking compliance complete: {len(results)} branches checked, {len(non_compliant)} non-compliant")
    return results


# Databricks notebook entry point
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_masking_compliance_check()
    for r in results:
        status = "PASS" if r["compliant"] else "FAIL"
        print(f"  [{status}] {r['branch_id']}: {r['branch_policy_count']}/{r['parent_policy_count']} policies")
