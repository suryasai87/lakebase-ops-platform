# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Vacuum Scheduler
# MAGIC Runs daily at 2 AM. Identifies tables needing vacuum and runs VACUUM ANALYZE.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "ops_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.performance_agent import PerformanceAgent
from config import settings

project_id = dbutils.widgets.get("project_id") if "dbutils" in dir() else settings.LAKEBASE_PROJECT_ID
branch_id = dbutils.widgets.get("branch_id") if "dbutils" in dir() else "production"

agent = PerformanceAgent()

# COMMAND ----------

# Identify tables needing vacuum
tables = agent.identify_tables_needing_vacuum(project_id=project_id, branch_id=branch_id)
print(f"Tables needing vacuum: {len(tables.get('tables', []))}")

# COMMAND ----------

# Schedule vacuum analyze for identified tables
result = agent.schedule_vacuum_analyze(project_id=project_id, branch_id=branch_id)
print(f"Vacuum scheduled: {result.get('status', 'unknown')}")
print(f"Tables vacuumed: {result.get('tables_vacuumed', 0)}")
