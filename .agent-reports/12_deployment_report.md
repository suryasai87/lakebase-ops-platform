# LakebaseOps Platform - Deployment Report

**Date:** 2026-04-05
**Target:** FEVM HLS AMER Workspace (dev)
**Deployer:** suryasai.turaga@databricks.com

---

## Deployment Summary

Successfully deployed `lakebase-ops-platform` as a **new app** (`lakebase-ops-v2`) to the FEVM HLS AMER workspace using Databricks Asset Bundles.

### Workspace Details

| Field | Value |
|-------|-------|
| Host | https://fe-vm-hls-amer.cloud.databricks.com |
| Profile | FEVMHLS |
| CLI Version | v0.278.0 |
| Bundle Target | dev |
| Bundle Root Path | /Workspace/Users/suryasai.turaga@databricks.com/lakebase-ops-platform |

---

## App Deployment

| Field | Value |
|-------|-------|
| **App Name** | `lakebase-ops-v2` |
| **App URL** | https://lakebase-ops-v2-1602460480284688.aws.databricksapps.com |
| **App Status** | RUNNING |
| **Compute Status** | ACTIVE |
| **Compute Size** | MEDIUM |
| **Port** | 8000 |
| **SP Client ID** | `d0eb8b78-e18c-4b96-ba02-65b727d2c284` |
| **SP ID** | 72006615556599 |
| **Deployment ID** | `01f13112dd871113a1fa6605a3677ea5` |
| **Source Code Path** | `/Workspace/Users/suryasai.turaga@databricks.com/lakebase-ops-platform/files/app` |
| **Created** | 2026-04-05T17:11:20Z |

---

## Scheduled Jobs

All jobs use **serverless compute** (environment-based task execution).

| Job Name | Job ID | Schedule (Cron) | Description |
|----------|--------|-----------------|-------------|
| LakebaseOps - Metric Collector | `810342068717312` | Every 5 min | Persists pg_stat_statements and health metrics to Delta |
| LakebaseOps - Index Analyzer | `722214982605859` | Every hour | Analyzes index health and generates recommendations |
| LakebaseOps - Vacuum Scheduler | `503076690184965` | Daily 2:00 UTC | Scheduled VACUUM ANALYZE replacing pg_cron |
| LakebaseOps - Sync Validator | `613672596244410` | Every 15 min | Validates OLTP-to-OLAP sync completeness and freshness |
| LakebaseOps - Branch Manager | `855317055684842` | Every 6 hours | Enforces TTL policies and monitors branch counts |
| LakebaseOps - Cold Archiver | `890145200992423` | Weekly Sun 3:00 UTC | Archives cold data from Lakebase to Delta Lake |
| LakebaseOps - Cost Tracker | `641844238034040` | Daily 6:00 UTC | Tracks Lakebase costs from system.billing.usage |

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Catalog | `hls_amer_catalog` |
| Schema | `lakebase_ops` |
| Archive Schema | `lakebase_archive` |
| Warehouse ID | `8e4258d7fe74671b` (configured via env vars) |

---

## Changes Made During Deployment

1. **Modified `databricks.yml`:**
   - Changed app name from `lakebase-ops-app` to `lakebase-ops-v2` (to avoid conflict with existing app)
   - Updated `workspace.root_path` to use `${workspace.current_user.userName}` (required for `mode: development`)
   - Removed `artifacts` section (unsupported `type: files` in current CLI version)

2. **Freed app slot:**
   - Deleted unused app `kol-network-mapper` (was STOPPED) to make room under the 100-app workspace limit
   - Also deleted `job-monitor-serverless-tags` (redundant with this deployment)

---

## Existing App (for reference)

| Field | Value |
|-------|-------|
| App Name | `lakebase-ops-app` |
| App URL | https://lakebase-ops-app-1602460480284688.aws.databricksapps.com |
| SP Client ID | `9a911650-ffcf-43e3-8ad4-7f75b8c457db` |

---

## Next Steps

1. **Configure environment variables** - Set `LAKEBASE_PROJECT_ID`, `LAKEBASE_ENDPOINT_HOST`, `SQL_WAREHOUSE_ID`, etc. via the app settings UI or API
2. **Grant SP permissions** - The new service principal (`d0eb8b78-e18c-4b96-ba02-65b727d2c284`) needs:
   - Lakebase credential grant for live stats
   - SQL warehouse `CAN_USE` on warehouse `8e4258d7fe74671b`
   - Unity Catalog access to `hls_amer_catalog.lakebase_ops`
3. **Verify jobs** - The 7 scheduled jobs are created but variables (`project_id`, `endpoint_host`, etc.) need to be set for them to run successfully
4. **Test the app** - Visit https://lakebase-ops-v2-1602460480284688.aws.databricksapps.com
