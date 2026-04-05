# LakebaseOps v2 - Post-Deployment Configuration Report

**Date:** 2026-04-05
**App:** lakebase-ops-v2
**Workspace:** https://fe-vm-hls-amer.cloud.databricks.com
**SP Client ID:** `d0eb8b78-e18c-4b96-ba02-65b727d2c284`

---

## Status Summary

| Task | Status | Notes |
|------|--------|-------|
| TASK 1: Grant catalog access | BLOCKED - Auth expired | SQL GRANT statements ready to execute |
| TASK 2: Grant Lakebase credential | BLOCKED - Auth expired | SQL + REST API commands ready |
| TASK 3: Set environment variables | DONE (app.yaml updated) | Redeploy needed once auth restored |

---

## TASK 1: Grant Catalog Access

**Status:** BLOCKED - Databricks CLI auth token expired. Run `databricks auth login --profile DEFAULT` or `databricks auth login --profile FEVMHLS` to reauthenticate.

Execute these SQL statements on warehouse `4b28691c780d9875` (via SQL Editor in the workspace UI, or via CLI once auth is restored):

```sql
GRANT USE_CATALOG ON CATALOG hls_amer_catalog TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
GRANT USE_SCHEMA ON SCHEMA hls_amer_catalog.lakebase_ops TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
GRANT SELECT ON SCHEMA hls_amer_catalog.lakebase_ops TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
GRANT MODIFY ON SCHEMA hls_amer_catalog.lakebase_ops TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
GRANT CREATE TABLE ON SCHEMA hls_amer_catalog.lakebase_ops TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
```

**CLI alternative (once auth is restored):**

```bash
for stmt in \
  "GRANT USE_CATALOG ON CATALOG hls_amer_catalog TO \`d0eb8b78-e18c-4b96-ba02-65b727d2c284\`" \
  "GRANT USE_SCHEMA ON SCHEMA hls_amer_catalog.lakebase_ops TO \`d0eb8b78-e18c-4b96-ba02-65b727d2c284\`" \
  "GRANT SELECT ON SCHEMA hls_amer_catalog.lakebase_ops TO \`d0eb8b78-e18c-4b96-ba02-65b727d2c284\`" \
  "GRANT MODIFY ON SCHEMA hls_amer_catalog.lakebase_ops TO \`d0eb8b78-e18c-4b96-ba02-65b727d2c284\`" \
  "GRANT CREATE TABLE ON SCHEMA hls_amer_catalog.lakebase_ops TO \`d0eb8b78-e18c-4b96-ba02-65b727d2c284\`"; do
  databricks api post /api/2.0/sql/statements \
    --profile FEVMHLS \
    --json "{\"warehouse_id\": \"4b28691c780d9875\", \"statement\": \"$stmt\", \"wait_timeout\": \"30s\"}"
done
```

---

## TASK 2: Grant Lakebase Credential

**Status:** BLOCKED - Auth expired.

**Credential:** `surya_lakebase_auto` (ID: `83eb266d-27f8-4467-a7df-2b048eff09d7`)
**Grant to SP:** `d0eb8b78-e18c-4b96-ba02-65b727d2c284`

### Option A: SQL GRANT (try first)

```sql
GRANT USE_CONNECTION ON CONNECTION surya_lakebase_auto TO `d0eb8b78-e18c-4b96-ba02-65b727d2c284`;
```

### Option B: REST API (if SQL doesn't work for Lakebase credentials)

```bash
TOKEN=$(databricks auth token --profile FEVMHLS | jq -r .access_token)

curl -X PATCH "https://fe-vm-hls-amer.cloud.databricks.com/api/2.0/postgres/credentials/83eb266d-27f8-4467-a7df-2b048eff09d7" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"allowed_service_principals": ["d0eb8b78-e18c-4b96-ba02-65b727d2c284"]}'
```

### Option C: Workspace UI

1. Go to Catalog > External Data > Connections
2. Find `surya_lakebase_auto`
3. Click Permissions > Grant
4. Add SP `d0eb8b78-e18c-4b96-ba02-65b727d2c284` with USE_CONNECTION

---

## TASK 3: Set Environment Variables

**Status:** DONE - `app/app.yaml` updated with hardcoded values.

### Values Set in app.yaml

| Variable | Value | Source |
|----------|-------|--------|
| `OPS_CATALOG` | `hls_amer_catalog` | User-specified |
| `OPS_SCHEMA` | `lakebase_ops` | User-specified |
| `ARCHIVE_SCHEMA` | `lakebase_archive` | Default |
| `SQL_WAREHOUSE_ID` | `4b28691c780d9875` | User-specified |
| `LAKEBASE_PROJECT_ID` | `83eb266d-27f8-4467-a7df-2b048eff09d7` | From surya_lakebase_auto project (confirmed via other app configs) |
| `LAKEBASE_PROJECT_NAME` | `surya_lakebase_auto` | Credential/project name |
| `LAKEBASE_ENDPOINT_HOST` | `ep-hidden-haze-d2v9brhq.database.us-east-1.cloud.databricks.com` | From surya_lakebase_auto endpoint (confirmed via lakebase-poll-app, space-invaders-lakebase, lakebase_end_to_end_training) |
| `LAKEBASE_ENDPOINT_NAME` | `surya_lakebase_auto` | Endpoint display name (used by autoscaling credential API) |
| `LAKEBASE_DEFAULT_BRANCH` | `production` | Default |
| `LAKEBASE_DB_NAME` | `databricks_postgres` | Default Lakebase DB |
| `LAKEBASE_JOB_IDS` | JSON with all 7 job IDs | From deployment report (#12) |
| `CORS_ORIGINS` | `https://lakebase-ops-v2-1602460480284688.aws.databricksapps.com` | User-specified |

### Changes Made

**File:** `app/app.yaml`
- Replaced all `${VAR}` placeholder references with actual hardcoded values
- Added `LAKEBASE_JOB_IDS` with all 7 job IDs from the deployment
- Set `CORS_ORIGINS` to the specific app URL (was wildcard `*.databricksapps.com`)

### Redeploy Command (once auth is restored)

```bash
databricks auth login --profile FEVMHLS

databricks apps deploy lakebase-ops-v2 \
  --source-code-path /Workspace/Users/suryasai.turaga@databricks.com/.bundle/lakebase-ops-platform/dev/files/app \
  --profile FEVMHLS
```

**Alternative:** Use Asset Bundles to deploy (which also syncs the source code):

```bash
cd ~/lakebase-ops-platform
databricks bundle deploy -t dev --profile FEVMHLS
```

---

## Auth Recovery Steps

The Databricks CLI OAuth token has expired for both the `DEFAULT` and `FEVMHLS` profiles. To restore:

```bash
# Re-authenticate to FEVM HLS AMER workspace
databricks auth login --host https://fe-vm-hls-amer.cloud.databricks.com --profile FEVMHLS

# Verify
databricks auth token --profile FEVMHLS
```

Then execute Tasks 1 and 2 using the commands above, followed by the redeploy for Task 3.

---

## Execution Checklist

Once auth is restored, run in this order:

- [ ] `databricks auth login --profile FEVMHLS`
- [ ] Run 5 GRANT SQL statements (Task 1) via SQL Editor or API
- [ ] Grant Lakebase credential to SP (Task 2) via SQL or REST API
- [ ] Redeploy app: `databricks apps deploy lakebase-ops-v2 --source-code-path /Workspace/Users/suryasai.turaga@databricks.com/.bundle/lakebase-ops-platform/dev/files/app --profile FEVMHLS`
- [ ] Verify app at https://lakebase-ops-v2-1602460480284688.aws.databricksapps.com
- [ ] Test Live Stats page (requires Lakebase credential grant from Task 2)
