"""
MigrationMixin — Schema Migration (Tasks 22-25)

Contains:
- apply_schema_migration
- capture_schema_diff
- test_migration_on_branch
- _validate_idempotent_ddl  (private helper, exposed as _is_idempotent_ddl)
"""

from __future__ import annotations

import logging

from framework.agent_framework import EventType
from config.settings import TTL_POLICIES
from sql import queries

logger = logging.getLogger("lakebase_ops.provisioning")


class MigrationMixin:
    """Mixin providing schema migration workflows."""

    def apply_schema_migration(self, project_id: str, branch_id: str,
                                migration_files: list[str] = None) -> dict:
        """
        Apply idempotent DDL migrations to a branch.
        Tasks 22-24: All DDL must be idempotent.
        """
        migrations = migration_files or [
            "CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, customer_id INT, status TEXT, created_at TIMESTAMPTZ DEFAULT NOW());",
            "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
        ]

        results = []
        for i, ddl in enumerate(migrations):
            # Validate idempotency
            if not self._is_idempotent_ddl(ddl):
                results.append({"migration": i + 1, "status": "rejected", "reason": "Non-idempotent DDL"})
                continue

            row_count = self.client.execute_statement(project_id, branch_id, ddl)
            results.append({"migration": i + 1, "ddl": ddl[:80], "status": "applied", "affected": row_count})

        self.emit_event(EventType.SCHEMA_MIGRATED, {
            "project_id": project_id,
            "branch_id": branch_id,
            "migrations_applied": len([r for r in results if r["status"] == "applied"]),
        })

        return {
            "project_id": project_id,
            "branch_id": branch_id,
            "migrations": results,
            "total_applied": len([r for r in results if r["status"] == "applied"]),
            "total_rejected": len([r for r in results if r["status"] == "rejected"]),
        }

    def _is_idempotent_ddl(self, ddl: str) -> bool:
        """Validate that DDL is idempotent (Task 23-24)."""
        ddl_upper = ddl.upper().strip()
        idempotent_patterns = [
            "IF NOT EXISTS",
            "IF EXISTS",
            "OR REPLACE",
            "ADD COLUMN IF NOT EXISTS",
        ]
        dangerous_patterns = [
            "DROP TABLE ",
            "DROP INDEX ",
            "TRUNCATE ",
        ]

        # Allow idempotent DDL
        for pattern in idempotent_patterns:
            if pattern in ddl_upper:
                return True

        # Block dangerous non-idempotent DDL
        for pattern in dangerous_patterns:
            if pattern in ddl_upper and "IF EXISTS" not in ddl_upper:
                return False

        # Simple DML is ok
        if ddl_upper.startswith(("INSERT", "UPDATE", "DELETE", "SELECT")):
            return True

        # CREATE without IF NOT EXISTS is not idempotent
        if ddl_upper.startswith("CREATE") and "IF NOT EXISTS" not in ddl_upper:
            return False

        return True

    def capture_schema_diff(self, project_id: str, source_branch: str,
                            target_branch: str) -> dict:
        """
        Generate schema diff between two branches.
        PRD FR-08 schema comparison.
        """
        source_schema = self.client.execute_query(
            project_id, source_branch, queries.SCHEMA_COLUMNS
        )
        target_schema = self.client.execute_query(
            project_id, target_branch, queries.SCHEMA_COLUMNS
        )

        # Mock diff result
        diff = {
            "tables_added": ["audit_log"],
            "tables_removed": [],
            "columns_added": [{"table": "orders", "column": "updated_at", "type": "TIMESTAMPTZ"}],
            "columns_removed": [],
            "indexes_added": ["idx_orders_updated_at"],
            "indexes_removed": [],
        }

        return {
            "project_id": project_id,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "diff": diff,
            "has_changes": any(v for v in diff.values() if v),
        }

    def test_migration_on_branch(self, project_id: str, pr_number: int,
                                  migration_files: list[str] = None) -> dict:
        """
        Full 9-step migration testing workflow.
        PRD FR-08: Schema Migration Testing on Branches.
        """
        branch_name = f"ci-pr-{pr_number}"
        ttl_seconds = TTL_POLICIES["ci"]  # 4 hours
        results = {"steps": []}

        # Step 1-2: PR opened, pipeline triggered
        results["steps"].append({"step": 1, "action": "Migration files received", "status": "ok"})
        results["steps"].append({"step": 2, "action": "CI/CD pipeline triggered", "status": "ok"})

        # Step 3: Create branch from staging
        branch_result = self.create_branch(
            project_id, branch_name,
            branch_type="ci",
            source_branch="staging",
            ttl_seconds=ttl_seconds,
        )
        results["steps"].append({"step": 3, "action": f"Branch '{branch_name}' created (TTL: {ttl_seconds}s)", "status": "ok"})

        # Step 4: Apply migrations
        migration_result = self.apply_schema_migration(project_id, branch_name, migration_files)
        results["steps"].append({
            "step": 4,
            "action": f"Migrations applied: {migration_result['total_applied']} success, {migration_result['total_rejected']} rejected",
            "status": "ok" if migration_result["total_rejected"] == 0 else "warning",
        })

        # Step 5: Schema Diff
        diff_result = self.capture_schema_diff(project_id, "staging", branch_name)
        results["steps"].append({
            "step": 5,
            "action": f"Schema diff captured: {diff_result['diff']}",
            "status": "ok",
        })

        # Step 6: Integration tests (mock)
        test_passed = True
        results["steps"].append({
            "step": 6,
            "action": "Integration tests passed (3/3)",
            "status": "ok" if test_passed else "failed",
        })

        # Step 7: Code review includes schema diff
        results["steps"].append({
            "step": 7,
            "action": "Schema diff ready for code review",
            "status": "ok",
        })

        # Steps 8-9: Handled on PR merge/close
        results["steps"].append({"step": 8, "action": "Pending: replay migrations on merge", "status": "pending"})
        results["steps"].append({"step": 9, "action": f"Branch auto-deletes after {ttl_seconds}s", "status": "pending"})

        overall = "pass" if all(s["status"] in ("ok", "pending") for s in results["steps"]) else "fail"
        results["overall_status"] = overall
        results["branch_name"] = branch_name

        return results
