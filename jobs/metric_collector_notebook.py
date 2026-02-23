# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Metric Collector
# MAGIC Runs every 5 minutes. Persists pg_stat_statements and health metrics to Delta.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "hls_amer_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.performance_agent import PerformanceAgent
from agents.health_agent import HealthAgent
from config.settings import SETTINGS

project_id = dbutils.widgets.get("project_id") if "dbutils" in dir() else SETTINGS.LAKEBASE_PROJECT_ID
branches = (dbutils.widgets.get("branches") if "dbutils" in dir() else "production").split(",")

perf = PerformanceAgent()
health = HealthAgent()

# COMMAND ----------

# Persist pg_stat_statements for each branch
for branch in branches:
    result = perf.persist_pg_stat_statements(project_id=project_id, branch_id=branch.strip())
    print(f"pg_stat_statements [{branch}]: {result.get('status', 'unknown')}")

# COMMAND ----------

# Monitor system health
for branch in branches:
    result = health.monitor_system_health(project_id=project_id, branch_id=branch.strip())
    print(f"health [{branch}]: {result.get('status', 'unknown')}")
