# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Index Analyzer
# MAGIC Runs hourly. Detects unused, bloated, missing, duplicate indexes.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "hls_amer_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.performance_agent import PerformanceAgent
from config.settings import SETTINGS

project_id = dbutils.widgets.get("project_id") if "dbutils" in dir() else SETTINGS.LAKEBASE_PROJECT_ID
branch_id = dbutils.widgets.get("branch_id") if "dbutils" in dir() else "production"

agent = PerformanceAgent()

# COMMAND ----------

result = agent.run_full_index_analysis(project_id=project_id, branch_id=branch_id)
print(f"Index analysis complete: {result.get('total_recommendations', 0)} recommendations")
for category, count in result.get("summary", {}).items():
    print(f"  {category}: {count}")
