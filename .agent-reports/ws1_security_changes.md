# WS1-SECURITY: Implementation Summary

**Agent:** WS1-SECURITY
**Date:** 2026-04-05
**Branch:** including_serverless_tags
**Gaps Addressed:** GAP-001, GAP-002, GAP-003, GAP-004, GAP-005, GAP-006

---

## GAP-001 (CRITICAL): SQL Injection in Routers

**Problem:** Routers used f-string interpolation to embed user-supplied values (`hours`, `limit`, `days`, `metric_name`) directly into SQL strings, creating SQL injection risk even where allowlist validation existed.

**Changes:**

| File | Change |
|------|--------|
| `app/backend/services/sql_service.py` | Extended `execute_query()` to accept an optional `parameters` list. Parameters are converted to `StatementParameterListItem` objects and passed to the Statement Execution API for safe server-side binding. |
| `app/backend/routers/metrics.py` | Replaced f-string `'{safe_metric}'` and `{safe_hours}` with named parameters `:metric_name` and `:hours`. |
| `app/backend/routers/performance.py` | Replaced `{hours}` and `{limit}` with named parameters `:hours` and `:row_limit`. |
| `app/backend/routers/operations.py` | Replaced `{days}` in vacuum_history with named parameter `:days`. |

**Pattern:** All user-controlled values now use `:param_name` placeholders bound via the Databricks SQL Statement Execution API's native parameterization.

---

## GAP-002 (HIGH): CORS Wildcard Default

**Problem:** When `CORS_ORIGINS` env var was unset, the app defaulted to `allow_origins=["*"]`, allowing any origin to make cross-origin requests.

**Changes:**

| File | Change |
|------|--------|
| `app/backend/main.py` | Changed default from `["*"]` to `[]` (deny-all) when `CORS_ORIGINS` is unset. |
| `app/app.yaml` | Added `CORS_ORIGINS` env var set to `https://*.databricksapps.com`. |

---

## GAP-003 (HIGH): UC Masking Validation

**Problem:** No mechanism existed to validate that Unity Catalog masking policies propagate from parent branches to child branches in Lakebase.

**Changes:**

| File | Change |
|------|--------|
| `agents/provisioning/governance.py` | Added `validate_branch_masking()` method to `GovernanceMixin`. Queries `information_schema.column_masking_policies` on both parent and child branches, compares policy sets, and reports missing/extra policies. |
| `jobs/masking_compliance_job.py` | **New file.** Scheduled job that iterates all active Lakebase branches, runs masking validation via `GovernanceMixin`, and writes results to the `masking_compliance_results` Delta table. Runnable as a Databricks notebook. |

---

## GAP-004 (HIGH): Auth Middleware

**Problem:** FastAPI app had zero authentication middleware, relying entirely on the Databricks Apps proxy without any server-side validation.

**Changes:**

| File | Change |
|------|--------|
| `app/backend/main.py` | Added `DatabricksProxyAuthMiddleware` that validates `X-Forwarded-User` and `X-Forwarded-Email` headers on all non-exempt routes. Returns 401 if headers are missing. Exempts `/api/health`, `/assets`, `/favicon`, and `/`. Supports `LAKEBASE_LOCAL_DEV=1` env var to bypass validation during local development. User identity is attached to `request.state` for downstream use. |

---

## GAP-005 (MEDIUM): Sensitive Data Inventory

**Problem:** No PII/PHI/PCI column inventory existed in the codebase, despite design docs requiring it.

**Changes:**

| File | Change |
|------|--------|
| `config/sensitive_columns.yaml` | **New file.** Defines three classification levels (PII, PHI, PCI) with columns, applicable regulations, masking function names, and descriptions. Includes 17 masking function SQL templates for use with Unity Catalog column masking. |

---

## GAP-006 (MEDIUM): Private SDK Access

**Problem:** `lakebase_service.py` Method 4 accessed private SDK attributes (`client.config.token`, `client.api_client.default_headers`) to extract OAuth tokens, which is fragile and may break on SDK upgrades.

**Changes:**

| File | Change |
|------|--------|
| `app/backend/services/lakebase_service.py` | Replaced Method 4 (private attribute access) with a call to the public `client.postgres.generate_database_credential()` API. Includes graceful fallback with `AttributeError` handling for older SDK versions, with a message to upgrade to `>= 0.81.0`. |

---

## Files Modified

1. `app/backend/services/sql_service.py` — parameterized query support
2. `app/backend/routers/metrics.py` — parameterized SQL
3. `app/backend/routers/performance.py` — parameterized SQL
4. `app/backend/routers/operations.py` — parameterized SQL
5. `app/backend/main.py` — CORS deny-all default + auth middleware
6. `app/app.yaml` — CORS_ORIGINS env var
7. `agents/provisioning/governance.py` — validate_branch_masking()
8. `app/backend/services/lakebase_service.py` — public SDK API only

## Files Created

1. `jobs/masking_compliance_job.py` — scheduled masking compliance checker
2. `config/sensitive_columns.yaml` — PII/PHI/PCI column inventory
