# Gap Analysis: lakebase-ops-platform

**Generated:** 2026-04-05
**Source Reports:** 00 (Lakebase API Docs), 01 (Repo Architecture), 02 (Code Quality), 03 (Data Integration), 04 (Slides Analysis), 05 (Design Doc 1), 06 (Design Doc 2), 07 (Jira Epic), 08 (Jira Board)
**Branch:** including_serverless_tags
**Total Gaps Identified:** 52

---

## Gap Matrix

### SECURITY

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-001 | **CRITICAL** | Report 02 (Code Quality 5.1) | `metrics.py` validates metric name against allowlist but still uses f-string interpolation `'{safe_metric}'` in SQL. `performance.py` interpolates `{hours}` and `{limit}` directly into SQL. `operations.py` interpolates `{days}`. | Refactor `app/backend/routers/metrics.py`, `performance.py`, `operations.py` to use parameterized queries via the SQL Statement Execution API's `parameters` field or add server-side type coercion. Even with the allowlist, the f-string pattern sets a dangerous precedent. | S | SQL injection risk in API routers |
| GAP-002 | **HIGH** | Report 02 (5.3), Report 05 (NFR-2), Report 06 (3.3) | `app/backend/main.py` falls back to `allow_origins=["*"]` when `CORS_ORIGINS` env var is unset. No env var is set in `app.yaml`. | Set `CORS_ORIGINS` in `app/app.yaml` to the Databricks Apps domain. Update default to deny-all instead of allow-all. Modify `app/backend/main.py`. | S | CORS wildcard default in production |
| GAP-003 | **HIGH** | Report 05 (NFR-2, Section 7), Report 06 (3.3), Report 04 (9.3) | `agents/provisioning/governance.py` creates per-tenant RLS but has no validation that UC masking policies propagate to new branches. No masking validation tool exists. | Create `agents/provisioning/governance.py::validate_branch_masking()` tool. Add `jobs/masking_compliance_job.py` for scheduled validation. Create Delta table `masking_compliance_results`. | L | UC masking propagation not validated |
| GAP-004 | **HIGH** | Report 02 (5.4), Report 05 (NFR-2) | FastAPI app has zero authentication middleware. Relies entirely on Databricks Apps proxy. | Add auth middleware that validates Databricks Apps proxy headers (`X-Forwarded-User`, `X-Forwarded-Email`). At minimum, reject requests without proxy headers when running in non-local mode. Modify `app/backend/main.py`. | M | No app-level authentication middleware |
| GAP-005 | **MEDIUM** | Report 05 (Section 7), Report 06 (3.3) | No PII/PHI column inventory exists in the codebase. Design docs require cataloging all sensitive columns. | Create `config/sensitive_columns.yaml` or integrate with UC tags API to auto-discover columns tagged as PII/PHI/PCI. Add validation in `governance.py`. | M | No sensitive data inventory |
| GAP-006 | **MEDIUM** | Report 02 (5.4) | `lakebase_service.py` accesses private SDK attributes (`client.config._token`, `client.config._header_factory`) for credential extraction. | Refactor `app/backend/services/lakebase_service.py` to use only public SDK APIs. Use `WorkspaceClient().postgres.generate_database_credential()` as primary path. | M | Private SDK API access is fragile |

---

### BACKEND

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-007 | **HIGH** | Report 02 (7.3), Report 01 (14) | `jobs/metric_collector_notebook.py` imports from `agents.performance_agent` which does not exist. All 7 notebook files have broken imports referencing an older module structure. | Update all files in `jobs/` to use correct import paths: `agents.performance.agent`, `agents.health.agent`, `agents.provisioning.agent`. Update `config.settings.SETTINGS` references. | S | Broken notebook imports |
| GAP-008 | **HIGH** | Report 02 (7.2) | `utils/alerting.py::_send_slack()` builds a Slack message dict but never sends it (no `requests.post`). `_send_pagerduty()` and `_send_email()` only log. | Implement actual HTTP calls in `utils/alerting.py` for Slack webhook, PagerDuty Events API, and email (SMTP or SES). | M | Alert channels not implemented |
| GAP-009 | **HIGH** | Report 02 (4.2) | No Pydantic response models. All FastAPI routers return raw dicts. No OpenAPI schema for responses. | Create `app/backend/models/` with Pydantic models for each router's response types. Add `response_model` to route decorators. | M | No Pydantic response models |
| GAP-010 | **MEDIUM** | Report 02 (6.3) | No pagination on `/api/metrics/overview`, `/api/indexes/recommendations`, `/api/operations/branches`. Frontend `useApiData` has no pagination support. | Add `offset` and `limit` query params to all list endpoints. Update frontend hook. Modify `app/backend/routers/metrics.py`, `indexes.py`, `operations.py` and `app/frontend/src/hooks/useApiData.ts`. | M | Missing API pagination |
| GAP-011 | **MEDIUM** | Report 02 (1.4) | `LakebaseClient` is 558 lines handling OAuth, connection pooling, PG queries, REST API, and mock data. | Refactor `utils/lakebase_client.py` into `ConnectionManager`, `BranchAPI`, `MockDataGenerator` classes. | L | LakebaseClient god object |
| GAP-012 | **MEDIUM** | Report 02 (2.2) | No custom exception hierarchy. All errors caught as generic `Exception`. | Create `utils/exceptions.py` with `LakebaseOpsError` base and `ConnectionError`, `QueryError`, `AuthError` subclasses. Update agent and service code. | M | No custom exception hierarchy |
| GAP-013 | **MEDIUM** | Report 02 (6.4, 6.5) | `sql_service` cache has no max-size or LRU eviction. `LakebaseClient._connections` dict has no max-size. `DeltaWriter._sql_execute_and_wait()` uses synchronous `time.sleep(2)` in async context. | Add `maxsize` to cache dict in `sql_service.py`. Add connection pool limit to `lakebase_client.py`. Convert blocking poll to async in `delta_writer.py`. | M | Unbounded caches and blocking I/O |
| GAP-014 | **LOW** | Report 02 (7.1) | Duplicate `AlertSeverity` enum in `config/settings.py` (unused) and `utils/alerting.py` (used). | Remove `AlertSeverity` from `config/settings.py`. | S | Duplicate enum definition |
| GAP-015 | **LOW** | Report 01 (10.1) | Root `requirements.txt` lists both `psycopg[binary]>=3.0` and `psycopg2-binary>=2.9`. Only psycopg3 is used. App `requirements.txt` pins `>=0.40.0` for databricks-sdk vs root `>=0.81.0`. | Remove `psycopg2-binary` from root `requirements.txt`. Align SDK version in `app/requirements.txt` to `>=0.81.0`. | S | Dependency inconsistencies |

---

### FRONTEND

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-016 | **HIGH** | Report 04 (9.4), Report 06 (4.2) | No "Branches" page exists. 7 pages present (Dashboard, Agents, Performance, Indexes, Operations, LiveStats, Assessment) but slides and design docs call for a dedicated branch status dashboard. | Create `app/frontend/src/pages/Branches.tsx` showing active branches, TTLs, parent, creation source (human/agent/CI), schema drift from main. Add route in `App.tsx`. Add sidebar link in `Sidebar.tsx`. Create `/api/branches/status` backend endpoint. | L | Missing Branches dashboard page |
| GAP-017 | **MEDIUM** | Report 04 (9.7) | No adoption metrics tracking or display. Slides define 9 KPIs (mock classes, provisioning time, DBA tickets, dev wait time, etc.). | Create `app/frontend/src/pages/AdoptionMetrics.tsx` with sprint-over-sprint trends. Create backend endpoint `/api/metrics/adoption`. | L | Missing Adoption Metrics page |
| GAP-018 | **MEDIUM** | Report 06 (4.2) | No branch observability dashboard: branch age distribution, storage consumption, creation/deletion rate, TTL compliance. | Incorporate into GAP-016 Branches page or create separate observability tab. Backend needs `/api/branches/observability` endpoint querying `branch_lifecycle` table. | M | Missing Branch Observability UI |
| GAP-019 | **LOW** | Report 02 (3.2) | Frontend tests only cover 5/13 components and 1/7 pages. Missing tests for Performance, Indexes, Operations, LiveStats, Assessment pages and Sidebar, MetricsChart, StatusBadge, ExtensionMatrix, CostEstimate, GanttChart, ErrorBoundary components. | Create test files in `app/frontend/src/__tests__/` for untested pages and components. | M | Low frontend test coverage |

---

### TESTING

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-020 | **CRITICAL** | Report 02 (3.3) | `tests/` directory contains only empty `__init__.py`. Zero unit tests for 47 agent tools, 15 mixin modules, framework core, utilities. Only `app/backend/tests/test_routers.py` has ~20 tests for the web app. | Create comprehensive test suite: `tests/test_framework.py`, `tests/test_agents/`, `tests/test_utils/`. Priority: framework event bus, LakebaseClient mock mode, DeltaWriter mock mode, AlertManager routing. | XL | Zero Python unit tests for agents |
| GAP-021 | **HIGH** | Report 02 (3.1) | No SQL query syntax validation tests. 21 SQL constants in `sql/queries.py` are untested. | Create `tests/test_sql_queries.py` that validates SQL syntax (parse with `sqlparse` or execute against a test DB). | M | No SQL query validation tests |
| GAP-022 | **HIGH** | Report 02 (3.2) | `app/backend/tests/test_routers.py` covers health, metrics, and assessment but not performance, indexes, operations, lakebase, jobs routers. | Add test classes for all remaining routers in `app/backend/tests/test_routers.py`. | M | Incomplete backend router tests |
| GAP-023 | **MEDIUM** | Report 05 (Section 6, Testing Requirements), Report 06 (Section 2.6) | No integration test for the 9-step migration workflow (create branch -> apply migration -> schema diff -> test -> cleanup). `deploy_and_test.py` tests individual tools but not the end-to-end workflow. | Create `tests/test_migration_workflow.py` testing the full 9-step flow in mock mode. | L | No migration workflow integration test |

---

### CICD

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-024 | **HIGH** | Report 01 (8.2) | No `.github/workflows/` directory. GitHub Actions files in `github_actions/` are templates, not active. No automated CI (linting, testing) runs on PRs. | Create `.github/workflows/ci.yml` with: install deps, run `pytest`, run frontend `vitest`, run ruff lint. | M | No active CI/CD pipeline |
| GAP-025 | **HIGH** | Report 04 (9.2), Report 07 (WS3) | CI/CD templates only cover GitHub Actions. Slides and Jira FEIP-5092 call for Jenkins, GitLab CI, Azure DevOps, CircleCI templates. | Create `cicd_templates/` directory with: `Jenkinsfile`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `.circleci/config.yml`. Each should demonstrate branch-per-PR Lakebase flow. Extend `agents/provisioning/cicd.py` with generator tools. | L | Missing CI/CD platform templates |
| GAP-026 | **MEDIUM** | Report 04 (9.2), Report 05 (FR-2) | Schema diff is generated by `migration.py` but never posted as a PR comment. No GitHub API integration for comment posting. | Add `agents/provisioning/cicd.py::post_schema_diff_to_pr()` tool that uses GitHub API (`gh api`) to post schema diff as PR comment. Add to GitHub Actions template. | M | Schema diff not posted to PRs |

---

### CONFIG

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-027 | **HIGH** | Report 01 (11.1), Report 02 (5.2) | `config/settings.py` previously had hardcoded infrastructure IDs. Current branch uses `os.getenv()` with empty defaults, but `app/app.yaml` may still contain hardcoded values. No `.env.example` documents all required variables. | Verify `app/app.yaml` env vars. Update `.env.example` to document ALL required environment variables including `LAKEBASE_PROJECT_ID`, `LAKEBASE_ENDPOINT_HOST`, `SQL_WAREHOUSE_ID`, `CORS_ORIGINS`. | S | Incomplete environment variable documentation |
| GAP-028 | **HIGH** | Report 01 (9), Report 04 (9.1) | No `databricks.yml` (Asset Bundles) in repo. `databricks_job_definitions.py` has a `generate_databricks_yml()` function but no actual bundle file. Design docs call for IaC. | Create `databricks.yml` at repo root with three targets (dev, staging, prod) defining all 7 jobs, app deployment, and dashboard. | L | No Databricks Asset Bundle |
| GAP-029 | **MEDIUM** | Report 02 (4.1) | No `pyproject.toml`. No linting (ruff), formatting (black), or type checking (mypy) configuration. No pre-commit hooks. | Create `pyproject.toml` with `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.mypy]` sections. Create `.pre-commit-config.yaml`. | S | No linting/formatting config |
| GAP-030 | **MEDIUM** | Report 01 (10.4) | No `Dockerfile` or container configuration. No `pyproject.toml` for packaging. Project uses `sys.path.insert` for imports. | Create `pyproject.toml` with proper package definition. Optionally create `Dockerfile` for local development. | M | No packaging or containerization |
| GAP-031 | **MEDIUM** | Report 00 (New Features 2026), Report 03 (3.3) | All three DABs targets (dev, staging, prod) in `generate_databricks_yml()` point to the same workspace. No environment separation. | Define separate workspace URLs per target in `databricks_job_definitions.py` or the future `databricks.yml`. Use variables for workspace-specific config. | S | No environment separation in IaC |

---

### DATA

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-032 | **HIGH** | Report 00 (Section 11: Lakehouse Sync), Report 08 (FEIP-5271) | Lakehouse Sync (CDC replication Lakebase -> Delta) is Beta since March 2026. Platform references synced tables for Lakehouse-to-Lakebase direction but has NO implementation for the reverse direction (Lakebase -> Lakehouse CDC). This is what FEIP-5271 "Centralized Lakebase Sync Monitor" targets. | Create `agents/health/lakehouse_sync.py` mixin with tools to: (1) configure Lakehouse Sync CDC pipelines, (2) monitor replication lag, (3) validate SCD Type 2 history in Delta targets. Add new Delta table `lakehouse_sync_status`. Add backend route `/api/operations/lakehouse-sync`. | L | Lakehouse Sync (CDC) not implemented |
| GAP-033 | **HIGH** | Report 00 (Budget policies and tags, Mar 2026) | Budget policies and custom tags for cost attribution are GA since March 2026. Platform has cost tracking via `system.billing.usage` but does NOT use the Lakebase-native tag API for project/branch tagging. | Update `agents/provisioning/project.py` to apply tags on project creation. Update `agents/health/operations.py` cost attribution to use native tags. Update `utils/lakebase_client.py` to support PATCH project with tags. | M | Budget policies and tags not utilized |
| GAP-034 | **MEDIUM** | Report 00 (Section 10: Catalogs), Report 06 (3.1) | `governance.py` has UC integration but does NOT use the Lakebase Catalog Registration API (`POST /api/2.0/postgres/catalogs`) to register Lakebase databases as UC catalogs. | Add `agents/provisioning/governance.py::register_lakebase_catalog()` tool using the Catalogs API. Add status monitoring. | M | Lakebase catalog registration not used |
| GAP-035 | **MEDIUM** | Report 00 (Data API / PostgREST) | Platform makes direct psycopg connections for all PG queries. The PostgREST Data API (GA for autoscaling) is not used anywhere, even though it could simplify the LiveStats page and reduce connection management overhead. | Evaluate replacing direct PG connections in `lakebase_service.py` with Data API calls for read operations. Create utility function for PostgREST queries. | M | PostgREST Data API not utilized |
| GAP-036 | **LOW** | Report 00 (Synced Tables API) | `agents/health/sync.py` validates sync status by comparing row counts between Lakebase and Delta, but does NOT use the Synced Tables API (`GET /api/2.0/postgres/synced_tables/{table_name}`) to check official sync status. | Update `agents/health/sync.py` to call the Synced Tables status API as an additional validation signal alongside row count comparison. | S | Synced Tables status API not used |

---

### AGENTS

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-037 | **HIGH** | Report 04 (9.1), Report 05 (FR-1), Report 06 (2.7) | `branching.py` has branch CRUD but no Git hook integration. No `create_branch_from_git_hook` or `manage_pr_branch_lifecycle` tools. Design docs and slides position this as P0. | Add two tools to `agents/provisioning/branching.py`: `create_branch_from_git_hook(git_ref, username)` and `manage_pr_branch_lifecycle(pr_number, action)`. Create `hooks/post-checkout.sh` template. | M | No Git hook integration for branching |
| GAP-038 | **HIGH** | Report 04 (9.6), Report 05 (FR-7), Report 06 (2.5) | No policy-as-code framework. Branch policies are hardcoded in `settings.py` (`TTL_POLICIES`, `BRANCH_NAMING`). Design docs call for declarative YAML/JSON policy config with enforcement. | Create `config/branch_policies.yaml` with policy definitions. Create `agents/provisioning/policy_engine.py` that loads, validates, and enforces policies. Update `branching.py` to check policies before branch operations. | L | No policy-as-code framework |
| GAP-039 | **MEDIUM** | Report 04 (9.5), Report 05 (FR-5) | No QA-specific branching tools. Design docs describe QA branch provisioning, destructive test support, and branch reset. | Add `agents/provisioning/branching.py::create_qa_branch()` and `reset_branch_to_parent()` tools. | M | No QA branch workflow support |
| GAP-040 | **MEDIUM** | Report 04 (9.9), Report 06 (4.3) | No agent attribution tracking. Design docs state 80%+ of branches are agent-created, but no tagging or tracking exists. | Add `creator_type` field (human/agent/CI) to branch creation in `branching.py`. Track in `branch_lifecycle` Delta table. Add analytics query. | S | No agent branch attribution |
| GAP-041 | **MEDIUM** | Report 00 (Read Replicas, HA), Report 05 (NFR-1) | Platform manages primary computes but has no tools for read replica management or high availability configuration (both GA since March 2026). | Add `agents/provisioning/project.py::manage_read_replicas()` and `configure_ha()` tools using the Endpoints API. | M | No read replica or HA management |
| GAP-042 | **MEDIUM** | Report 04 (9.9), Report 07 (WS1), Report 08 (FEIP-5433) | No MCP server for Lakebase branching. Jira FEIP-5433 calls for a Lakebase MCP Server hosted on Databricks Apps. Design docs position this as P1 for AI agent integration. | Create `mcp/` directory with MCP server exposing branch CRUD, schema diff, and governance tools. | XL | No Lakebase MCP server |
| GAP-043 | **LOW** | Report 04 (9.4), Report 06 (4.2) | No automated nightly branch reset. Design docs call for scheduling `reset_branch()` via Databricks Jobs. | Add `jobs/branch_reset_notebook.py` for nightly staging reset. Add job definition to `databricks_job_definitions.py`. | S | No automated nightly branch reset |

---

### DEPLOYMENT

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-044 | **HIGH** | Report 04 (Slides 11-12), Report 07 (FEIP-5484) | The lakebase-scm VS Code/Cursor extension exists in a separate repo (`kevin-hartman_data/lakebase-scm-extension`) but is not referenced or integrated with lakebase-ops-platform. No documentation linking the two. | Add documentation in README or create `integrations/` directory linking to the SCM extension. Consider shared configuration patterns. | S | SCM extension not integrated |
| GAP-045 | **MEDIUM** | Report 01 (8.1) | GitHub Actions templates in `github_actions/` are not in `.github/workflows/`. They are reference templates, not active CI for this repo. | In addition to GAP-024 (CI pipeline), move or symlink the Lakebase branch automation templates to a clearly named `templates/github-actions/` directory and document usage in README. | S | GitHub Actions templates mislocated |

---

### DOCS

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-046 | **HIGH** | Report 01 (13), Report 05 (Section 8) | No deployment runbook. No API documentation beyond auto-generated FastAPI docs. No contribution guidelines. No changelog. | Create `docs/DEPLOYMENT.md` (runbook), `docs/CONTRIBUTING.md`, `CHANGELOG.md`. FastAPI auto-docs are accessible at `/docs` but not documented. | M | Missing operational documentation |
| GAP-047 | **MEDIUM** | Report 05 (Section 15), Report 06 (Part 5) | Design docs define a Branch-Based Development Playbook, DBA Transition Guide, and Maturity Model. None exist in the repo. | Create `docs/playbook/` directory with `branch-based-development.md`, `dba-transition-guide.md`, `maturity-model.md`. These are content docs, not code. | M | Missing methodology documentation |
| GAP-048 | **MEDIUM** | Report 06 (2.3, 5.1-5.4) | Design doc defines 11 branch naming conventions and cheat sheets. These exist in `config/settings.py` as `BRANCH_NAMING` dict but are not documented for end users. | Create `docs/naming-conventions.md` covering both UC and Lakebase naming. Reference the mapping table from design doc Part 3. | S | Naming conventions not documented |
| GAP-049 | **LOW** | Report 04 (9.8), Report 05 (Section 12) | No "show me" demo workflow. `main.py` runs a 16-week simulation but it is not an agile workflow demo suitable for customer presentations. | Create `demo/agile_workflow_demo.py` with an end-to-end demo: create project, create branch, apply migration, run tests, schema diff, merge, cleanup. | M | No customer-facing demo workflow |

---

### JIRA ALIGNMENT

| Gap ID | Severity | Source | Current State | Required Changes | Complexity | Description |
|--------|----------|--------|---------------|------------------|------------|-------------|
| GAP-050 | **CRITICAL** | Report 08 (FEIP-5271) | FEIP-5271 "Centralized Lakebase Sync Monitor" is the **only CRITICAL priority ticket** in all of FEIP. It is unassigned and in Idea status. The lakebase-ops-platform has sync validation but NOT a centralized monitor covering Lakehouse Sync CDC. | Claim FEIP-5271. Implement GAP-032 (Lakehouse Sync CDC monitoring). Create centralized sync dashboard combining synced tables status + CDC replication lag + row count drift. This directly maps to the platform's mission. | L | FEIP-5271 not claimed or implemented |
| GAP-051 | **HIGH** | Report 08 (FEIP-3106) | FEIP-3106 "[Ops] Lakebase & Genie Field Intelligence Hub" (Rishi Ghose, In Progress) directly overlaps with lakebase-ops-platform. No coordination documented. | Coordinate with Rishi Ghose on FEIP-3106 to avoid duplication. Document relationship in README. Consider combining efforts or defining clear scope boundaries. | S | FEIP-3106 overlap not addressed |
| GAP-052 | **MEDIUM** | Report 08 (FEIP-1444) | FEIP-1444 "Lakebase cost attribution" is Blocked and unassigned. Platform has cost tracking via `system.billing.usage` and `cost_tracker_notebook.py`. Could help unblock this ticket. | Claim or offer assistance on FEIP-1444. The existing cost tracking + GAP-033 (native tags) would address this ticket's requirements. | M | FEIP-1444 cost attribution blocked |

---

## Implementation Priority Summary

### P0 -- Fix Immediately (7 gaps)

| Gap ID | Category | Description | Complexity |
|--------|----------|-------------|------------|
| GAP-001 | SECURITY | SQL injection patterns in routers | S |
| GAP-007 | BACKEND | Broken notebook imports in jobs/ | S |
| GAP-020 | TESTING | Zero Python unit tests for agents | XL |
| GAP-024 | CICD | No active CI/CD pipeline | M |
| GAP-050 | JIRA | Claim FEIP-5271 (CRITICAL sync monitor) | L |
| GAP-027 | CONFIG | Incomplete env var documentation | S |
| GAP-002 | SECURITY | CORS wildcard default | S |

### P1 -- Fix Soon (16 gaps)

| Gap ID | Category | Description | Complexity |
|--------|----------|-------------|------------|
| GAP-003 | SECURITY | UC masking propagation not validated | L |
| GAP-004 | SECURITY | No app-level auth middleware | M |
| GAP-008 | BACKEND | Alert channels not implemented | M |
| GAP-009 | BACKEND | No Pydantic response models | M |
| GAP-016 | FRONTEND | Missing Branches dashboard page | L |
| GAP-021 | TESTING | No SQL query validation tests | M |
| GAP-022 | TESTING | Incomplete backend router tests | M |
| GAP-025 | CICD | Missing CI/CD platform templates | L |
| GAP-028 | CONFIG | No Databricks Asset Bundle | L |
| GAP-029 | CONFIG | No linting/formatting config | S |
| GAP-032 | DATA | Lakehouse Sync (CDC) not implemented | L |
| GAP-033 | DATA | Budget policies and tags not utilized | M |
| GAP-037 | AGENTS | No Git hook integration for branching | M |
| GAP-038 | AGENTS | No policy-as-code framework | L |
| GAP-046 | DOCS | Missing operational documentation | M |
| GAP-051 | JIRA | FEIP-3106 overlap not addressed | S |

### P2 -- Improve Over Time (18 gaps)

| Gap ID | Category | Description | Complexity |
|--------|----------|-------------|------------|
| GAP-005 | SECURITY | No sensitive data inventory | M |
| GAP-006 | SECURITY | Private SDK API access | M |
| GAP-010 | BACKEND | Missing API pagination | M |
| GAP-011 | BACKEND | LakebaseClient god object | L |
| GAP-012 | BACKEND | No custom exception hierarchy | M |
| GAP-013 | BACKEND | Unbounded caches and blocking I/O | M |
| GAP-017 | FRONTEND | Missing Adoption Metrics page | L |
| GAP-018 | FRONTEND | Missing Branch Observability UI | M |
| GAP-019 | FRONTEND | Low frontend test coverage | M |
| GAP-023 | TESTING | No migration workflow integration test | L |
| GAP-026 | CICD | Schema diff not posted to PRs | M |
| GAP-030 | CONFIG | No packaging or containerization | M |
| GAP-031 | CONFIG | No environment separation in IaC | S |
| GAP-034 | DATA | Lakebase catalog registration not used | M |
| GAP-035 | DATA | PostgREST Data API not utilized | M |
| GAP-039 | AGENTS | No QA branch workflow support | M |
| GAP-040 | AGENTS | No agent branch attribution | S |
| GAP-041 | AGENTS | No read replica or HA management | M |

### P3 -- Nice to Have (11 gaps)

| Gap ID | Category | Description | Complexity |
|--------|----------|-------------|------------|
| GAP-014 | BACKEND | Duplicate enum definition | S |
| GAP-015 | BACKEND | Dependency inconsistencies | S |
| GAP-036 | DATA | Synced Tables status API not used | S |
| GAP-042 | AGENTS | No Lakebase MCP server | XL |
| GAP-043 | AGENTS | No automated nightly branch reset | S |
| GAP-044 | DEPLOYMENT | SCM extension not integrated | S |
| GAP-045 | DEPLOYMENT | GitHub Actions templates mislocated | S |
| GAP-047 | DOCS | Missing methodology documentation | M |
| GAP-048 | DOCS | Naming conventions not documented | S |
| GAP-049 | DOCS | No customer-facing demo workflow | M |
| GAP-052 | JIRA | FEIP-1444 cost attribution blocked | M |

---

## Grouped by Implementation Category (for Parallel Execution)

### SECURITY (6 gaps)
- GAP-001 (CRITICAL): SQL injection patterns -- `app/backend/routers/metrics.py`, `performance.py`, `operations.py`
- GAP-002 (HIGH): CORS wildcard -- `app/backend/main.py`, `app/app.yaml`
- GAP-003 (HIGH): UC masking validation -- `agents/provisioning/governance.py`, new job
- GAP-004 (HIGH): Auth middleware -- `app/backend/main.py`
- GAP-005 (MEDIUM): Sensitive data inventory -- `config/sensitive_columns.yaml`
- GAP-006 (MEDIUM): Private SDK access -- `app/backend/services/lakebase_service.py`

### BACKEND (9 gaps)
- GAP-007 (HIGH): Broken imports -- all files in `jobs/`
- GAP-008 (HIGH): Alert channels -- `utils/alerting.py`
- GAP-009 (HIGH): Pydantic models -- new `app/backend/models/`
- GAP-010 (MEDIUM): Pagination -- `app/backend/routers/`, `app/frontend/src/hooks/`
- GAP-011 (MEDIUM): God object refactor -- `utils/lakebase_client.py`
- GAP-012 (MEDIUM): Exception hierarchy -- new `utils/exceptions.py`
- GAP-013 (MEDIUM): Caches and blocking I/O -- `sql_service.py`, `lakebase_client.py`, `delta_writer.py`
- GAP-014 (LOW): Duplicate enum -- `config/settings.py`
- GAP-015 (LOW): Dependencies -- `requirements.txt`, `app/requirements.txt`

### FRONTEND (4 gaps)
- GAP-016 (HIGH): Branches page -- new `pages/Branches.tsx`, `App.tsx`, `Sidebar.tsx`
- GAP-017 (MEDIUM): Adoption Metrics page -- new `pages/AdoptionMetrics.tsx`
- GAP-018 (MEDIUM): Branch Observability UI -- extend `pages/Branches.tsx`
- GAP-019 (LOW): Frontend test coverage -- `app/frontend/src/__tests__/`

### AGENTS (7 gaps)
- GAP-037 (HIGH): Git hook integration -- `agents/provisioning/branching.py`, new `hooks/`
- GAP-038 (HIGH): Policy-as-code -- new `config/branch_policies.yaml`, new `policy_engine.py`
- GAP-039 (MEDIUM): QA branch workflow -- `agents/provisioning/branching.py`
- GAP-040 (MEDIUM): Agent attribution -- `agents/provisioning/branching.py`, `branch_lifecycle` table
- GAP-041 (MEDIUM): Read replica/HA management -- `agents/provisioning/project.py`
- GAP-042 (LOW): MCP server -- new `mcp/` directory
- GAP-043 (LOW): Nightly branch reset -- new job notebook

### TESTING (4 gaps)
- GAP-020 (CRITICAL): Agent unit tests -- new `tests/test_framework.py`, `tests/test_agents/`, `tests/test_utils/`
- GAP-021 (HIGH): SQL query tests -- new `tests/test_sql_queries.py`
- GAP-022 (HIGH): Router tests -- `app/backend/tests/test_routers.py`
- GAP-023 (MEDIUM): Migration workflow test -- new `tests/test_migration_workflow.py`

### CICD (3 gaps)
- GAP-024 (HIGH): Active CI pipeline -- new `.github/workflows/ci.yml`
- GAP-025 (HIGH): CI/CD platform templates -- new `cicd_templates/`
- GAP-026 (MEDIUM): Schema diff PR posting -- `agents/provisioning/cicd.py`

### CONFIG (5 gaps)
- GAP-027 (HIGH): Env var docs -- `.env.example`
- GAP-028 (HIGH): Asset Bundle -- new `databricks.yml`
- GAP-029 (MEDIUM): Linting config -- new `pyproject.toml`, `.pre-commit-config.yaml`
- GAP-030 (MEDIUM): Packaging -- `pyproject.toml`
- GAP-031 (MEDIUM): Environment separation -- `databricks_job_definitions.py`

### DATA (5 gaps)
- GAP-032 (HIGH): Lakehouse Sync CDC -- new `agents/health/lakehouse_sync.py`, new route
- GAP-033 (HIGH): Budget policies/tags -- `agents/provisioning/project.py`, `lakebase_client.py`
- GAP-034 (MEDIUM): Catalog registration -- `agents/provisioning/governance.py`
- GAP-035 (MEDIUM): PostgREST Data API -- `app/backend/services/lakebase_service.py`
- GAP-036 (LOW): Synced Tables API -- `agents/health/sync.py`

### DEPLOYMENT (2 gaps)
- GAP-044 (LOW): SCM extension integration -- README, new `integrations/`
- GAP-045 (LOW): Template location -- `github_actions/` -> `templates/`

### DOCS (4 gaps)
- GAP-046 (HIGH): Operational docs -- new `docs/DEPLOYMENT.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- GAP-047 (MEDIUM): Methodology docs -- new `docs/playbook/`
- GAP-048 (LOW): Naming conventions -- new `docs/naming-conventions.md`
- GAP-049 (LOW): Demo workflow -- new `demo/agile_workflow_demo.py`

### JIRA ALIGNMENT (3 gaps)
- GAP-050 (CRITICAL): Claim FEIP-5271 -- organizational action
- GAP-051 (HIGH): Coordinate FEIP-3106 -- organizational action
- GAP-052 (MEDIUM): Assist FEIP-1444 -- organizational action

---

## Complexity Distribution

| Complexity | Count | Examples |
|------------|-------|---------|
| **S** (Small, < 1 day) | 16 | GAP-001, GAP-002, GAP-007, GAP-014, GAP-015, GAP-027, GAP-029, GAP-031, GAP-036, GAP-040, GAP-043, GAP-044, GAP-045, GAP-048, GAP-051 |
| **M** (Medium, 1-3 days) | 23 | GAP-004, GAP-005, GAP-006, GAP-008, GAP-009, GAP-010, GAP-012, GAP-013, GAP-018, GAP-019, GAP-021, GAP-022, GAP-024, GAP-026, GAP-030, GAP-033, GAP-034, GAP-035, GAP-037, GAP-039, GAP-041, GAP-046, GAP-047, GAP-049, GAP-052 |
| **L** (Large, 3-7 days) | 11 | GAP-003, GAP-011, GAP-016, GAP-017, GAP-023, GAP-025, GAP-028, GAP-032, GAP-038, GAP-050 |
| **XL** (Extra Large, 1-2 weeks) | 2 | GAP-020, GAP-042 |

**Total estimated effort:** ~45-65 developer-days across all gaps.

---

*Report generated by Gap Analysis Engine on 2026-04-05.*
