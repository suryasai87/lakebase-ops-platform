# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Cost Tracker
# MAGIC Runs daily at 6 AM. Tracks Lakebase cost attribution from system.billing.usage.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "hls_amer_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.health_agent import HealthAgent

agent = HealthAgent()

# COMMAND ----------

result = agent.track_cost_attribution()
print(f"Cost tracking: {result.get('status', 'unknown')}")
print(f"Total DBUs: {result.get('total_dbus', 0)}")
print(f"Estimated cost: ${result.get('estimated_cost_usd', 0):.2f}")
