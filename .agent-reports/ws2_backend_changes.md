# WS2 Backend API Changes Report

**Agent:** WS2-BACKEND-API
**Date:** 2026-04-05
**Branch:** including_serverless_tags

---

## Summary

Implemented fixes for 7 backend gaps identified in the gap analysis (09_gap_analysis.md). All changes follow existing code patterns and conventions.

---

## GAP-007 (HIGH): Broken notebook imports -- FIXED

**Problem:** All 7 job notebook files in `jobs/` imported from non-existent module paths (`agents.performance_agent`, `agents.health_agent`, `agents.provisioning_agent`) that referenced an older flat module structure.

**Fix:** Updated all import statements to match the actual nested package structure:
- `agents.performance_agent.PerformanceAgent` -> `agents.performance.PerformanceAgent`
- `agents.health_agent.HealthAgent` -> `agents.health.HealthAgent`
- `agents.provisioning_agent.ProvisioningAgent` -> `agents.provisioning.ProvisioningAgent`

**Files changed:**
- `jobs/metric_collector_notebook.py`
- `jobs/index_analyzer_notebook.py`
- `jobs/vacuum_scheduler_notebook.py`
- `jobs/sync_validator_notebook.py`
- `jobs/cold_archiver_notebook.py`
- `jobs/cost_tracker_notebook.py`
- `jobs/branch_manager_notebook.py`

---

## GAP-008 (HIGH): Alert channels not implemented -- FIXED

**Problem:** `_send_slack()` built a Slack payload but never sent it (no HTTP call). `_send_pagerduty()` and `_send_email()` only logged.

**Fix:** Implemented actual HTTP calls for all three channels:
- **Slack:** `requests.post()` to configured `webhook_url` with Block Kit payload, 10s timeout, error handling
- **PagerDuty:** `requests.post()` to Events API v2 (`https://events.pagerduty.com/v2/enqueue`) with proper `routing_key`, dedup key, severity mapping, and custom details
- **Email:** SMTP via `smtplib.SMTP` with TLS, configurable host/port/credentials/recipients

All methods gracefully skip if their channel config is missing (with a warning log), and catch/log request failures without raising.

**Files changed:**
- `utils/alerting.py` (added `import requests, json, smtplib, email.mime.*`)

**New dependency:** Added `requests>=2.31.0` to root `requirements.txt`

---

## GAP-009 (HIGH): Pydantic response models -- FIXED

**Problem:** All FastAPI routers returned raw dicts with no type validation or OpenAPI schema.

**Fix:** Created `app/backend/models/` package with Pydantic BaseModel classes for every router's response types, and added `response_model=` to all route decorators.

**New files:**
- `app/backend/models/__init__.py` -- Package exports
- `app/backend/models/health.py` -- `HealthResponse`
- `app/backend/models/agents.py` -- `AgentTool`, `AgentSummary`
- `app/backend/models/metrics.py` -- `MetricSnapshot`, `MetricTrendPoint`
- `app/backend/models/performance.py` -- `SlowQuery`, `RegressionEntry`
- `app/backend/models/indexes.py` -- `IndexRecommendationSummary`
- `app/backend/models/operations.py` -- `VacuumDaySummary`, `SyncTableStatus`, `BranchActivityDay`, `ArchivalDaySummary`
- `app/backend/models/lakebase.py` -- `RealtimeStatsResponse`
- `app/backend/models/jobs.py` -- `JobInfo`, `JobListResponse`, `TriggeredJob`, `JobError`, `TriggerSyncResponse`, `RunStatus`, `PollSyncStatusResponse`

**Routers updated with `response_model`:**
- `app/backend/routers/health.py`
- `app/backend/routers/agents.py`
- `app/backend/routers/metrics.py`
- `app/backend/routers/performance.py`
- `app/backend/routers/indexes.py`
- `app/backend/routers/operations.py`
- `app/backend/routers/lakebase.py`

**Note:** The assessment router (`assessment.py`) already used Pydantic models and was not modified.

---

## GAP-010 (MEDIUM): Missing API pagination -- FIXED

**Problem:** List endpoints returned unbounded result sets with no pagination support.

**Fix:** Added `offset` (default 0, min 0) and `limit` (default 100, min 1, max 500) query parameters to all list endpoints. SQL queries now use parameterized `LIMIT :row_limit OFFSET :row_offset`. Cache keys include pagination params.

**Endpoints updated:**
- `GET /api/metrics/overview` -- added `offset`, `limit`
- `GET /api/indexes/recommendations` -- added `offset`, `limit`
- `GET /api/operations/vacuum` -- added `offset`, `limit`
- `GET /api/operations/branches` -- added `offset`, `limit`
- `GET /api/operations/archival` -- added `offset`, `limit`

**Not paginated (by design):**
- `/api/metrics/trends` -- already bounded by `hours` param + aggregation
- `/api/performance/queries` -- already has `limit` param
- `/api/operations/sync` -- returns only latest per table (small set)

---

## GAP-012 (MEDIUM): Custom exception hierarchy -- FIXED

**Problem:** No custom exceptions; all errors caught as generic `Exception`.

**Fix:** Created `utils/exceptions.py` with a structured hierarchy:

```
LakebaseOpsError (base)
  |-- LakebaseConnectionError  (endpoint unreachable, pool exhausted)
  |-- QueryError               (SQL execution failures)
  |-- AuthError                (OAuth/credential failures)
  |-- ConfigError              (missing env vars, invalid settings)
  |-- AlertDeliveryError       (Slack/PagerDuty/email send failures)
  |-- DeltaWriteError          (Delta Lake table write failures)
```

All exceptions include a `detail` field for structured error context. Specific subclasses carry relevant context attributes (e.g., `endpoint`, `query`, `channel`, `table`, `setting`).

**New file:** `utils/exceptions.py`

---

## GAP-014 (LOW): Duplicate enum -- FIXED

**Problem:** `AlertSeverity` was defined in both `config/settings.py` (unused) and `utils/alerting.py` (used).

**Fix:** Removed the unused `AlertSeverity` enum from `config/settings.py`. The canonical definition remains in `utils/alerting.py` where it is actually consumed.

**File changed:** `config/settings.py`

---

## GAP-015 (LOW): Dependency inconsistencies -- FIXED

**Problem:** Root `requirements.txt` listed both `psycopg[binary]>=3.0` and `psycopg2-binary>=2.9` (only psycopg3 is used). App `requirements.txt` pinned `databricks-sdk>=0.40.0` vs root `>=0.81.0`.

**Fix:**
- Removed `psycopg2-binary>=2.9` from root `requirements.txt`, replaced with `requests>=2.31.0` (needed by alerting)
- Updated `app/requirements.txt` SDK pin from `>=0.40.0` to `>=0.81.0` to match root

**Files changed:**
- `requirements.txt`
- `app/requirements.txt`

---

## Files Not Modified (Security scope -- handled by WS1)

Per instructions, the following security-related files were not touched:
- `app/backend/main.py` (CORS, auth middleware -- GAP-001, GAP-002, GAP-004)
- `app/backend/services/lakebase_service.py` (private SDK access -- GAP-006)
- `app/app.yaml` (env var config -- GAP-002)

---

## Verification Checklist

- [x] All 7 job notebooks import from correct module paths
- [x] Slack alerting makes actual HTTP POST to webhook URL
- [x] PagerDuty alerting calls Events API v2 with proper payload
- [x] Email alerting uses SMTP with TLS
- [x] All alert channels gracefully skip when not configured
- [x] Pydantic response models created for all non-assessment routers
- [x] `response_model` added to all route decorators
- [x] Pagination (`offset`/`limit`) added to 5 list endpoints
- [x] Custom exception hierarchy created with 6 specific error types
- [x] Duplicate `AlertSeverity` enum removed from `config/settings.py`
- [x] `psycopg2-binary` removed from root requirements
- [x] SDK version aligned across requirements files
