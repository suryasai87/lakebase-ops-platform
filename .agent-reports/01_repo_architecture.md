# LakebaseOps Platform -- Architectural Report

**Generated:** 2026-04-05
**Repository:** ~/lakebase-ops-platform
**Branch:** including_serverless_tags

---

## 1. Executive Summary

LakebaseOps is a multi-agent autonomous DBA platform for Databricks Lakebase (managed PostgreSQL 17). It automates routine database operations -- vacuum scheduling, index analysis, sync validation, branch lifecycle, cold archival -- using 3 collaborative AI agents with 47 registered tools. The platform includes a full-stack monitoring web application deployed to Databricks Apps.

**Key metrics:**
- 61 Python files, ~8,079 lines of Python
- 24 frontend TypeScript/TSX files, ~1,537 lines
- 3 agents (Provisioning, Performance, Health) with 47 tools total
- 7 operational Delta tables in Unity Catalog
- 8 scheduled Databricks Jobs (replacing pg_cron)
- Mock mode for local development; real mode for Databricks deployment

---

## 2. Directory Tree

```
lakebase-ops-platform/
|-- main.py                          # CLI orchestrator -- simulates full 16-week cycle
|-- deploy_and_test.py               # Deployment + 5-phase integration test harness
|-- requirements.txt                 # Root Python dependencies
|-- README.md                        # Architecture docs, tool inventory
|-- ENHANCED_PROMPT.md               # Original AI prompt (PRD spec)
|-- PRD_V2_ARCHITECTURE.md           # V2 architecture reference
|-- .gitignore
|
|-- framework/
|   |-- __init__.py
|   |-- agent_framework.py           # AgentFramework, BaseAgent, EventBus, TaskResult
|
|-- agents/
|   |-- __init__.py                  # Exports ProvisioningAgent, PerformanceAgent, HealthAgent
|   |-- provisioning/
|   |   |-- __init__.py
|   |   |-- agent.py                 # ProvisioningAgent (17 tools)
|   |   |-- project.py               # ProjectMixin -- project creation, ops catalog
|   |   |-- branching.py             # BranchingMixin -- branch CRUD, TTL, protection
|   |   |-- migration.py             # MigrationMixin -- DDL migrations, schema diff, 9-step testing
|   |   |-- cicd.py                  # CICDMixin -- GitHub Actions YAML generation
|   |   |-- governance.py            # GovernanceMixin -- RLS, UC integration, AI agent branching
|   |-- performance/
|   |   |-- __init__.py
|   |   |-- agent.py                 # PerformanceAgent (14 tools)
|   |   |-- metrics.py               # MetricsMixin -- pg_stat_statements persistence
|   |   |-- indexes.py               # IndexMixin -- unused/bloated/missing/duplicate/FK index detection
|   |   |-- maintenance.py           # MaintenanceMixin -- vacuum scheduling, TXID wraparound
|   |   |-- optimization.py          # OptimizationMixin -- AI query optimization, capacity forecast
|   |-- health/
|       |-- __init__.py
|       |-- agent.py                 # HealthAgent (16 tools)
|       |-- monitoring.py            # MonitoringMixin -- health metrics, threshold evaluation, SOP
|       |-- sync.py                  # SyncMixin -- OLTP-to-OLAP sync validation
|       |-- archival.py              # ArchivalMixin -- cold data identification and archival
|       |-- connections.py           # ConnectionMixin -- connection pool monitoring, idle cleanup
|       |-- operations.py            # OperationsMixin -- cost attribution, self-healing, NL DBA
|
|-- config/
|   |-- __init__.py
|   |-- settings.py                  # Centralized configuration (enums, thresholds, defaults)
|
|-- sql/
|   |-- __init__.py
|   |-- queries.py                   # 21 named SQL constants (native PG17 catalogs)
|
|-- utils/
|   |-- __init__.py
|   |-- lakebase_client.py           # OAuth-aware PG client + REST API + MockConnection
|   |-- delta_writer.py              # Delta Lake writer (mock/SQL API/PySpark modes)
|   |-- alerting.py                  # Multi-channel AlertManager (Slack/PagerDuty/Email/DBSQL)
|
|-- jobs/
|   |-- __init__.py
|   |-- databricks_job_definitions.py # 8 Databricks Job definitions (JSON specs)
|   |-- create_all_jobs.py            # Script to create all jobs via Databricks CLI
|   |-- metric_collector_notebook.py  # Notebook: persist pg_stat_statements + health metrics
|   |-- index_analyzer_notebook.py    # Notebook: full index health analysis
|   |-- vacuum_scheduler_notebook.py  # Notebook: vacuum/analyze scheduling
|   |-- sync_validator_notebook.py    # Notebook: OLTP-to-OLAP sync validation
|   |-- cold_archiver_notebook.py     # Notebook: cold data archival
|   |-- cost_tracker_notebook.py      # Notebook: cost attribution tracking
|   |-- branch_manager_notebook.py    # Notebook: branch TTL enforcement + monitoring
|
|-- dashboards/
|   |-- lakebase_ops_dashboard.sql    # DBSQL/Lakeview dashboard queries (10+ queries)
|
|-- github_actions/
|   |-- create_branch_on_pr.yml       # GH Actions: create Lakebase branch on PR open
|   |-- delete_branch_on_pr_close.yml # GH Actions: delete branch on PR close/merge
|
|-- app/                              # Databricks Apps monitoring dashboard
|   |-- app.yaml                      # Databricks Apps manifest (uvicorn, port 8000)
|   |-- requirements.txt              # App-specific dependencies
|   |-- build.py                      # Frontend build + copy to static/
|   |-- deploy_to_databricks.py       # Deployment script (create app, upload, deploy)
|   |-- backend/
|   |   |-- __init__.py
|   |   |-- main.py                   # FastAPI app with SPA fallback
|   |   |-- routers/
|   |   |   |-- health.py             # GET /api/health
|   |   |   |-- agents.py             # GET /api/agents/summary
|   |   |   |-- metrics.py            # GET /api/metrics/overview, /api/metrics/trends
|   |   |   |-- performance.py        # GET /api/performance/queries, /regressions
|   |   |   |-- indexes.py            # GET /api/indexes/recommendations
|   |   |   |-- operations.py         # GET /api/operations/vacuum, /sync, /branches, /archival
|   |   |   |-- lakebase.py           # GET /api/lakebase/realtime
|   |   |   |-- jobs.py               # Databricks Jobs management endpoints
|   |   |-- services/
|   |       |-- sql_service.py        # SQL Statement Execution API wrapper
|   |       |-- lakebase_service.py   # Lakebase REST API wrapper
|   |       |-- agent_service.py      # Agent simulation service
|   |-- frontend/
|   |   |-- package.json              # React 18 + MUI 5 + Framer Motion + Recharts
|   |   |-- vite.config.ts
|   |   |-- vitest.config.ts
|   |   |-- tsconfig.json
|   |   |-- index.html
|   |   |-- src/
|   |       |-- main.tsx              # React entry point
|   |       |-- App.tsx               # Router + layout
|   |       |-- theme.ts              # MUI theme
|   |       |-- hooks/useApiData.ts   # Data fetching hook
|   |       |-- components/
|   |       |   |-- AgentCard.tsx
|   |       |   |-- AnimatedLayout.tsx
|   |       |   |-- DataTable.tsx
|   |       |   |-- KPICard.tsx
|   |       |   |-- MetricsChart.tsx
|   |       |   |-- Sidebar.tsx
|   |       |   |-- StatusBadge.tsx
|   |       |-- pages/
|   |       |   |-- Dashboard.tsx
|   |       |   |-- Agents.tsx
|   |       |   |-- Performance.tsx
|   |       |   |-- Indexes.tsx
|   |       |   |-- Operations.tsx
|   |       |   |-- LiveStats.tsx
|   |       |-- __tests__/
|   |           |-- setup.ts
|   |           |-- App.test.tsx
|   |           |-- AgentCard.test.tsx
|   |           |-- DashboardPage.test.tsx
|   |           |-- DataTable.test.tsx
|   |           |-- KPICard.test.tsx
|   |-- static/                       # Built frontend output (gitignored)
|
|-- tests/
|   |-- __init__.py                   # Empty -- no test files exist
|
|-- .agent-reports/                   # Agent-generated reports (this file)
```

---

## 3. Entry Points

| Entry Point | Command | Purpose |
|---|---|---|
| `main.py` | `python main.py` | Run full 16-week simulation in mock mode |
| `deploy_and_test.py` | `python deploy_and_test.py [--phase X]` | Deploy to real Databricks + integration tests (5 phases) |
| `app/backend/main.py` | `uvicorn backend.main:app` | FastAPI monitoring dashboard (via app.yaml) |
| `app/build.py` | `python app/build.py` | Build frontend and copy to static/ |
| `app/deploy_to_databricks.py` | `python app/deploy_to_databricks.py` | Deploy app to Databricks Apps |
| `jobs/create_all_jobs.py` | `python jobs/create_all_jobs.py` | Create all 8 Databricks Jobs via CLI |

---

## 4. Agent Architecture

### 4.1 AgentFramework (Coordinator)

**File:** `framework/agent_framework.py` (311 lines)

Core components:
- **BaseAgent** (ABC): Abstract base with tool registration, execution tracking, event emission
- **AgentFramework**: Agent registry, event bus (pub/sub), shared state, full-cycle orchestrator
- **EventType** enum: 11 event types (BRANCH_CREATED, THRESHOLD_BREACHED, VACUUM_COMPLETED, etc.)
- **TaskResult**: Standardized result with status, timing, data payload
- **AgentTool**: Registered callable with schedule, risk level, approval flag

Execution order in `run_full_cycle()`:
1. Provisioning Agent (sequential)
2. Performance Agent + Health Agent (parallel via asyncio.gather)

### 4.2 Provisioning Agent (17 tools)

**Files:** `agents/provisioning/` -- 5 mixin modules

| Mixin | Responsibility | PRD Reference |
|---|---|---|
| ProjectMixin | Project creation, ops catalog setup | Tasks 1-4, Phase 1.1 |
| BranchingMixin | Branch CRUD, TTL enforcement, protection, PR lifecycle | Tasks 5-21, FR-06 |
| MigrationMixin | Idempotent DDL, schema diff via pg_catalog, 9-step testing | Tasks 22-25, FR-08 |
| CICDMixin | GitHub Actions YAML generation for branch automation | Tasks 26-32 |
| GovernanceMixin | RLS, Unity Catalog integration, AI agent branching | Tasks 33-36, 50-57 |

### 4.3 Performance Agent (14 tools)

**Files:** `agents/performance/` -- 4 mixin modules

| Mixin | Responsibility | PRD Reference |
|---|---|---|
| MetricsMixin | pg_stat_statements persistence (PG17 columns: WAL, JIT) | FR-01 |
| IndexMixin | 5-way index health: unused, bloated, missing, duplicate, FK | FR-02 |
| MaintenanceMixin | VACUUM/ANALYZE scheduling, TXID wraparound detection | FR-03, UC-09 |
| OptimizationMixin | AI query optimization (LLM-powered), capacity forecasting | UC-12, UC-15 |

### 4.4 Health Agent (16 tools)

**Files:** `agents/health/` -- 5 mixin modules

| Mixin | Responsibility | PRD Reference |
|---|---|---|
| MonitoringMixin | 8 health metrics, threshold evaluation (warning/critical) | FR-04 |
| SyncMixin | OLTP-to-OLAP sync validation (count, timestamp, checksum) | FR-05 |
| ArchivalMixin | Cold data identification (90-day) and archival to Delta | FR-07 |
| ConnectionMixin | Connection pool monitoring, idle session termination | UC-10 |
| OperationsMixin | Cost attribution, self-healing, NL DBA (V2 AI features) | UC-11, UC-13, UC-14 |

---

## 5. Data Architecture

### 5.1 Delta Lake Tables (Unity Catalog)

All tables live in `hls_amer_catalog.lakebase_ops`:

| Table | Partitioning | Write Frequency | Purpose |
|---|---|---|---|
| `pg_stat_history` | project_id, branch_id | Every 5 min | Query performance metrics |
| `index_recommendations` | None | Hourly | Index health findings |
| `vacuum_history` | None | Daily | VACUUM/ANALYZE operation logs |
| `lakebase_metrics` | project_id, metric_name | Every 5 min | 8 health metrics |
| `sync_validation_history` | None | Every 15 min | OLTP-to-OLAP sync status |
| `branch_lifecycle` | None | On event | Branch create/delete/protect events |
| `data_archival_history` | None | Weekly | Cold data archival operations |

Table creation DDL is in `utils/delta_writer.py` (`create_ops_catalog_and_schemas()`).

### 5.2 SQL Queries

**File:** `sql/queries.py` -- 21 named SQL constants

All queries use native PostgreSQL catalogs (`pg_catalog.*`), not `information_schema`. Categories:
- FR-01: pg_stat_statements (full, info, slow)
- FR-02: Index health (unused, bloated, missing, duplicate, FK)
- FR-03: Vacuum candidates, TXID wraparound
- FR-04: Database stats, connection states, dead tuples, locks, TXID age, I/O, WAL
- UC-10: Connection details, idle connections
- FR-08: Schema columns via pg_catalog

---

## 6. Web Application (Databricks Apps)

### 6.1 Backend

**Stack:** FastAPI + uvicorn, port 8000

**Routers** (8 route modules):

| Router | Endpoints |
|---|---|
| health | `/api/health` |
| agents | `/api/agents/summary` |
| metrics | `/api/metrics/overview`, `/api/metrics/trends` |
| performance | `/api/performance/queries`, `/api/performance/regressions` |
| indexes | `/api/indexes/recommendations` |
| operations | `/api/operations/vacuum`, `/sync`, `/branches`, `/archival` |
| lakebase | `/api/lakebase/realtime` |
| jobs | Databricks Jobs CRUD endpoints |

**Services** (3 service modules):
- `sql_service.py`: SQL Statement Execution API wrapper
- `lakebase_service.py`: Lakebase REST API wrapper (branches, credentials, pg connections)
- `agent_service.py`: Agent simulation service

### 6.2 Frontend

**Stack:** React 18 + TypeScript + Vite + MUI 5 + Framer Motion + Recharts

**Pages** (6):
- Dashboard: KPI overview with charts
- Agents: Agent status cards
- Performance: Query performance tables
- Indexes: Index recommendation table
- Operations: Vacuum, sync, branch, archival views
- LiveStats: Real-time Lakebase metrics

**Components** (7): AgentCard, AnimatedLayout, DataTable, KPICard, MetricsChart, Sidebar, StatusBadge

**Tests** (5 test files): App, AgentCard, DashboardPage, DataTable, KPICard

### 6.3 Deployment

- `app.yaml`: Databricks Apps manifest -- runs `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- Environment variables: OPS_CATALOG, OPS_SCHEMA, SQL_WAREHOUSE_ID, LAKEBASE_PROJECT_ID, LAKEBASE_ENDPOINT_HOST
- `deploy_to_databricks.py`: 4-step deploy (build frontend, create app, upload source, deploy)
- `build.py`: npm install + build, copy `dist/` to `static/`

---

## 7. Scheduled Jobs (Databricks Jobs)

**File:** `jobs/databricks_job_definitions.py`

These replace pg_cron (unavailable in Lakebase):

| Job | Schedule | Notebook | PRD |
|---|---|---|---|
| metric_collector | Every 5 min | metric_collector_notebook.py | FR-01, FR-04 |
| index_analyzer | Hourly | index_analyzer_notebook.py | FR-02 |
| vacuum_scheduler | Daily 2 AM | vacuum_scheduler_notebook.py | FR-03 |
| sync_validator | Every 15 min | sync_validator_notebook.py | FR-05 |
| branch_manager | Every 6 hours | branch_manager_notebook.py | FR-06 |
| cold_archiver | Weekly Sun 3 AM | cold_archiver_notebook.py | FR-07 |
| connection_monitor | Every minute | (defined in settings) | UC-10 |
| cost_tracker | Daily 6 AM | cost_tracker_notebook.py | UC-11 |

Each notebook imports agents from the root project and executes the relevant tools.

---

## 8. CI/CD Pipeline Definitions

### 8.1 GitHub Actions (Template Workflows)

**Location:** `github_actions/` (NOT `.github/workflows/` -- these are templates, not active)

| File | Trigger | Action |
|---|---|---|
| `create_branch_on_pr.yml` | `pull_request: [opened, reopened]` | Create ephemeral Lakebase branch `ci-pr-{N}`, apply migrations, run tests, post schema diff |
| `delete_branch_on_pr_close.yml` | `pull_request: [closed]` | Delete ephemeral branch; if merged, replay migrations to staging + production |

**Required secrets:** `DATABRICKS_HOST`, `DATABRICKS_TOKEN`
**Required variables:** `LAKEBASE_PROJECT`

### 8.2 No Active CI/CD

There is no `.github/workflows/` directory. The `github_actions/` directory contains reference templates meant to be copied into consuming repositories. The repo itself has no automated CI, linting, or test pipeline.

---

## 9. Infrastructure-as-Code

**No Terraform, Pulumi, ARM templates, CloudFormation, or Databricks Asset Bundles (databricks.yml) are present.**

Infrastructure is managed through:
- Python scripts (`deploy_and_test.py`, `jobs/create_all_jobs.py`)
- Databricks CLI commands (invoked from Python via subprocess)
- SQL DDL in `delta_writer.py` (creates catalogs, schemas, tables)
- REST API calls to Databricks workspace

---

## 10. Dependencies

### 10.1 Root Python (`requirements.txt`)

```
databricks-sdk>=0.81.0
psycopg[binary]>=3.0
psycopg2-binary>=2.9
pytest>=7.0
pytest-asyncio>=0.21
# Optional: pyspark>=3.5.0
# Optional: databricks-genai-inference>=0.1.0
```

### 10.2 App Python (`app/requirements.txt`)

```
databricks-sdk>=0.40.0
fastapi>=0.104.0
uvicorn>=0.24.0
psycopg[binary]>=3.0
```

### 10.3 Frontend (`app/frontend/package.json`)

**Runtime:** react 18, react-dom, react-router-dom 6, @mui/material 5, @mui/icons-material, @emotion/react, @emotion/styled, framer-motion 11, recharts 2
**Dev:** typescript 5, vite 5, vitest 2, @vitejs/plugin-react, @testing-library/react 14, jsdom 24

### 10.4 Notable Absent Dependencies

- No `pyproject.toml`, `setup.cfg`, or `setup.py` -- not packaged as a distributable Python package
- No `Pipfile` or `poetry.lock`
- No `Dockerfile` or container config

---

## 11. Environment Configuration and Secrets

### 11.1 Hardcoded Configuration (`config/settings.py`)

| Setting | Value | Notes |
|---|---|---|
| WORKSPACE_HOST | `fe-vm-hls-amer.cloud.databricks.com` | Databricks workspace |
| DEFAULT_CATALOG | `hls_amer_catalog` | Unity Catalog |
| OPS_SCHEMA | `lakebase_ops` | Operational schema |
| ARCHIVE_SCHEMA | `lakebase_archive` | Archive schema |
| SQL_WAREHOUSE_ID | `8e4258d7fe74671b` | Serverless Demo warehouse |
| LAKEBASE_PROJECT_ID | `83eb266d-27f8-4467-a7df-2b048eff09d7` | Real Lakebase project |
| LAKEBASE_ENDPOINT_HOST | `ep-hidden-haze-d2v9brhq.database.us-east-1.cloud.databricks.com` | PG endpoint |
| LAKEBASE_DB_NAME | `databricks_postgres` | Default database |
| LAKEBASE_PG_VERSION | 17 | PostgreSQL version |

### 11.2 App Environment (`app/app.yaml`)

Same values passed as env vars: OPS_CATALOG, OPS_SCHEMA, SQL_WAREHOUSE_ID, LAKEBASE_PROJECT_ID, LAKEBASE_ENDPOINT_HOST.

### 11.3 Secrets Handling

- **No `.env` file** (gitignored)
- **No secrets in code** -- authentication uses `databricks auth token --profile DEFAULT` (CLI-based OAuth)
- GitHub Actions templates reference `secrets.DATABRICKS_HOST` and `secrets.DATABRICKS_TOKEN`
- OAuth tokens auto-refresh at 50 minutes (before 1-hour expiry)

---

## 12. Testing

### 12.1 Backend Tests

- `tests/__init__.py` exists but is **empty** -- no Python unit tests
- `deploy_and_test.py` is a comprehensive 5-phase integration test harness (2,091 lines) that tests all 47 tools against real infrastructure
- The `main.py` orchestrator runs a full simulation in mock mode, acting as a smoke test

### 12.2 Frontend Tests

5 Vitest test files in `app/frontend/src/__tests__/`:
- `App.test.tsx`
- `AgentCard.test.tsx`
- `DashboardPage.test.tsx`
- `DataTable.test.tsx`
- `KPICard.test.tsx`

Run with: `cd app/frontend && npm run test`

---

## 13. Documentation Quality

| Document | Lines | Quality | Notes |
|---|---|---|---|
| `README.md` | 410+ | **Strong** | Full architecture diagram, all 47 tools documented, PRD mapping |
| `PRD_V2_ARCHITECTURE.md` | 470+ | **Strong** | V2 changelog, PG17 columns, native catalog migration |
| `ENHANCED_PROMPT.md` | 560+ | **Good** | Original AI prompt / PRD spec with all use cases |
| Code docstrings | Throughout | **Good** | All agents, mixins, utils have clear module-level docstrings |
| Inline comments | Moderate | **Adequate** | Key decisions documented, PRD references included |

**Gaps:**
- No API documentation (OpenAPI/Swagger auto-generated by FastAPI but not explicitly documented)
- No deployment runbook beyond the script flags
- No contribution guidelines
- No changelog

---

## 14. Key Findings and Observations

### Strengths

1. **Clean mixin-based architecture**: Each agent composes 4-5 mixins, keeping files focused and navigable
2. **Mock mode throughout**: Every external call (Lakebase, Delta, alerts) has a mock path for local development
3. **Event-driven coordination**: Agents communicate through a typed event bus, enabling loose coupling
4. **Comprehensive SQL library**: 21 named query constants using native PG17 catalogs
5. **Three data paths for Delta writes**: Mock, SQL Statement API (no PySpark needed), and PySpark
6. **Strong PRD traceability**: Every tool maps to a specific PRD requirement (FR-01 through FR-08, UC-09 through UC-15)

### Risks and Gaps

1. **No active CI/CD**: The GitHub Actions files are templates in `github_actions/`, not active in `.github/workflows/`
2. **No Python unit tests**: `tests/` directory is empty; all testing relies on the integration harness or mock simulation
3. **Hardcoded infrastructure IDs**: Workspace host, project IDs, warehouse IDs, and endpoint hosts are in `config/settings.py` with no environment-variable override
4. **No IaC**: Infrastructure created imperatively via Python scripts and CLI; no Terraform, DABs, or declarative config
5. **No packaging**: No `pyproject.toml` or `setup.py`; project relies on `sys.path.insert` for imports
6. **Duplicate psycopg dependencies**: Root `requirements.txt` lists both `psycopg[binary]>=3.0` and `psycopg2-binary>=2.9` (different drivers); only psycopg3 is actually used in code
7. **App SDK version mismatch**: Root requires `databricks-sdk>=0.81.0`, app requires `>=0.40.0`
