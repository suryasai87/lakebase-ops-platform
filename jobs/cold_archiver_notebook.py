# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Cold Data Archiver
# MAGIC Runs weekly Sunday 3 AM. Archives cold data from Lakebase to Delta Lake.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "hls_amer_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.health_agent import HealthAgent
from config.settings import SETTINGS

project_id = dbutils.widgets.get("project_id") if "dbutils" in dir() else SETTINGS.LAKEBASE_PROJECT_ID
branch_id = dbutils.widgets.get("branch_id") if "dbutils" in dir() else "production"
cold_days = int(dbutils.widgets.get("cold_threshold_days") if "dbutils" in dir() else "90")

agent = HealthAgent()

# COMMAND ----------

# Identify cold data
cold = agent.identify_cold_data(
    project_id=project_id, branch_id=branch_id, threshold_days=cold_days
)
print(f"Cold tables found: {len(cold.get('tables', []))}")

# COMMAND ----------

# Archive cold data to Delta
result = agent.archive_cold_data_to_delta(
    project_id=project_id, branch_id=branch_id, threshold_days=cold_days
)
print(f"Archival: {result.get('status', 'unknown')}")
print(f"Rows archived: {result.get('rows_archived', 0)}")
print(f"Bytes reclaimed: {result.get('bytes_reclaimed', 0)}")
