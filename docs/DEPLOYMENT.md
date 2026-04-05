# Deployment Runbook

Target workspace: **FEVM HLS AMER** (`fe-vm-hls-amer.cloud.databricks.com`)

## Prerequisites

- Databricks CLI v0.250+ with DEFAULT profile configured
- Service principal with Workspace Admin permissions
- SQL Warehouse ID and Lakebase project provisioned
- Python 3.11+ with dependencies from `requirements.txt`

## Environment Variables

Set these in `app/app.yaml` or via Databricks Apps resource config:

| Variable | Required | Example |
|----------|----------|---------|
| `DATABRICKS_HOST` | Yes | `fe-vm-hls-amer.cloud.databricks.com` |
| `DATABRICKS_CLIENT_ID` | Yes | SP client ID |
| `DATABRICKS_CLIENT_SECRET` | Yes | SP secret |
| `SQL_WAREHOUSE_ID` | Yes | Serverless warehouse ID |
| `OPS_CATALOG` | Yes | `hls_amer_catalog` |
| `OPS_SCHEMA` | Yes | `lakebase_ops` |
| `LAKEBASE_PROJECT_ID` | Yes | UUID from project creation |
| `LAKEBASE_PROJECT_NAME` | Yes | e.g. `hls-amer-prod` |
| `LAKEBASE_ENDPOINT_HOST` | Yes | Postgres endpoint hostname |
| `CORS_ORIGINS` | Yes | `https://lakebase-ops-app-*.aws.databricksapps.com` |

## Step 1: Create Ops Catalog and Schema

```bash
databricks api post /api/2.0/sql/statements --profile DEFAULT --json '{
  "warehouse_id": "<WAREHOUSE_ID>",
  "statement": "CREATE CATALOG IF NOT EXISTS hls_amer_catalog; CREATE SCHEMA IF NOT EXISTS hls_amer_catalog.lakebase_ops;"
}'
```

## Step 2: Deploy Delta Tables

Run the provisioning agent to create all required Delta tables:

```bash
cd ~/lakebase-ops-platform
python -c "
from agents.provisioning.agent import ProvisioningAgent
agent = ProvisioningAgent(mock_mode=True)
result = agent.create_ops_catalog()
print(result)
"
```

## Step 3: Deploy Databricks Jobs

Upload notebooks and create scheduled jobs:

```bash
databricks workspace import-dir jobs/ /Workspace/Apps/lakebase-ops-app/jobs --profile DEFAULT
python jobs/databricks_job_definitions.py
```

Jobs created:
- `metric_collector` -- every 5 minutes
- `index_analyzer` -- hourly
- `vacuum_scheduler` -- daily at 2 AM
- `sync_validator` -- every 15 minutes
- `branch_manager` -- every 6 hours
- `cold_archiver` -- weekly Sunday 3 AM
- `cost_tracker` -- daily 6 AM

## Step 4: Build Frontend

```bash
cd app/frontend
npm install
npm run build
```

## Step 5: Deploy Databricks App

```bash
cd ~/lakebase-ops-platform
databricks workspace import-dir app/ /Workspace/Apps/lakebase-ops-app --profile DEFAULT
databricks apps deploy lakebase-ops-app --profile DEFAULT
```

The app serves on port **8000** (not 8080). Verify `app.yaml` has `--port 8000`.

## Step 6: Verify

1. Check app health: `GET /health`
2. Check FastAPI docs: `GET /docs`
3. Verify metrics flow: `GET /api/metrics/overview`
4. Verify sync status: `GET /api/operations/sync`
5. Verify lakehouse sync: `GET /api/operations/lakehouse-sync`

## Rollback

If the deployment fails:

```bash
# Revert to previous app version
databricks apps get lakebase-ops-app --profile DEFAULT  # check current state
# Re-upload the previous version from git
git checkout main -- app/
databricks workspace import-dir app/ /Workspace/Apps/lakebase-ops-app --profile DEFAULT
databricks apps deploy lakebase-ops-app --profile DEFAULT
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 502 App Not Available | Wrong port | Ensure `app.yaml` has `--port 8000` |
| Empty metrics | Warehouse not running | Start serverless warehouse |
| Auth errors | Expired SP secret | Rotate via Databricks console |
| CORS errors | Missing `CORS_ORIGINS` | Set in `app.yaml` env section |
