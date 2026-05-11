# Implementation Plan: LakebaseOps Platform v2.0

**Generated:** 2026-04-05
**Source Reports:** 00 (Lakebase API Docs), 01 (Repo Architecture), 02 (Code Quality), 04 (Slides Analysis), 06 (Design Doc), 07 (Jira Epic), 08 (Jira Board)
**Target Branch:** `feat/v2-platform-upgrade`
**Total Workstreams:** 8 (parallel)

---

## Table of Contents

1. [Overview](#overview)
2. [WS1-SECURITY](#ws1-security)
3. [WS2-BACKEND-API](#ws2-backend-api)
4. [WS3-FRONTEND](#ws3-frontend)
5. [WS4-AGENTS](#ws4-agents)
6. [WS5-TESTING](#ws5-testing)
7. [WS6-CICD](#ws6-cicd)
8. [WS7-CONFIG](#ws7-config)
9. [WS8-DATA](#ws8-data)
10. [Cross-Workstream Dependencies](#cross-workstream-dependencies)
11. [CHANGELOG Entry](#changelog-entry)
12. [Commit Messages](#commit-messages)

---

## Overview

This plan addresses all gaps identified across the 8 analysis reports. Every task traces back to at least one of: code quality findings (Report 02), slides vision (Report 04), design doc requirements (Report 06), Jira tickets (Reports 07-08), or Lakebase 2026 API capabilities (Report 00).

**Aggregate Estimates:**

| Workstream | Files to Create | Files to Modify | Est. Lines (New) | Priority |
|------------|----------------|----------------|------------------|----------|
| WS1-SECURITY | 3 | 5 | ~550 | P0 |
| WS2-BACKEND-API | 6 | 4 | ~1,800 | P0 |
| WS3-FRONTEND | 8 | 3 | ~2,400 | P1 |
| WS4-AGENTS | 5 | 4 | ~2,200 | P1 |
| WS5-TESTING | 14 | 2 | ~3,500 | P0 |
| WS6-CICD | 7 | 1 | ~1,200 | P1 |
| WS7-CONFIG | 4 | 3 | ~800 | P0 |
| WS8-DATA | 3 | 2 | ~600 | P0 |
| **Totals** | **50** | **24** | **~13,050** | -- |

---

## WS1-SECURITY

**Scope:** Fix SQL injection in metrics.py, add input validation across all routers, create custom exception hierarchy, tighten CORS, add Pydantic response models.

**Traces to:** Report 02 Section 5.1 (SQL injection -- HIGH SEVERITY), Section 5.3 (CORS), Section 2.2 (no custom exceptions), Section 8.4 (missing Pydantic models).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `app/backend/exceptions.py` | Custom exception hierarchy: `LakebaseOpsError` base, `QueryError`, `AuthError`, `ValidationError`, `ConnectionError`, `RateLimitError`. FastAPI exception handlers registered in `main.py`. | ~80 |
| 2 | `app/backend/models/responses.py` | Pydantic response models for all router endpoints: `MetricOverview`, `MetricTrend`, `PerformanceQuery`, `IndexRecommendation`, `OperationStatus`, `HealthStatus`, `AgentSummary`, `LakebaseRealtime`. Enables OpenAPI schema generation and response validation. | ~200 |
| 3 | `app/backend/middleware/input_validation.py` | Shared validation utilities: `validate_metric_name()`, `validate_table_name()`, `sanitize_integer_param()`. Centralized allowlist enforcement. | ~100 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `app/backend/routers/metrics.py` | **CRITICAL:** Replace string interpolation `'{safe_metric}'` on line 61 with parameterized query. The `ALLOWED_METRICS` allowlist already exists (lines 8-14) and is checked (line 46-47), but the SQL still uses f-string interpolation. Switch to SQL parameter binding via the Databricks SQL Statement API's `parameters` field. Also add `-> MetricOverview` / `-> MetricTrend` return types. | P0 |
| 2 | `app/backend/routers/performance.py` | Replace `INTERVAL {hours} HOURS` and `LIMIT {limit}` f-string interpolation (lines 26-28) with parameterized queries. Add Pydantic response models. | P0 |
| 3 | `app/backend/routers/operations.py` | Replace `INTERVAL {days} DAYS` interpolation (line 22) with parameter binding. Add response models. | P0 |
| 4 | `app/backend/main.py` | (a) Change CORS `allow_origins=["*"]` (line ~37) to `allow_origins=["https://*.databricksapps.com", "http://localhost:5173"]`. (b) Register custom exception handlers from `exceptions.py`. (c) Add request validation middleware. | P1 |
| 5 | `app/backend/routers/health.py` | Log the exception in the catch block instead of silently returning `{"status": "degraded"}`. Use custom `QueryError`. | P1 |

### New Dependencies

None -- uses built-in FastAPI/Pydantic features.

### Estimates

- **Files:** 3 create + 5 modify = 8 total
- **New lines:** ~550
- **Effort:** 1-2 days

### Priority Order (within workstream)

1. Fix SQL injection in `metrics.py` (P0 -- exploitable)
2. Fix SQL injection in `performance.py` and `operations.py` (P0)
3. Create `exceptions.py` and register handlers (P1)
4. Create `models/responses.py` and apply to all routers (P1)
5. Tighten CORS in `main.py` (P1)
6. Create `middleware/input_validation.py` (P2)

### Dependencies on Other Workstreams

- **None** -- WS1 can start immediately and should be the first to merge.
- WS5-TESTING depends on WS1: tests will import the new exception hierarchy.

---

## WS2-BACKEND-API

**Scope:** New FastAPI endpoints for branch lifecycle (create/delete linked to PRs), schema diff API, Lakebase API integration for 2026 features (HA, OAuth roles, budget policies/tags), cost attribution endpoint. Addresses FEIP-5271 (sync monitor) and FEIP-1444 (cost attribution).

**Traces to:** Report 04 Sections 9.1-9.2 (branch lifecycle, CI/CD), Report 06 Part 2 (branching design), Report 07 (LADT workstreams), Report 08 (FEIP-5271 Critical, FEIP-1444 Blocked), Report 00 Section 15 (2026 features).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `app/backend/routers/branches.py` | New router: `POST /api/branches/create` (create branch linked to PR), `DELETE /api/branches/{branch_id}` (delete), `GET /api/branches` (list with TTL/status/creator), `POST /api/branches/{branch_id}/reset` (reset from parent), `GET /api/branches/{branch_id}/schema-diff` (diff vs parent). Uses `lakebase_service.py` for Lakebase API calls. | ~300 |
| 2 | `app/backend/routers/cost.py` | New router: `GET /api/cost/attribution` (cost by project/branch/tag), `GET /api/cost/trends` (daily/weekly cost trends), `GET /api/cost/budget-policies` (list budget policies). Reads from `cost_attribution` Delta table + Lakebase API tags endpoint. Addresses FEIP-1444. | ~200 |
| 3 | `app/backend/routers/sync_monitor.py` | New router: `GET /api/sync/status` (all synced tables with lag), `GET /api/sync/history` (sync validation history), `POST /api/sync/validate` (trigger on-demand validation). Addresses FEIP-5271 (Critical). | ~200 |
| 4 | `app/backend/services/branch_service.py` | Service layer for branch operations: wraps Lakebase REST API `/api/2.0/postgres/projects/{id}/branches`, handles long-running operation polling, maps branch naming conventions (RFC 1123), manages TTL lifecycle. | ~350 |
| 5 | `app/backend/services/cost_service.py` | Service layer for cost attribution: queries Delta table, aggregates by tag/project/branch, integrates with Lakebase budget policy API (`/api/2.0/postgres/projects` with tags). | ~200 |
| 6 | `app/backend/models/branch.py` | Pydantic models: `BranchCreateRequest` (name, source_branch, ttl_hours, pr_number, creator_type), `BranchResponse`, `SchemaDiffResponse` (tables_added, tables_modified, tables_dropped, columns, indexes), `BranchPolicy` (ttl, max_branches, naming_pattern). | ~150 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `app/backend/main.py` | Register new routers: `branches`, `cost`, `sync_monitor`. Add to router includes. | P0 |
| 2 | `app/backend/services/lakebase_service.py` | Add methods: `create_branch()`, `delete_branch()`, `reset_branch()`, `list_branches()`, `get_branch_schema()`, `get_project_tags()`, `set_project_tags()`, `get_budget_policy()`. Also add HA status check and OAuth role management methods per 2026 API (Report 00, March 2026 features). | P0 |
| 3 | `app/backend/services/sql_service.py` | Add parameterized query support: `execute_query_params(sql, params)` method that passes parameters to the Databricks SQL Statement API. This unblocks WS1 parameterized queries. Add LRU cache with max size (fix unbounded cache). | P1 |
| 4 | `app/backend/routers/operations.py` | Add `/api/operations/sync` endpoint enhancement to reference new sync_monitor router. Add link to cost attribution. | P2 |

### New Dependencies

```
# app/requirements.txt additions
pydantic>=2.0          # Already a FastAPI transitive dep, pin explicitly
```

### Estimates

- **Files:** 6 create + 4 modify = 10 total
- **New lines:** ~1,800
- **Effort:** 3-5 days

### Priority Order (within workstream)

1. `branch_service.py` + `models/branch.py` (foundation)
2. `routers/branches.py` (branch lifecycle API)
3. `routers/sync_monitor.py` (FEIP-5271 Critical)
4. `cost_service.py` + `routers/cost.py` (FEIP-1444)
5. `lakebase_service.py` modifications (2026 features)
6. `sql_service.py` parameterized query support

### Dependencies on Other Workstreams

- **WS1-SECURITY:** `sql_service.py` parameterized query support enables WS1 fixes. Coordinate: WS2 adds the method, WS1 uses it.
- **WS7-CONFIG:** Branch naming conventions and TTL policies come from WS7 feature flags/config.
- **WS8-DATA:** `cost_attribution` and `branch_lifecycle` Delta tables must exist before cost/branch routers can query them.

---

## WS3-FRONTEND

**Scope:** New pages (Branch Dashboard, Schema Diff Viewer, Cost Attribution), new UI components for branch management, fix missing component/page tests.

**Traces to:** Report 04 Section 9.4 (Branch Dashboard), Report 06 Section 4.2 (Branch Observability Dashboard), Report 02 Section 3.2 (frontend test gaps), Report 08 FEIP-1444 (cost attribution UI).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `app/frontend/src/pages/Branches.tsx` | Branch Dashboard page: table of all active branches (name, type, TTL, parent, creator, age, storage divergence), create branch dialog, delete confirmation, reset action, status badges (ACTIVE/CREATING/ARCHIVED). Filter by type (CI/dev/QA/protected). Links to schema diff. | ~350 |
| 2 | `app/frontend/src/pages/SchemaDiff.tsx` | Schema Diff Viewer page: side-by-side or unified diff view of branch schema vs parent. Tables added (green), modified (yellow), dropped (red). Column-level detail. Index changes. Triggered from Branches page or direct URL `/schema-diff/:branchId`. | ~300 |
| 3 | `app/frontend/src/pages/CostAttribution.tsx` | Cost Attribution page: cost breakdown by project, branch, tag. Stacked bar chart (daily cost by branch type), pie chart (cost by tag category), table of top-cost branches. Date range picker. Budget policy status. | ~300 |
| 4 | `app/frontend/src/pages/SyncMonitor.tsx` | Sync Monitor page (FEIP-5271): table of all synced tables, sync lag (seconds/bytes), last sync timestamp, status badge (healthy/warning/critical). Auto-refresh every 30s. Trend chart for lag over time. | ~250 |
| 5 | `app/frontend/src/components/BranchCreateDialog.tsx` | Modal dialog for creating a new branch: name input (RFC 1123 validation), source branch dropdown, TTL selector (preset or custom), PR number (optional), creator type tag. Submit calls `POST /api/branches/create`. | ~200 |
| 6 | `app/frontend/src/components/SchemaDiffView.tsx` | Reusable schema diff renderer: accepts `SchemaDiffResponse` object, renders as expandable tree (table -> columns -> indexes). Color-coded additions/modifications/deletions. Used by both `SchemaDiff.tsx` page and future PR comment preview. | ~250 |
| 7 | `app/frontend/src/components/CostChart.tsx` | Cost visualization component: wraps Recharts for stacked area/bar charts specific to cost data. Supports daily/weekly/monthly aggregation toggle. | ~150 |
| 8 | `app/frontend/src/components/BranchTimeline.tsx` | Visual timeline of branch lifecycle events (created, migration applied, tests passed, merged/deleted). Horizontal timeline with event icons. Used in Branches page detail drawer. | ~150 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `app/frontend/src/App.tsx` | Add routes for new pages: `/branches`, `/schema-diff/:branchId`, `/cost`, `/sync`. Import new page components. | P0 |
| 2 | `app/frontend/src/components/Sidebar.tsx` | Add navigation items for Branches, Cost Attribution, Sync Monitor. Group under "Branch Management" and "Cost & Sync" sections. Use MUI icons: `AccountTree` (branches), `DifferenceOutlined` (schema diff), `AttachMoney` (cost), `Sync` (sync). | P0 |
| 3 | `app/frontend/src/hooks/useApiData.ts` | Add pagination support: accept `page` and `pageSize` params, return `totalCount` and `hasMore`. Used by Branches and Cost pages. | P1 |

### New Dependencies

```json
// package.json additions
"@mui/x-date-pickers": "^7.0.0"   // Date range picker for cost page
```

### Estimates

- **Files:** 8 create + 3 modify = 11 total
- **New lines:** ~2,400
- **Effort:** 4-6 days

### Priority Order (within workstream)

1. `Sidebar.tsx` + `App.tsx` route updates (unblocks all pages)
2. `Branches.tsx` + `BranchCreateDialog.tsx` (core feature)
3. `SchemaDiffView.tsx` + `SchemaDiff.tsx` (schema diff viewer)
4. `SyncMonitor.tsx` (FEIP-5271)
5. `CostAttribution.tsx` + `CostChart.tsx` (FEIP-1444)
6. `BranchTimeline.tsx` (enhancement)
7. `useApiData.ts` pagination

### Dependencies on Other Workstreams

- **WS2-BACKEND-API:** Frontend pages consume new API endpoints. WS3 can stub with mock data initially, then integrate once WS2 endpoints are ready.
- **WS8-DATA:** Cost data availability.

---

## WS4-AGENTS

**Scope:** New agent tools for branch lifecycle management, schema diff generation, UC masking validation, sync monitoring (FEIP-5271), cost attribution. Enhance existing agents with 2026 Lakebase capabilities.

**Traces to:** Report 04 Sections 9.1-9.3 (branch lifecycle, CI/CD, UC governance), Report 06 Sections 2.2-2.7 (branching design), Report 07 WS1/WS4 (CLI compatibility, UC masking), Report 08 FEIP-5271/FEIP-1444, Report 00 (2026 API features).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `agents/provisioning/branch_lifecycle.py` | New mixin: `BranchLifecycleMixin`. Tools: `create_branch_for_pr(pr_number, source_branch, ttl_hours)` -- creates RFC 1123 compliant branch `ci-pr-{N}`, tags with creator type; `delete_branch_for_pr(pr_number)` -- cleanup on merge/close; `enforce_branch_ttl()` -- scan all branches, delete expired TTL; `reset_branch_to_parent(branch_id)` -- reset for destructive testing; `get_branch_status(branch_id)` -- active/creating/archived with compute status. | ~500 |
| 2 | `agents/provisioning/schema_diff.py` | New mixin: `SchemaDiffMixin`. Tools: `generate_schema_diff(source_branch, target_branch)` -- compare pg_catalog schemas between two branches, produce structured diff (tables, columns, indexes, constraints, FKs); `format_diff_as_markdown()` -- render for PR comments; `format_diff_as_json()` -- structured output for API. Uses existing `SCHEMA_COLUMNS` query from `sql/queries.py` against both branch endpoints. | ~400 |
| 3 | `agents/provisioning/uc_masking.py` | New mixin: `UCMaskingMixin`. Tools: `validate_branch_masking(branch_id)` -- connect to branch, query `information_schema.column_privileges` and UC masking policies, verify PII/PHI columns have masking applied; `audit_all_branches_masking()` -- scan all active branches for masking compliance, return compliance percentage; `apply_rls_workaround(branch_id, policy_config)` -- interim RLS-based workaround per Report 07 WS4. | ~350 |
| 4 | `agents/health/sync_monitor.py` | New mixin: `SyncMonitorMixin`. Tools: `check_all_synced_tables()` -- query all synced table statuses via Lakebase API (`GET /api/2.0/postgres/synced_tables`), compute lag metrics; `validate_sync_integrity(table_name)` -- count/timestamp/checksum validation between source Delta and target Lakebase; `alert_on_sync_lag(threshold_seconds)` -- emit alert if any table exceeds lag threshold. Addresses FEIP-5271 (Critical). | ~450 |
| 5 | `agents/health/cost_attribution.py` | New mixin: `CostAttributionMixin`. Tools: `collect_cost_metrics()` -- gather compute CU-hours, storage bytes, branch count per project; tag with budget policy labels; `attribute_cost_by_tag(tag_key)` -- aggregate cost by serverless tag taxonomy; `generate_cost_report(period_days)` -- structured cost report per project/branch/tag. Addresses FEIP-1444 (Blocked). | ~500 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `agents/provisioning/agent.py` | Add new mixins to `ProvisioningAgent` MRO: `BranchLifecycleMixin`, `SchemaDiffMixin`, `UCMaskingMixin`. Register new tools in `register_tools()`. Update tool count (17 -> ~25). | P0 |
| 2 | `agents/health/agent.py` | Add new mixins: `SyncMonitorMixin`, `CostAttributionMixin`. Register new tools. Update tool count (16 -> ~22). | P0 |
| 3 | `agents/provisioning/branching.py` | Refactor: move PR-specific branch logic to new `branch_lifecycle.py`. Keep generic branch CRUD. Fix existing TTL enforcement to use configurable policies from WS7-CONFIG instead of hardcoded values. | P1 |
| 4 | `framework/agent_framework.py` | Add new `EventType` values: `BRANCH_TTL_EXPIRED`, `SCHEMA_DIFF_GENERATED`, `SYNC_LAG_DETECTED`, `COST_THRESHOLD_BREACHED`, `MASKING_VIOLATION_FOUND`. | P1 |

### New Dependencies

None -- uses existing `databricks-sdk` and `psycopg` for all Lakebase API and PG connections.

### Estimates

- **Files:** 5 create + 4 modify = 9 total
- **New lines:** ~2,200
- **Effort:** 4-6 days

### Priority Order (within workstream)

1. `branch_lifecycle.py` + agent registration (core feature)
2. `schema_diff.py` (schema diff generation)
3. `sync_monitor.py` (FEIP-5271 Critical)
4. `cost_attribution.py` (FEIP-1444)
5. `uc_masking.py` (UC governance)
6. `framework/agent_framework.py` event types
7. Refactor `branching.py`

### Dependencies on Other Workstreams

- **WS7-CONFIG:** TTL policies and feature flags consumed by branch_lifecycle tools.
- **WS8-DATA:** `branch_lifecycle`, `cost_attribution`, `sync_monitoring` Delta tables must exist for persistence.
- **WS2-BACKEND-API:** Agent tools feed data that backend API exposes. No direct code dependency (decoupled via Delta tables).

---

## WS5-TESTING

**Scope:** Backend unit tests for all agents/tools/routers/services, integration test framework, frontend test coverage expansion. Addresses the "zero backend unit tests" critical gap.

**Traces to:** Report 02 Section 3 (test coverage -- CRITICAL: 0% backend), Section 3.4 (coverage estimates), Report 01 Section 12 (empty tests/ directory).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `tests/conftest.py` | Shared pytest fixtures: `mock_lakebase_client`, `mock_delta_writer`, `mock_alert_manager`, `sample_project_config`, `sample_branch_data`, `mock_sql_service`, `fastapi_test_client` (TestClient for routers). Uses `unittest.mock` and `pytest-asyncio`. | ~200 |
| 2 | `tests/test_agent_framework.py` | Tests for `BaseAgent`, `AgentFramework`, `EventBus`: tool registration, event dispatch, subscriber notification, task result creation, cycle execution order, error handling in dispatch. ~15 tests. | ~300 |
| 3 | `tests/test_provisioning_agent.py` | Tests for ProvisioningAgent tools: project creation (mock mode), branch CRUD, TTL enforcement, migration execution, CICD YAML generation, governance tools. Mock all external calls. ~20 tests. | ~350 |
| 4 | `tests/test_performance_agent.py` | Tests for PerformanceAgent tools: metric collection, index analysis (5 detection types), vacuum scheduling, TXID wraparound detection, capacity forecasting. ~15 tests. | ~300 |
| 5 | `tests/test_health_agent.py` | Tests for HealthAgent tools: health metric evaluation, threshold breach detection, sync validation, archival identification, connection monitoring, cost attribution, self-healing. ~15 tests. | ~300 |
| 6 | `tests/test_lakebase_client.py` | Tests for `LakebaseClient`: mock mode connection, token refresh logic, REST API wrapper methods, branch operations, connection pool behavior. ~12 tests. | ~250 |
| 7 | `tests/test_delta_writer.py` | Tests for `DeltaWriter`: mock mode writes, SQL API batch construction, table creation DDL, schema validation. ~8 tests. | ~200 |
| 8 | `tests/test_sql_queries.py` | SQL syntax validation: parse all 21 query constants from `sql/queries.py` using `sqlparse` to verify syntactic correctness. Also validate that placeholder variables are properly formatted. ~21 tests. | ~150 |
| 9 | `tests/test_routers_metrics.py` | FastAPI router tests for `metrics.py`: test `/api/metrics/overview` returns cached data, `/api/metrics/trends` validates metric allowlist, rejects invalid metrics with 400, parameterized query construction. Uses `TestClient`. ~8 tests. | ~200 |
| 10 | `tests/test_routers_branches.py` | FastAPI router tests for new `branches.py` router: create branch, delete branch, list branches, reset, schema diff endpoint. Mock `branch_service`. ~10 tests. | ~250 |
| 11 | `tests/test_routers_cost.py` | FastAPI router tests for new `cost.py` router: attribution endpoint, trends, budget policies. Mock `cost_service`. ~6 tests. | ~150 |
| 12 | `tests/test_services.py` | Tests for `sql_service`, `lakebase_service`, `agent_service`: query execution, caching behavior, credential acquisition fallback chain, agent simulation. ~10 tests. | ~250 |
| 13 | `app/frontend/src/__tests__/Branches.test.tsx` | Frontend tests for Branches page: renders branch table, create dialog opens, filter by type, delete confirmation, empty state. ~5 tests. | ~150 |
| 14 | `app/frontend/src/__tests__/SyncMonitor.test.tsx` | Frontend tests for SyncMonitor page: renders table, status badges, auto-refresh behavior. ~4 tests. | ~120 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `tests/__init__.py` | Keep as-is (empty file for package discovery). Already exists. | -- |
| 2 | `requirements.txt` | Add test dependencies: `sqlparse>=0.5`, `httpx>=0.27` (for FastAPI TestClient async), `pytest-cov>=5.0`. | P0 |

### New Dependencies

```
# requirements.txt additions
sqlparse>=0.5.0       # SQL syntax validation in tests
httpx>=0.27.0         # FastAPI TestClient (async)
pytest-cov>=5.0.0     # Coverage reporting
```

### Estimates

- **Files:** 14 create + 2 modify = 16 total
- **New lines:** ~3,500
- **Effort:** 5-7 days

### Priority Order (within workstream)

1. `conftest.py` (all tests depend on this)
2. `test_agent_framework.py` (core framework)
3. `test_sql_queries.py` (quick win -- validates all 21 queries)
4. `test_routers_metrics.py` (validates WS1 security fixes)
5. `test_lakebase_client.py` + `test_delta_writer.py` (utilities)
6. `test_provisioning_agent.py` + `test_performance_agent.py` + `test_health_agent.py`
7. `test_routers_branches.py` + `test_routers_cost.py` (new WS2 endpoints)
8. `test_services.py`
9. Frontend tests: `Branches.test.tsx`, `SyncMonitor.test.tsx`

### Dependencies on Other Workstreams

- **WS1-SECURITY:** Tests for routers validate the parameterized query fixes and exception handling.
- **WS2-BACKEND-API:** Tests for new routers (`branches`, `cost`, `sync_monitor`) require those routers to exist.
- **WS4-AGENTS:** Tests for new agent tools require mixin files to exist.
- **WS7-CONFIG:** `conftest.py` fixtures use config from `pyproject.toml` test section.

---

## WS6-CICD

**Scope:** GitHub Actions workflows (branch-on-PR, schema diff in PR comments, TTL cleanup), DABs bundle config, linting config (ruff/black/mypy). Move template workflows to active `.github/workflows/`.

**Traces to:** Report 01 Section 8 (no active CI/CD), Report 02 Section 4 (no linting config), Report 04 Section 9.2 (CI/CD integration), Report 06 Section 2.7 (GitHub Actions), Report 07 WS3 (FEIP-5092 CI/CD Integrations).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `.github/workflows/ci.yml` | Core CI pipeline: on push/PR to main. Steps: (a) checkout, (b) setup Python 3.11, (c) install deps, (d) ruff check + ruff format --check, (e) mypy --strict on `app/backend/` and `agents/`, (f) pytest with coverage report, (g) fail if coverage < 60%. | ~120 |
| 2 | `.github/workflows/branch-on-pr.yml` | Lakebase branch-per-PR: on PR opened/reopened. Steps: (a) install Databricks CLI, (b) create Lakebase branch `ci-pr-{PR_NUMBER}` from production with TTL 4h, (c) apply SQL migrations from `sql/` directory, (d) run integration tests against branch endpoint, (e) generate schema diff and post as PR comment via `gh api`. Adapted from existing `github_actions/create_branch_on_pr.yml` template. | ~180 |
| 3 | `.github/workflows/branch-cleanup.yml` | Branch cleanup: on PR closed. Steps: (a) delete Lakebase branch `ci-pr-{PR_NUMBER}`, (b) if merged, optionally replay migrations to staging. Adapted from existing `github_actions/delete_branch_on_pr_close.yml`. | ~80 |
| 4 | `.github/workflows/branch-ttl-cleanup.yml` | Scheduled TTL enforcement: runs every 6 hours via cron. Steps: (a) list all branches via Databricks CLI, (b) identify branches past TTL, (c) delete expired branches, (d) post summary to Slack (optional). | ~100 |
| 5 | `.github/workflows/frontend-ci.yml` | Frontend CI: on changes to `app/frontend/**`. Steps: (a) setup Node 20, (b) npm ci, (c) npm run lint (if eslint added), (d) npm run test -- --coverage, (e) npm run build. | ~80 |
| 6 | `databricks.yml` | Databricks Asset Bundles configuration: defines the app deployment target, job definitions (8 jobs from `jobs/`), workspace file sync paths. Environments: dev, staging, production. References `app/app.yaml` for Apps deployment. | ~250 |
| 7 | `.pre-commit-config.yaml` | Pre-commit hooks: ruff (lint + format), mypy, trailing whitespace, end-of-file fixer, check-yaml, check-json. | ~40 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `.gitignore` | Add: `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `app/static/`, `*.pyc`, `.env`. Some may already be present -- verify and add missing entries. | P1 |

### New Dependencies

```
# Dev dependencies (in pyproject.toml [project.optional-dependencies] dev section)
ruff>=0.4.0
mypy>=1.10.0
pre-commit>=3.7.0
```

### Estimates

- **Files:** 7 create + 1 modify = 8 total
- **New lines:** ~1,200
- **Effort:** 2-3 days

### Priority Order (within workstream)

1. `.github/workflows/ci.yml` (core CI -- unblocks all PR quality gates)
2. `.github/workflows/branch-on-pr.yml` + `branch-cleanup.yml` (branch lifecycle)
3. `databricks.yml` (IaC for deployment)
4. `.pre-commit-config.yaml` (developer experience)
5. `.github/workflows/frontend-ci.yml` (frontend quality)
6. `.github/workflows/branch-ttl-cleanup.yml` (operational)

### Dependencies on Other Workstreams

- **WS7-CONFIG:** `pyproject.toml` (from WS7) must define `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections that CI workflows reference.
- **WS5-TESTING:** CI runs `pytest` -- tests must exist.
- **WS2-BACKEND-API:** `branch-on-pr.yml` uses Lakebase branch API patterns defined in WS2 `branch_service.py`.

---

## WS7-CONFIG

**Scope:** Settings refactor (environment variable overrides instead of hardcoded IDs), feature flags, serverless tagging taxonomy, `pyproject.toml` for packaging and tooling.

**Traces to:** Report 02 Section 5.2 (hardcoded IDs), Section 4 (no linting config), Section 7.2 (dead code/duplicate enums), Report 01 Section 10.4 (no pyproject.toml), Report 01 Section 11.1 (hardcoded settings).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `pyproject.toml` | Project metadata, dependencies (migrate from `requirements.txt`), optional-dependencies (dev, test), tool config for ruff, black, mypy, pytest. Defines `[project]` with name `lakebase-ops-platform`, version `2.0.0`, Python `>=3.11`. Replaces need for separate tool config files. | ~150 |
| 2 | `config/feature_flags.py` | Feature flag registry: `ENABLE_BRANCH_LIFECYCLE`, `ENABLE_SCHEMA_DIFF`, `ENABLE_COST_ATTRIBUTION`, `ENABLE_SYNC_MONITOR`, `ENABLE_UC_MASKING_VALIDATION`, `ENABLE_HA_MONITORING`. Each flag reads from env var with default. Used by agents and routers to gate new features. | ~80 |
| 3 | `config/tagging.py` | Serverless tagging taxonomy for Lakebase cost attribution. Defines tag keys: `team`, `environment`, `workload-type` (ci/dev/qa/perf/prod), `creator-type` (human/agent/ci), `pr-number`, `ttl-policy`. Validation functions for tag values. Maps to Lakebase API tag format per Report 00 March 2026 features. | ~100 |
| 4 | `.env.example` | Example environment file documenting all configurable settings: `DATABRICKS_HOST`, `LAKEBASE_PROJECT_ID`, `SQL_WAREHOUSE_ID`, `LAKEBASE_ENDPOINT_HOST`, `OPS_CATALOG`, `OPS_SCHEMA`, plus all feature flags. No actual secrets -- template only. | ~50 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `config/settings.py` | **Major refactor:** (a) Replace all hardcoded values with `os.environ.get("VAR", default)` pattern. Specifically: `WORKSPACE_HOST`, `DEFAULT_CATALOG`, `OPS_SCHEMA`, `SQL_WAREHOUSE_ID`, `LAKEBASE_PROJECT_ID`, `LAKEBASE_ENDPOINT_HOST`. (b) Remove duplicate `AlertSeverity` enum (lines 36-39) -- it already exists in `utils/alerting.py`. (c) Add `ServerlessConfig` dataclass with tagging taxonomy reference. (d) Add `TTLPolicy` dataclass per branch type (from design doc Section 2.4): CI=4h, hotfix=24h, feature=7d, QA=14d, audit=30d. | P0 |
| 2 | `config/__init__.py` | Export new modules: `feature_flags`, `tagging`. | P1 |
| 3 | `app/app.yaml` | Update env section to reference all new configurable variables. Add feature flag env vars. | P1 |

### New Dependencies

None -- pure Python configuration.

### Estimates

- **Files:** 4 create + 3 modify = 7 total
- **New lines:** ~800
- **Effort:** 1-2 days

### Priority Order (within workstream)

1. `pyproject.toml` (unblocks WS6 CI linting)
2. `config/settings.py` refactor (env var overrides)
3. `.env.example` (developer onboarding)
4. `config/feature_flags.py` (gates new features)
5. `config/tagging.py` (serverless cost taxonomy)

### Dependencies on Other Workstreams

- **None inbound** -- WS7 has no blockers.
- **Outbound:** WS6 depends on `pyproject.toml` for tool config. WS4 depends on feature flags and TTL policies. WS2 depends on configurable settings.

---

## WS8-DATA

**Scope:** New Delta tables for branch lifecycle tracking, cost attribution, sync monitoring; SQL migrations; update existing queries.

**Traces to:** Report 01 Section 5.1 (7 existing Delta tables -- need 3 more), Report 04 Section 9.4 (branch creation metrics), Report 06 Section 4.2 (branch observability), Report 08 FEIP-5271 (sync monitor), FEIP-1444 (cost attribution).

### Files to CREATE

| # | File Path | Description | Est. Lines |
|---|-----------|-------------|------------|
| 1 | `sql/migrations/001_add_branch_lifecycle_columns.sql` | ALTER existing `branch_lifecycle` table: add columns `pr_number` (INT), `creator_type` (STRING -- human/agent/ci), `source_branch` (STRING), `ttl_hours` (INT), `storage_divergence_bytes` (BIGINT), `schema_diff_json` (STRING), `deleted_at` (TIMESTAMP), `deletion_reason` (STRING -- ttl_expired/pr_merged/pr_closed/manual). Also CREATE TABLE IF NOT EXISTS `cost_attribution` (project_id, branch_id, date, compute_cu_hours DECIMAL, storage_bytes BIGINT, tag_team STRING, tag_environment STRING, tag_workload_type STRING, tag_creator_type STRING, estimated_cost_usd DECIMAL) PARTITIONED BY (project_id, date). And CREATE TABLE IF NOT EXISTS `sync_monitoring` (table_name, sync_direction, source_row_count BIGINT, target_row_count BIGINT, lag_seconds DECIMAL, lag_bytes BIGINT, validation_method STRING, validation_status STRING, checked_at TIMESTAMP). | ~120 |
| 2 | `sql/migrations/002_add_tagging_tables.sql` | CREATE TABLE IF NOT EXISTS `serverless_tags` (project_id STRING, tag_key STRING, tag_value STRING, applied_at TIMESTAMP, applied_by STRING). CREATE TABLE IF NOT EXISTS `budget_policies` (policy_id STRING, project_id STRING, monthly_budget_usd DECIMAL, alert_threshold_pct INT, current_spend_usd DECIMAL, period_start DATE, period_end DATE). | ~60 |
| 3 | `sql/migrations/README.md` | Migration README: explains migration numbering convention, how to run migrations (via `databricks sql execute` or `delta_writer.py`), idempotency requirements. | ~40 |

### Files to MODIFY

| # | File Path | Changes | Priority |
|---|-----------|---------|----------|
| 1 | `utils/delta_writer.py` | Add `create_ops_catalog_and_schemas()` expansion: include DDL for 3 new tables (`cost_attribution`, `sync_monitoring`, `serverless_tags`, `budget_policies`). Add new write methods: `write_cost_attribution()`, `write_sync_monitoring()`, `write_serverless_tags()`. | P0 |
| 2 | `sql/queries.py` | Add new named SQL constants: `COST_ATTRIBUTION_BY_PROJECT`, `COST_ATTRIBUTION_BY_TAG`, `COST_TRENDS_DAILY`, `SYNC_STATUS_ALL`, `SYNC_LAG_HISTORY`, `BRANCH_LIFECYCLE_WITH_PR`, `BRANCH_STORAGE_DIVERGENCE`, `ACTIVE_BUDGET_POLICIES`. ~8 new queries. | P0 |

### New Dependencies

None.

### Estimates

- **Files:** 3 create + 2 modify = 5 total
- **New lines:** ~600
- **Effort:** 1-2 days

### Priority Order (within workstream)

1. `001_add_branch_lifecycle_columns.sql` (enables WS2/WS4 branch and cost features)
2. `delta_writer.py` expansion (write methods for new tables)
3. `sql/queries.py` new constants (read queries for new tables)
4. `002_add_tagging_tables.sql` (serverless tagging)

### Dependencies on Other Workstreams

- **None inbound** -- WS8 has no blockers. Should start early.
- **Outbound:** WS2 (backend API), WS4 (agents), and WS3 (frontend) all depend on these tables existing.

---

## Cross-Workstream Dependencies

```
Execution Order (DAG):

Layer 0 (start immediately, no deps):
  WS7-CONFIG   -- pyproject.toml, settings refactor, feature flags
  WS8-DATA     -- Delta tables, migrations, queries
  WS1-SECURITY -- SQL injection fixes (can start in parallel)

Layer 1 (after Layer 0):
  WS2-BACKEND-API -- needs WS7 (config), WS8 (tables), WS1 (parameterized queries)
  WS4-AGENTS      -- needs WS7 (feature flags, TTL policies), WS8 (tables)
  WS6-CICD        -- needs WS7 (pyproject.toml for tool config)

Layer 2 (after Layer 1):
  WS3-FRONTEND    -- needs WS2 (API endpoints to consume)
  WS5-TESTING     -- needs WS1, WS2, WS4 (code to test)

Note: All workstreams CAN start in parallel with stubs/mocks.
The dependencies above indicate when integration is possible.
```

### Dependency Matrix

| Workstream | Depends On | Depended On By |
|------------|-----------|----------------|
| WS1-SECURITY | -- | WS5 |
| WS2-BACKEND-API | WS1, WS7, WS8 | WS3, WS5 |
| WS3-FRONTEND | WS2 | WS5 |
| WS4-AGENTS | WS7, WS8 | WS5 |
| WS5-TESTING | WS1, WS2, WS3, WS4 | -- |
| WS6-CICD | WS7 | -- |
| WS7-CONFIG | -- | WS2, WS4, WS6 |
| WS8-DATA | -- | WS2, WS4 |

---

## CHANGELOG Entry

```markdown
# Changelog

## [2.0.0] - 2026-04-XX

### Security
- **BREAKING:** Fixed SQL injection vulnerability in `/api/metrics/trends` endpoint (metrics.py line 61)
- Fixed SQL interpolation in performance.py and operations.py routers
- Tightened CORS from `allow_origins=["*"]` to Databricks Apps domains only
- Added custom exception hierarchy (`LakebaseOpsError` and subclasses)
- Added Pydantic response models for all API endpoints
- Added input validation middleware

### Added
- **Branch Lifecycle Management:** New `/api/branches` endpoints for create, delete, reset, list, and schema diff
- **Schema Diff Viewer:** Side-by-side schema comparison between Lakebase branches
- **Cost Attribution:** New `/api/cost` endpoints and dashboard page (addresses FEIP-1444)
- **Sync Monitor:** New `/api/sync` endpoints and dashboard page (addresses FEIP-5271)
- **UC Masking Validation:** Agent tools to verify Unity Catalog masking propagation to branches
- **Frontend Pages:** Branches, Schema Diff, Cost Attribution, Sync Monitor pages
- **Frontend Components:** BranchCreateDialog, SchemaDiffView, CostChart, BranchTimeline
- **Backend Unit Tests:** 130+ tests across agents, framework, routers, services, and utilities
- **Frontend Tests:** Branch and Sync Monitor page tests
- **CI/CD Pipelines:** GitHub Actions for CI, branch-on-PR, branch cleanup, TTL enforcement, frontend CI
- **Databricks Asset Bundles:** `databricks.yml` for declarative infrastructure deployment
- **Feature Flags:** Runtime feature toggle system for all new capabilities
- **Serverless Tagging Taxonomy:** Cost attribution tags (team, environment, workload-type, creator-type)
- **Delta Tables:** `cost_attribution`, `sync_monitoring`, `serverless_tags`, `budget_policies`
- **SQL Migrations:** Numbered migration files with idempotent DDL

### Changed
- **BREAKING:** `config/settings.py` now reads all infrastructure IDs from environment variables (with backwards-compatible defaults)
- Migrated project configuration from `requirements.txt` to `pyproject.toml`
- Added `pyproject.toml` with ruff, mypy, and pytest configuration
- Expanded `branch_lifecycle` Delta table with PR tracking columns
- Added parameterized query support in `sql_service.py`
- Added LRU max-size to `sql_service` cache (was unbounded)
- Added pagination support to frontend `useApiData` hook

### Removed
- Duplicate `AlertSeverity` enum from `config/settings.py` (kept in `utils/alerting.py`)

### Fixed
- `health.py` router now logs exceptions instead of silently swallowing them
- Notebook import paths in `jobs/*.py` corrected to match actual module structure
```

---

## Commit Messages

### WS1-SECURITY
```
fix(security): patch SQL injection in metrics router and add input validation

Replace f-string SQL interpolation with parameterized queries across all
routers. Add custom exception hierarchy (LakebaseOpsError), Pydantic
response models, and CORS tightening. Addresses CVE-equivalent SQL
injection in /api/metrics/trends endpoint.

Co-authored-by: Isaac
```

### WS2-BACKEND-API
```
feat(api): add branch lifecycle, cost attribution, and sync monitor endpoints

New routers: /api/branches (CRUD + schema diff), /api/cost (attribution
+ budget policies), /api/sync (status + validation). New service layers
for branch operations and cost aggregation. Integrates Lakebase 2026 API
features (HA, OAuth roles, budget policies/tags).

Addresses: FEIP-5271 (Centralized Lakebase Sync Monitor), FEIP-1444
(Lakebase cost attribution).

Co-authored-by: Isaac
```

### WS3-FRONTEND
```
feat(frontend): add Branch Dashboard, Schema Diff, Cost, and Sync Monitor pages

Four new pages with supporting components: BranchCreateDialog (RFC 1123
validation), SchemaDiffView (color-coded diff tree), CostChart (stacked
area/bar), BranchTimeline (lifecycle events). Pagination support added
to useApiData hook. Sidebar updated with new navigation sections.

Co-authored-by: Isaac
```

### WS4-AGENTS
```
feat(agents): add branch lifecycle, schema diff, UC masking, sync, and cost tools

New mixins: BranchLifecycleMixin (PR-linked branch CRUD, TTL enforcement),
SchemaDiffMixin (pg_catalog comparison, markdown/JSON output),
UCMaskingMixin (masking propagation validation), SyncMonitorMixin
(synced table lag detection), CostAttributionMixin (compute/storage cost
collection and tag-based aggregation). ProvisioningAgent: 17->25 tools.
HealthAgent: 16->22 tools.

Co-authored-by: Isaac
```

### WS5-TESTING
```
test: add comprehensive backend unit tests and expand frontend coverage

130+ backend tests covering agent framework, all three agents, utilities
(LakebaseClient, DeltaWriter), SQL query syntax validation, FastAPI
routers (metrics, branches, cost, sync), and services. Frontend tests
for Branches and SyncMonitor pages. Shared fixtures in conftest.py.

Backend test coverage: 0% -> ~65% estimated.

Co-authored-by: Isaac
```

### WS6-CICD
```
ci: add GitHub Actions pipelines, DABs config, and pre-commit hooks

Active CI/CD: ci.yml (ruff + mypy + pytest), branch-on-pr.yml (Lakebase
branch per PR with schema diff comment), branch-cleanup.yml, ttl-cleanup
(cron), frontend-ci.yml. databricks.yml for Asset Bundles deployment.
.pre-commit-config.yaml for local dev quality gates.

Replaces template-only github_actions/ directory with active pipelines.

Co-authored-by: Isaac
```

### WS7-CONFIG
```
refactor(config): replace hardcoded IDs with env vars, add pyproject.toml

Settings refactor: all infrastructure IDs (WORKSPACE_HOST, PROJECT_ID,
WAREHOUSE_ID, ENDPOINT_HOST) now read from environment variables with
backwards-compatible defaults. Added pyproject.toml (ruff, mypy, pytest
config), feature flags, serverless tagging taxonomy, TTL policies per
branch type, and .env.example template.

Removed duplicate AlertSeverity enum from settings.py.

Co-authored-by: Isaac
```

### WS8-DATA
```
feat(data): add Delta tables for cost attribution, sync monitoring, and tagging

SQL migrations: branch_lifecycle table expansion (PR tracking, creator
type, storage divergence), new cost_attribution table (CU-hours, storage,
tags), sync_monitoring table, serverless_tags, budget_policies.
DeltaWriter updated with new write methods. 8 new SQL query constants.

Co-authored-by: Isaac
```

---

## Summary

| Metric | Value |
|--------|-------|
| Total files to create | 50 |
| Total files to modify | 24 |
| Total estimated new lines | ~13,050 |
| Total estimated effort | 21-33 person-days |
| Backend test count (new) | ~130 |
| Frontend test count (new) | ~9 |
| New API endpoints | 11 |
| New frontend pages | 4 |
| New frontend components | 4 |
| New agent tools | ~14 |
| New Delta tables | 4 |
| New SQL migrations | 2 |
| Jira tickets addressed | FEIP-5271 (Critical), FEIP-1444 (Blocked), FEIP-5484 (In Progress) |

---

*Generated by Implementation Planner agent on 2026-04-05.*
