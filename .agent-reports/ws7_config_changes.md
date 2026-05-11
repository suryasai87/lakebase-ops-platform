# WS7-CONFIG: Configuration & Packaging Changes

**Agent:** WS7-CONFIG
**Date:** 2026-04-05
**Branch:** including_serverless_tags

---

## GAP-027 (HIGH): Environment Variable Documentation

**Status:** COMPLETE

### Changes
- **`.env.example`** — Rewrote from 24 lines to 82 lines. Now documents every environment variable consumed by the platform across `config/settings.py`, `app/backend/services/`, and `app/backend/routers/`. Variables are grouped by domain (Workspace, Unity Catalog, SQL Warehouse, Lakebase Project, Lakebase Auth, App Config, Job IDs). Each variable indicates whether it is `[REQUIRED]` or has a default.
- **`app/app.yaml`** — Added 6 missing env var entries: `ARCHIVE_SCHEMA`, `LAKEBASE_PROJECT_NAME`, `LAKEBASE_ENDPOINT_NAME`, `LAKEBASE_DEFAULT_BRANCH`, `LAKEBASE_DB_NAME`, `LAKEBASE_JOB_IDS`. These were consumed by backend services but not passed through the app manifest.

### New env vars added to .env.example
| Variable | Source | Previously Documented |
|---|---|---|
| `DATABRICKS_TOKEN` | local dev auth | No |
| `DATABRICKS_CLIENT_ID` | lakebase_service.py | No |
| `DATABRICKS_CLIENT_SECRET` | SP auth | No |
| `ARCHIVE_SCHEMA` | config/settings.py | No |
| `SQL_WAREHOUSE_NAME` | config/settings.py | No |
| `LAKEBASE_ENDPOINT_NAME` | lakebase_service.py | No |
| `LAKEBASE_ENDPOINT_PORT` | config/settings.py | No |
| `LAKEBASE_PG_VERSION` | config/settings.py | No |
| `LAKEBASE_OAUTH_TOKEN` | lakebase_service.py | No |
| `LAKEBASE_DB_USER` | lakebase_service.py | No |
| `CORS_ORIGINS` | backend/main.py | No |
| `LAKEBASE_LOCAL_DEV` | backend/main.py | No |

---

## GAP-028 (HIGH): Databricks Asset Bundle

**Status:** COMPLETE

### Changes
- **`databricks.yml`** — Created at repo root. Follows DABs v2 syntax.

### Contents
- **Bundle variables** (`project_id`, `endpoint_host`, `ops_catalog`, `ops_schema`, `archive_schema`, `warehouse_id`, `notification_email`) — allow per-target overrides without editing job definitions.
- **7 jobs** defined with full config: `metric_collector`, `index_analyzer`, `vacuum_scheduler`, `sync_validator`, `branch_manager` (2-task DAG), `cold_archiver`, `cost_tracker`. All use serverless environments with `psycopg` and `databricks-sdk` dependencies.
- **App deployment** via `resources.apps.lakebase-ops-app`.
- **3 targets** with environment separation (see GAP-031).

### Reference
Used `jobs/databricks_job_definitions.py::generate_databricks_yml()` and `JOB_DEFINITIONS` dict as the source of truth for schedules, timeouts, task keys, and tags. Converted classic cluster config to serverless environment specs.

---

## GAP-029 (MEDIUM): Linting and Formatting Config

**Status:** COMPLETE

### Changes
- **`pyproject.toml`** — Added `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`, `[tool.pytest.ini_options]`, and `[tool.mypy]` sections.
- **`.pre-commit-config.yaml`** — Created with hooks for ruff lint, ruff format, mypy, and general file hygiene (trailing whitespace, end-of-file fixer, YAML/JSON validation, large file guard, debug statement detection).

### Ruff Config Details
- `target-version = "py311"` (upgraded from py310 per gap spec)
- `line-length = 120`
- Lint rules: E, F, W, I (isort), N (naming), UP (pyupgrade), B (bugbear), S (bandit security), T20 (print), SIM (simplify), RUF
- Per-file ignores for tests (`S101`), notebooks/scripts (`T201`)
- Known first-party packages configured for isort

### Mypy Config Details
- `python_version = "3.11"`, `check_untyped_defs = true`, `ignore_missing_imports = true`
- Excludes `app/frontend` and `node_modules`

---

## GAP-030 (MEDIUM): Python Packaging

**Status:** COMPLETE

### Changes
- **`pyproject.toml`** — Added `[build-system]` (hatchling) and `[project]` sections with proper metadata, classifiers, `requires-python = ">=3.11"`, and `[project.optional-dependencies]` for `dev` and `aws` extras.
- **`[tool.hatch.build.targets.wheel]`** — Declares packages: `agents`, `config`, `framework`, `jobs`, `utils`, `app/backend`.

---

## GAP-031 (MEDIUM): Environment Separation

**Status:** COMPLETE

### Changes
- **`databricks.yml` targets** now point to distinct workspace URLs and use different catalog/schema names per environment:

| Target | Workspace | Catalog | Schema |
|--------|-----------|---------|--------|
| `dev` (default) | fe-vm-hls-amer.cloud.databricks.com | `dev_ops_catalog` | `lakebase_ops_dev` |
| `staging` | fe-vm-hls-amer-staging.cloud.databricks.com | `staging_ops_catalog` | `lakebase_ops_staging` |
| `prod` | fe-vm-hls-amer.cloud.databricks.com | `ops_catalog` | `lakebase_ops` |

- `dev` target uses `mode: development` (prefixes resource names with user identity).
- `prod` target uses `run_as.service_principal_name` for least-privilege execution.
- All workspace-specific config flows through bundle `variables`, so jobs reference `${var.project_id}` etc. instead of hardcoded values.

---

## Files Modified / Created

| File | Action | Gap |
|------|--------|-----|
| `.env.example` | Rewritten | GAP-027 |
| `app/app.yaml` | Modified (6 env vars added) | GAP-027 |
| `databricks.yml` | Created | GAP-028, GAP-031 |
| `pyproject.toml` | Rewritten (packaging + tool config) | GAP-029, GAP-030 |
| `.pre-commit-config.yaml` | Created | GAP-029 |

## Files NOT Modified (per rules)
- No Python source code changed
- No frontend files changed
- `jobs/databricks_job_definitions.py` left as-is (still useful as a programmatic reference; `databricks.yml` is now the canonical IaC)
