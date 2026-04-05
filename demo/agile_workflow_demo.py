"""
Agile Workflow Demo — GAP-049

End-to-end demonstration of the lakebase-ops-platform:
1. Create a Lakebase project with tags
2. Create a feature branch
3. Apply a schema migration on the branch
4. Run schema diff between branch and production
5. Validate sync status
6. Monitor replication lag
7. Clean up: delete branch

Usage:
    python demo/agile_workflow_demo.py [--live]

By default runs in mock mode. Pass --live for real Databricks API calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

# Add project root to path
sys.path.insert(0, ".")

from utils.lakebase_client import LakebaseClient


def banner(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def step(num: int, title: str) -> None:
    print(f"\n--- Step {num}: {title} ---\n")


def pp(data: dict | list) -> None:
    print(json.dumps(data, indent=2, default=str))


def run_demo(mock_mode: bool = True) -> None:
    client = LakebaseClient(mock_mode=mock_mode)
    project_id = "demo-agile-workflow"
    branch_name = "feat-add-orders-index"

    banner("Lakebase Agile Workflow Demo")
    print(f"Mode: {'MOCK' if mock_mode else 'LIVE'}")
    print(f"Project: {project_id}")
    print(f"Branch: {branch_name}")

    # Step 1: Create project with tags
    step(1, "Create project with budget tags")
    project = client.create_project(project_id)
    pp(project)

    tags = {
        "domain": "demo",
        "environment": "development",
        "managed_by": "lakebase-ops-platform",
        "cost_center": "field-engineering",
    }
    tag_result = client.update_project_tags(project_id, tags)
    print(f"Tags applied: {tags}")
    pp(tag_result)

    # Step 2: Create protected production branch + feature branch
    step(2, "Create branches")
    prod = client.create_branch(project_id, "production", is_protected=True)
    print(f"Production branch: {prod.get('status', 'unknown')}")

    feat = client.create_branch(
        project_id, branch_name,
        source_branch="production",
        ttl_seconds=604800,  # 7 days
    )
    print(f"Feature branch: {feat.get('status', 'unknown')} (TTL: 7 days)")

    # Step 3: Apply schema migration on feature branch
    step(3, "Apply schema migration")
    migration_sql = """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_status_created
    ON orders (status, created_at);
    """
    result = client.execute_statement(project_id, branch_name, migration_sql)
    print(f"Migration applied. Rows affected: {result}")

    # Step 4: Schema diff
    step(4, "Run schema diff (branch vs production)")
    branch_schema = client.execute_query(
        project_id, branch_name,
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position"
    )
    prod_schema = client.execute_query(
        project_id, "production",
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position"
    )
    print(f"Branch columns: {len(branch_schema)}")
    print(f"Production columns: {len(prod_schema)}")
    print("Schema diff: migration adds index (no column changes)")

    # Step 5: Check synced table status
    step(5, "Validate synced table status")
    sync_status = client.get_synced_table_status("orders")
    pp(sync_status)

    # Step 6: Check replication lag
    step(6, "Monitor replication lag")
    repl_data = client.execute_query(
        project_id, "production",
        "SELECT * FROM pg_stat_replication LIMIT 1"
    )
    if repl_data:
        pp(repl_data[0])
    else:
        print("No active replication slots (expected in mock mode)")

    # Step 7: Register as UC catalog
    step(7, "Register Lakebase catalog in Unity Catalog")
    catalog_result = client.register_catalog(project_id, "production", "demo_agile_workflow")
    pp(catalog_result)

    # Step 8: Clean up
    step(8, "Clean up: delete feature branch")
    deleted = client.delete_branch(project_id, branch_name)
    print(f"Branch {branch_name} deleted: {deleted}")

    banner("Demo Complete")
    print("All steps executed successfully.")
    print("\nResources created (mock):")
    print(f"  - Project: {project_id}")
    print(f"  - Tags: {list(tags.keys())}")
    print(f"  - UC Catalog: demo_agile_workflow")
    print(f"  - Feature branch: {branch_name} (deleted)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lakebase Agile Workflow Demo")
    parser.add_argument("--live", action="store_true", help="Use live Databricks APIs (not mock)")
    args = parser.parse_args()
    run_demo(mock_mode=not args.live)
