# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Sync Validator
# MAGIC Runs every 15 minutes. Validates OLTP-to-OLAP sync completeness.

# COMMAND ----------

import os
import sys

sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "ops_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.health import HealthAgent
from config import settings

project_id = dbutils.widgets.get("project_id") if "dbutils" in dir() else settings.LAKEBASE_PROJECT_ID
branch_id = dbutils.widgets.get("branch_id") if "dbutils" in dir() else "production"

agent = HealthAgent()

# COMMAND ----------

result = agent.run_full_sync_validation(project_id=project_id, branch_id=branch_id)
print(f"Sync validation: {result.get('status', 'unknown')}")
print(f"Tables checked: {result.get('tables_checked', 0)}")
print(f"Issues found: {result.get('issues', 0)}")
