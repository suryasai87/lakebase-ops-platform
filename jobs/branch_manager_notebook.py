# Databricks notebook source
# MAGIC %md
# MAGIC # LakebaseOps - Branch Manager
# MAGIC Runs every 6 hours. Enforces TTL policies and resets staging branch.

# COMMAND ----------

import sys, os
sys.path.insert(0, "/Workspace/Repos/lakebase-ops")
os.environ.setdefault("OPS_CATALOG", "hls_amer_catalog")
os.environ.setdefault("OPS_SCHEMA", "lakebase_ops")

# COMMAND ----------

from agents.provisioning_agent import ProvisioningAgent
from config.settings import SETTINGS

action = dbutils.widgets.get("action") if "dbutils" in dir() else "enforce_ttl"
agent = ProvisioningAgent()

# COMMAND ----------

if action == "enforce_ttl":
    result = agent.enforce_ttl_policies(project_id=SETTINGS.LAKEBASE_PROJECT_ID)
    print(f"TTL enforcement: {result.get('status', 'unknown')}")
    print(f"Branches cleaned: {result.get('branches_deleted', 0)}")
elif action == "reset_staging":
    result = agent.reset_branch_from_parent(
        project_id=SETTINGS.LAKEBASE_PROJECT_ID,
        branch_id="staging",
    )
    print(f"Staging reset: {result.get('status', 'unknown')}")
else:
    print(f"Unknown action: {action}")
