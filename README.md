# LakebaseOps: Autonomous Database Operations Platform

> **v2.2** | 3 Agents | 51 Tools | 8 Source Engines | PostgreSQL 17

Automated DBA Operations, Monitoring & Migration Assessment for [Databricks Lakebase](https://docs.databricks.com/en/lakebase/index.html) (managed PostgreSQL 17).

A multi-agent system that automates critical DBA tasks — reducing DBA toil from 20+ hours/week to under 5 hours and MTTR from 4+ hours to under 30 minutes.

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment Guide](#deployment-guide)
- [Monitoring App](#monitoring-app)
- [Migration Assessment](#migration-assessment)
- [Project Structure](#project-structure)
- [Configuration Reference](#configuration-reference)
- [Development](#development)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

---

## Architecture

Three collaborative AI agents (51 tools total) coordinated by an `AgentFramework` with event bus and scheduler:

```
                         +----------------------+
                         |    AgentFramework     |
                         |     (Coordinator)     |
                         |  Event Bus + Scheduler|
                         +----------+-----------+
                                    |
               +--------------------+--------------------+
               |                    |                    |
    +----------+----------+  +-----+----------+  +-----+----------+
    |  Provisioning Agent |  | Performance    |  |  Health Agent   |
    |     (21 tools)      |  | Agent (14)     |  |    (16 tools)   |
    |  Day 0 / Day 1      |  |  Day 1+        |  |    Day 2        |
    +---------------------+  +----------------+  +----------------+
    | ProjectMixin        |  | MetricsMixin   |  | MonitoringMixin|
    | BranchingMixin      |  | IndexMixin     |  | SyncMixin      |
    | MigrationMixin      |  | MaintenanceMix |  | ArchivalMixin  |
    | CICDMixin           |  | OptimizationMix|  | ConnectionMixin|
    | GovernanceMixin     |  |                |  | OperationsMixin|
    | AssessmentMixin     |  |                |  | LakehouseSync  |
    | PolicyEngine        |  |                |  |                |
    +---------------------+  +----------------+  +----------------+
               |                     |                    |
               v                     v                    v
    +------------------------------------------------------------+
    |      sql/queries.py - Named SQL Constants (PG17)           |
    +------------------------------------------------------------+
    |  Lakebase (PostgreSQL 17)      |  Delta Lake (Unity Catalog)|
    |  psycopg3 + OAuth auto-refresh |  Spark SQL via SDK         |
    +------------------------------------------------------------+
```

### How the Agents Collaborate

| Agent | Role | When It Runs |
|-------|------|--------------|
| **Provisioning** | Project setup, branching, migrations, governance, assessment | Day 0-1 setup + on-demand |
| **Performance** | Metrics collection, index analysis, vacuum scheduling, query optimization | Continuous (scheduled jobs) |
| **Health** | System monitoring, alerting, self-healing, sync validation, archival | Continuous (scheduled jobs) |

Agents communicate via an event bus — e.g., when Provisioning creates a new branch, Performance and Health automatically start monitoring it.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.11 | Backend, agents, jobs |
| Node.js | >= 18 | Frontend build |
| [uv](https://docs.astral.sh/uv/) | latest | Python dependency management |
| [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) | >= 0.200 | Workspace deployment |

### Databricks Requirements

- A Databricks workspace with [Lakebase](https://docs.databricks.com/en/lakebase/index.html) enabled
- A Lakebase project with at least one branch (typically `main`)
- A SQL Warehouse (serverless recommended)
- A Unity Catalog with a catalog for operational data (default: `ops_catalog`)
- A [Service Principal](https://docs.databricks.com/en/admin/users-groups/service-principals.html) for the Databricks App (auto-created by `databricks apps deploy`)

---

## Quick Start

### Local Simulation (no external dependencies)

Run the full 5-phase simulation locally — all agents operate in `mock_mode=True`:

```bash
git clone https://github.com/suryasai87/lakebase-ops-platform.git
cd lakebase-ops-platform

uv sync
uv run python main.py
```

This demonstrates all 5 PRD phases:
1. **Foundation** — Ops catalog creation, metric collection, alerting
2. **Index & Vacuum** — Index analysis, vacuum scheduling, autovacuum tuning
3. **Sync & Branches** — OLTP-to-OLAP validation, branch lifecycle
4. **Cold Archival** — Data archival pipeline, unified access views
5. **AI Operations** — Query optimization, self-healing, NL DBA, capacity planning

### Run Tests

```bash
# All Python tests
uv run pytest -v

# Frontend tests
cd app/frontend && npm install && npm test
```

---

## Deployment Guide

### Option 1: Databricks Asset Bundles (Recommended)

The `databricks.yml` file defines a complete deployment bundle with 7 scheduled jobs and the monitoring app.

**Step 1: Configure your environment**

```bash
cp .env.example .env
# Edit .env with your workspace values (see Configuration Reference below)
```

**Step 2: Configure the Databricks CLI**

```bash
# Set up a CLI profile for your workspace
databricks configure --profile DEFAULT --host https://YOUR-WORKSPACE.cloud.databricks.com
```

**Step 3: Deploy with Asset Bundles**

```bash
# Dev deployment
databricks bundle deploy -t dev

# Staging deployment
databricks bundle deploy -t staging

# Production deployment
databricks bundle deploy -t prod
```

This creates:
- 7 serverless Databricks Jobs (metric collection, index analysis, vacuum scheduling, etc.)
- The monitoring app with all environment variables

**Step 4: Deploy the monitoring app**

```bash
# Build the frontend
cd app/frontend
npm install
npm run build
cd ../..

# Deploy to Databricks Apps
python app/deploy_to_databricks.py
```

The app deploys to port **8000** (Databricks Apps proxy forwards to this port).

**Step 5: Configure the service principal**

After the app deploys, Databricks creates a service principal. Grant it:
- `USE CATALOG` on your ops catalog
- `USE SCHEMA` on the ops schema
- `SELECT` on all operational tables
- Lakebase project access (for live PG metrics)

```sql
-- Run in a SQL editor
GRANT USE CATALOG ON CATALOG ops_catalog TO `<service-principal-app-id>`;
GRANT USE SCHEMA ON SCHEMA ops_catalog.lakebase_ops TO `<service-principal-app-id>`;
GRANT SELECT ON SCHEMA ops_catalog.lakebase_ops TO `<service-principal-app-id>`;
```

### Option 2: Manual Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for step-by-step manual deployment instructions.

### Post-Deployment Verification

1. Open the app URL in your browser
2. The **Dashboard** page should show KPI cards (initially with mock data)
3. Navigate to **Operations** → click "Sync All Jobs" to trigger the first data collection
4. After ~5 minutes, real metrics should appear on Dashboard and Performance pages

---

## Monitoring App

The full-stack monitoring app (FastAPI + React + MUI + Recharts) provides real-time visibility into your Lakebase environment.

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | KPI overview, assessment summary, migration timeline, cost comparison |
| Assessment | `/assessment` | 4-step migration assessment wizard with enrichment widgets |
| Agents | `/agents` | Agent status, tool inventory, event history |
| Performance | `/performance` | Slow query analysis, regression detection, pg_stat trends |
| Indexes | `/indexes` | Index recommendations (unused, bloated, missing, duplicate) |
| Operations | `/operations` | Vacuum status, sync validation, branch lifecycle, job triggers |
| Branches | `/branches` | Branch management, observability, policy enforcement |
| Live Stats | `/live` | Real-time pg_stat metrics from Lakebase |
| Adoption Metrics | `/adoption` | 9 KPIs tracking platform adoption and sprint trends |

### API Endpoints

**Core endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check (SQL warehouse connectivity) |
| `GET` | `/api/metrics/latest` | Latest collected metrics |
| `GET` | `/api/metrics/trends` | Metric trends over time |
| `GET` | `/api/performance/slow-queries` | Slow query analysis |
| `GET` | `/api/indexes/recommendations` | Index recommendations |
| `GET` | `/api/operations/vacuum-status` | Vacuum status |
| `GET` | `/api/agents/status` | Agent status and tool counts |
| `POST` | `/api/jobs/sync` | Trigger all 7 jobs |
| `GET` | `/api/jobs/list` | List jobs with status |

**Assessment endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/assessment/discover` | Discover source DB schema and extensions |
| `POST` | `/api/assessment/profile/{id}` | Profile workload (QPS, TPS, connections) |
| `POST` | `/api/assessment/readiness/{id}` | Score readiness (6 dimensions) |
| `POST` | `/api/assessment/blueprint/{id}` | Generate migration blueprint |
| `GET` | `/api/assessment/extension-matrix/{id}` | Extension/feature compatibility matrix |
| `GET` | `/api/assessment/timeline/{id}` | Migration timeline for Gantt chart |
| `GET` | `/api/assessment/cost-estimate/{id}` | Region-aware cost comparison |
| `GET` | `/api/assessment/regions/{engine}` | Available regions for a source engine |
| `GET` | `/api/assessment/history` | Past assessment profiles |

---

## Migration Assessment

The `AssessmentMixin` provides a 4-step pipeline for evaluating external databases for migration to Lakebase:

```
  Source DB (8 engines)
       |
  1. Discover ──→ Extension/Feature Compatibility Matrix
       |
  2. Profile ──→ QPS, TPS, connections, read/write ratio
       |
  3. Readiness ──→ Score against 6 dimensions
       |
  4. Blueprint ──→ 4-phase migration plan + Timeline Gantt + Cost Estimate
```

### Supported Source Engines

| Engine | Cloud | Key Differentiators |
|--------|-------|-------------------|
| Aurora PostgreSQL | AWS | IAM auth, I/O-optimized storage, RDS Proxy |
| RDS PostgreSQL | AWS | Standard managed PG, gp3 storage |
| Cloud SQL for PostgreSQL | GCP | Cloud SQL Auth Proxy, `google_ml_integration` |
| Azure Database for PostgreSQL | Azure | Entra ID auth, built-in PgBouncer |
| AlloyDB for PostgreSQL | GCP | Columnar engine, high-performance |
| Supabase PostgreSQL | Multi | `pg_graphql`, `pgjwt`, platform-managed |
| Self-Managed PostgreSQL | Any | Full extension control |
| Amazon DynamoDB | AWS | NoSQL cross-engine migration (GSI/LSI, Streams) |

### Assessment Page Enrichments

After running the pipeline, the Assessment page displays three widgets:
- **Extension/Feature Compatibility Matrix** — Color-coded per-item status (supported/workaround/unsupported)
- **Migration Timeline Gantt** — 4 phases with duration, effort, and risk level
- **Cost Estimation** — Source vs Lakebase pricing by region with formula tooltips

---

## Project Structure

```
lakebase-ops-platform/
├── pyproject.toml                       # Python config (uv, ruff, pytest, mypy)
├── databricks.yml                       # Databricks Asset Bundle (dev/staging/prod)
├── main.py                              # 5-phase simulation orchestrator
├── deploy_and_test.py                   # Real deployment + integration tests
├── .env.example                         # Environment variable template
├── LICENSE                              # Apache 2.0
│
├── agents/                              # 3 AI agents (mixin-based architecture)
│   ├── provisioning/                    # 21 tools: project, branching, migration, governance, assessment
│   ├── performance/                     # 14 tools: metrics, indexes, maintenance, optimization
│   └── health/                          # 16 tools: monitoring, sync, archival, connections, operations
│
├── app/                                 # Databricks App (full-stack monitoring)
│   ├── app.yaml                         # Databricks Apps deployment config (port 8000)
│   ├── backend/                         # FastAPI backend
│   │   ├── main.py                      # Entry point with auth middleware
│   │   ├── routers/                     # 9 API routers
│   │   ├── models/                      # Pydantic response models
│   │   └── services/                    # SQL service, Lakebase service
│   └── frontend/                        # React + MUI + Vite + Recharts
│       └── src/
│           ├── pages/                   # 10 pages (Dashboard, Assessment, Branches, ...)
│           ├── components/              # Reusable components (KPICard, DataTable, GanttChart, ...)
│           └── hooks/                   # useApiData (polling data fetcher)
│
├── config/                              # Configuration
│   ├── settings.py                      # Environment-driven settings (dataclasses)
│   ├── migration_profiles.py            # Assessment data models + SourceEngine enum
│   ├── pricing.py                       # Static pricing registry (per-engine, per-region)
│   ├── branch_policies.yaml             # Branch naming, TTL, protection rules
│   └── sensitive_columns.yaml           # Column masking patterns
│
├── utils/                               # Shared utilities
│   ├── databricks_auth.py               # Token management + SQL Statement Execution API
│   ├── lakebase_client.py               # OAuth-aware PostgreSQL client
│   ├── delta_writer.py                  # Unity Catalog Delta writer
│   ├── readiness_scorer.py              # 6-dimension readiness scoring
│   ├── blueprint_generator.py           # Engine-aware migration blueprint
│   ├── alerting.py                      # Multi-channel alert manager (Slack, PagerDuty, Email)
│   └── exceptions.py                    # Custom exception hierarchy
│
├── sql/                                 # Named SQL constants
│   ├── queries.py                       # 21 PG17 queries
│   └── assessment_queries.py            # Discovery + profiling SQL
│
├── framework/                           # Agent coordination
│   └── agent_framework.py               # BaseAgent, AgentFramework, EventBus
│
├── jobs/                                # Databricks Jobs (replace pg_cron)
│   ├── databricks_job_definitions.py    # 7 job specs
│   └── *_notebook.py                    # Individual job notebooks
│
├── tests/                               # Test suite
│   ├── conftest.py                      # Shared fixtures (mock agents, clients)
│   ├── test_assessment.py               # Assessment pipeline tests (incl. DynamoDB)
│   ├── test_framework.py                # AgentFramework tests
│   ├── test_migration_workflow.py        # End-to-end migration workflow tests
│   ├── test_sql_queries.py              # SQL constant validation
│   ├── test_agents/                     # Per-agent unit tests
│   └── test_utils/                      # Per-utility unit tests
│
├── dashboards/                          # 8 AI/BI dashboard SQL query sets
├── templates/github-actions/            # GitHub Actions for branch lifecycle
├── cicd_templates/                      # Jenkins, GitLab CI, Azure DevOps, CircleCI
├── docs/                                # Additional documentation
│   ├── DEPLOYMENT.md                    # Manual deployment guide
│   ├── CONTRIBUTING.md                  # Contributor guide
│   ├── naming-conventions.md            # Branch naming conventions
│   └── playbook/                        # Operational playbooks
└── hooks/                               # Git hooks (post-checkout)
```

---

## Configuration Reference

### Environment Variables

Copy `.env.example` to `.env` and configure. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABRICKS_HOST` | Yes | Workspace hostname (e.g., `my-workspace.cloud.databricks.com`) |
| `LAKEBASE_PROJECT_ID` | Yes | Lakebase project UUID |
| `SQL_WAREHOUSE_ID` | Yes | SQL Warehouse ID for Delta queries |
| `LAKEBASE_ENDPOINT_HOST` | Yes | Lakebase PG endpoint hostname |
| `LAKEBASE_ENDPOINT_PORT` | No | PG port (default: `5432`) |
| `OPS_CATALOG` | No | Unity Catalog name (default: `ops_catalog`) |
| `OPS_SCHEMA` | No | Schema name (default: `lakebase_ops`) |
| `LAKEBASE_JOB_IDS` | No | JSON map of job names to IDs (set after deploying jobs) |
| `CORS_ORIGINS` | No | Allowed CORS origins for the app |
| `LAKEBASE_LOCAL_DEV` | No | Set to `true` to skip auth middleware locally |

See `.env.example` for the complete list with descriptions.

### Alert Thresholds

Configured in `config/settings.py` via `AlertThresholds`:

| Metric | Warning | Critical | Auto-SOP |
|--------|---------|----------|----------|
| Cache hit ratio | < 99% | < 95% | Recommend CU increase |
| Connection utilization | > 70% | > 85% | Auto-terminate idle > 30min |
| Dead tuple ratio | > 10% | > 25% | Schedule VACUUM ANALYZE |
| Lock wait time | > 30s | > 120s | Log lock chain |
| Deadlocks/hour | > 2 | > 5 | Capture blocking queries |
| Slow query | > 5s | > 30s | Log EXPLAIN plan |
| TXID age | > 500M | > 1B | Emergency VACUUM FREEZE |
| Replication lag | > 10s | > 60s | Investigate network |

### Scheduled Jobs

7 Databricks Jobs replace pg_cron (unavailable in Lakebase):

| Job | Schedule | Timeout | Purpose |
|-----|----------|---------|---------|
| Metric Collector | Every 5 min | 5 min | pg_stat_statements + system health |
| Index Analyzer | Hourly | 10 min | Full index health check |
| Vacuum Scheduler | Daily 2 AM UTC | 60 min | Dead tuple analysis + VACUUM |
| Sync Validator | Every 15 min | 5 min | OLTP-to-OLAP sync validation |
| Branch Manager | Every 6 hours | 10 min | TTL enforcement + nightly reset |
| Cold Data Archiver | Weekly Sun 3 AM | 120 min | Archive old data to Delta |
| Cost Tracker | Daily 6 AM UTC | 10 min | Billing attribution analysis |

### Pricing Configuration

Cost estimates use a static pricing registry in `config/pricing.py`. To update:
1. Edit rates under `SOURCE_ENGINES` and/or `LAKEBASE_PRICING`
2. Update `last_verified` date for each modified engine
3. Bump `PRICING_VERSION` to the current month

---

## Development

### Setup

```bash
# Clone and install
git clone https://github.com/suryasai87/lakebase-ops-platform.git
cd lakebase-ops-platform
uv sync

# Frontend
cd app/frontend
npm install
cd ../..

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# All Python tests
uv run pytest -v

# Specific test file
uv run pytest tests/test_assessment.py -v

# Frontend tests
cd app/frontend && npm test

# With coverage
uv run pytest --cov=agents --cov=utils --cov=framework -v
```

### Linting & Formatting

```bash
# Python lint
uv run ruff check .

# Python format
uv run ruff format .

# Type checking
uv run mypy agents/ utils/ framework/ --ignore-missing-imports
```

### Frontend Development

```bash
cd app/frontend
npm run dev          # Vite dev server with HMR (port 5173)
```

Set `LAKEBASE_LOCAL_DEV=true` in your `.env` to skip auth middleware when running the backend locally.

### Adding a New Source Engine

1. Add to `SourceEngine` enum in `config/migration_profiles.py`
2. Add `_mock_discover_<engine>()` in `agents/provisioning/assessment.py`
3. Update `utils/blueprint_generator.py` dictionaries
4. Add scoring logic to `utils/readiness_scorer.py`
5. Add pricing to `config/pricing.py`
6. Update `ENGINE_LABELS` in `app/frontend/src/pages/Assessment.tsx`

---

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

**Quick summary:**
1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes with tests
3. Ensure `uv run ruff check .` and `uv run pytest` pass
4. Open a PR against `main`

---

## Key Design Decisions

1. **Databricks Jobs replace pg_cron** — All scheduling via native workspace integration
2. **Delta Lake for 90-day trending** — pg_stat_statements persisted for historical analysis
3. **Native pg_catalog over information_schema** — Faster, richer schema introspection
4. **Mixin-based modular agents** — Each agent composed of 5-7 focused mixins
5. **Mock mode for local development** — All external calls wrapped in mock-capable clients
6. **Event-driven coordination** — Provisioning → Performance → Health via EventType subscriptions
7. **Risk-stratified remediation** — Low-risk auto-executes, medium/high requires approval
8. **Static pricing registry** — Rates from official pricing pages, versioned and auditable
9. **Shared auth utilities** — Token management and SQL execution centralized in `utils/databricks_auth.py`

---

## Changelog

### v2.2 (2026-03-26)

- Added Amazon DynamoDB as 8th source engine (first NoSQL cross-engine migration)
- Introduced `ENGINE_KIND` discriminator for PostgreSQL vs NoSQL routing
- 52 gap fixes: SQL injection security fixes, branch management, Lakehouse Sync CDC, policy engine, adoption metrics
- Added 386 tests (352 Python + 34 frontend), CI/CD pipeline, pre-commit hooks
- Extracted shared `utils/databricks_auth.py` for token management
- Removed cross-layer `config → utils` import dependency
- Added Pydantic response models, pagination, and parameterized SQL queries

### v2.1 (2026-03-11)

- Added AlloyDB and Supabase as source engines (5 → 7)
- Extension Compatibility Matrix, Migration Timeline Gantt, Cost Estimation widgets
- Static pricing registry (`config/pricing.py`)
- 5 new assessment API endpoints

### v2.0 (2026-02-21)

- Mixin-based architecture (7 mixins for Provisioning, 4 for Performance, 5 for Health)
- PG17 extended columns (WAL, JIT) in pg_stat_statements
- Migration assessment pipeline (4-step wizard, 5 initial source engines)
- Centralized SQL in `sql/queries.py` (21 named constants)

### v1.0 (2026-01-15)

- Initial release: 3 agents, 47 tools, 7 scheduled jobs
- Full-stack monitoring app (FastAPI + React + MUI)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
