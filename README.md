# LakebaseOps: Autonomous Lakebase Database Operations Platform

> **v2.2** | 3 Agents | 51 Tools | 8 Source Engines | PostgreSQL 17

**Automated DBA Operations, Monitoring & OLTP-to-OLAP Lifecycle Management**

A multi-agent system that automates critical DBA tasks for Databricks Lakebase (managed PostgreSQL 17), reducing DBA toil from 20+ hours/week to under 5 hours and MTTR from 4+ hours to under 30 minutes.

---

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Monitoring App Pages](#monitoring-app-pages)
- [Project Structure](#project-structure-v2--modular-mixin-architecture)
- [Alert Thresholds](#alert-thresholds-fr-04)
- [Success Metrics](#success-metrics)
- [PG17 Features Leveraged](#pg17-features-leveraged)
- [Scheduled Jobs](#scheduled-jobs-databricks-jobs)
- [API Endpoints](#job-api-endpoints-app-backend)
- [Pricing Configuration](#pricing-configuration-configpricingpy)
- [Key Design Decisions](#key-design-decisions)
- [Development](#development)
- [Changelog](#changelog)

---

## Architecture

The platform consists of **3 collaborative AI agents** (51 tools total) coordinated by an `AgentFramework`, with a modular mixin-based architecture:

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
    | AssessmentMixin     |  |                |  |                |
    | (8 engines)         |  |                |  |                |
    +----------+----------+  +-------+--------+  +-------+--------+
               |                     |                    |
               v                     v                    v
    +------------------------------------------------------------+
    |      sql/queries.py - Named SQL Constants (PG17)           |
    +------------------------------------------------------------+
    |  Lakebase (PostgreSQL 17)      |  Delta Lake (Unity Catalog)|
    |  psycopg3 + OAuth auto-refresh |  Spark SQL via SDK         |
    +------------------------------------------------------------+
```

### Migration Assessment Pipeline

The `AssessmentMixin` provides a 4-step pipeline for evaluating external databases for migration to Lakebase. Supports both PostgreSQL engines and NoSQL sources (DynamoDB):

```
  Source DB (8 engines supported)
       |
       v
  1. Discover - schema, extensions/features, functions, triggers, edge cases
       |                                      +---------------------------+
       +------------------------------------->| Extension / Feature       |
       |                                      | Compatibility Matrix      |
       v                                      | (per-item supported/      |
  2. Profile  - QPS, TPS, connections,        | workaround/unsupported)   |
       |        read/write ratio              +---------------------------+
       v
  3. Readiness - score against Lakebase constraints (6 dimensions)
       |
       v
  4. Blueprint - 4-phase migration plan with effort estimates
       |
       +---> Migration Timeline (Gantt view of 4 phases)
       +---> Cost Estimation (source vs Lakebase, per-region pricing)
```

**Supported source engines:**

| Engine | Cloud | Key Differentiators |
|--------|-------|-------------------|
| Aurora PostgreSQL | AWS | IAM auth, I/O-optimized storage, RDS Proxy |
| RDS PostgreSQL | AWS | Standard managed PG, gp3 storage |
| Cloud SQL for PostgreSQL | GCP | Cloud SQL Auth Proxy, `google_ml_integration` |
| Azure Database for PostgreSQL | Azure | Entra ID auth, built-in PgBouncer, `azure_storage` |
| AlloyDB for PostgreSQL | GCP | Columnar engine, `google_ml_integration`, high-perf |
| Supabase PostgreSQL | Multi | `pg_graphql`, `pgjwt`, platform-managed auth/storage/realtime schemas |
| Self-Managed PostgreSQL | Any | Full extension control, `timescaledb`, `citus`, `pglogical` |
| Amazon DynamoDB | AWS | NoSQL cross-engine migration, GSI/LSI, Streams, on-demand/provisioned billing |

### Agent 1: Provisioning & DevOps (21 tools)

Automates "Day 0" and "Day 1" - the 59 setup tasks from the Enterprise Lakebase Design Guide, plus the 4-step migration assessment pipeline:

| Tool | Module | Description | PRD Reference |
|------|--------|-------------|---------------|
| `provision_lakebase_project` | project | Create project with full branch hierarchy | Tasks 1-15 |
| `create_ops_catalog` | project | Create Unity Catalog ops tables | Phase 1.1 |
| `create_branch` | branching | Branch with naming conventions + TTL | Tasks 5-15 |
| `protect_branch` | branching | Mark branch as protected | Tasks 16-17 |
| `enforce_ttl_policies` | branching | Scan and delete expired branches | Task 18, FR-06 |
| `monitor_branch_count` | branching | Alert on approaching 10-branch limit | Task 19, FR-06 |
| `reset_branch_from_parent` | branching | Nightly staging reset | Task 40 |
| `create_branch_on_pr` | branching | Auto-create ephemeral branch on PR open | FR-06 |
| `delete_branch_on_pr_close` | branching | Auto-delete branch on PR merge/close | FR-06 |
| `apply_schema_migration` | migration | Idempotent DDL migrations | Tasks 22-25 |
| `capture_schema_diff` | migration | Schema diff via native PG catalogs | FR-08 |
| `test_migration_on_branch` | migration | Full 9-step migration testing | FR-08 |
| `setup_cicd_pipeline` | cicd | Generate GitHub Actions YAML | Tasks 26-32 |
| `configure_rls` | governance | Row-level security setup | Tasks 33-36 |
| `setup_unity_catalog_integration` | governance | UC governance alignment | Tasks 50-54 |
| `setup_ai_agent_branching` | governance | AI agent branching config | Tasks 55-57 |
| `provision_with_governance` | governance | Full project setup with all governance | Combined |
| `connect_and_discover` | assessment | Discover source DB schema, extensions, features (8 engines) | Migration |
| `profile_workload` | assessment | Analyze QPS, TPS, connections, read/write ratio | Migration |
| `assess_readiness` | assessment | Score against Lakebase constraints (6 dimensions) | Migration |
| `generate_migration_blueprint` | assessment | 4-phase migration plan with effort estimates | Migration |

### Agent 2: Performance & Optimization (14 tools)

Addresses the core problem that **pg_cron is unavailable** and persists **pg_stat_statements to Delta for 90-day trending and cross-branch comparison**. Leverages PG17 extended columns (WAL, JIT) and native `pg_catalog` for real index detection:

| Tool | Module | Description | PRD Reference |
|------|--------|-------------|---------------|
| `persist_pg_stat_statements` | metrics | Capture full PG17 columns to Delta every 5 min | FR-01 |
| `detect_unused_indexes` | indexes | idx_scan=0 for 7+ days | FR-02 |
| `detect_bloated_indexes` | indexes | Bloat ratio > 2.0x | FR-02 |
| `detect_missing_indexes` | indexes | seq_scan >> idx_scan | FR-02 |
| `detect_duplicate_indexes` | indexes | pg_index self-join on matching indkey | FR-02 |
| `detect_missing_fk_indexes` | indexes | pg_constraint + pg_index for unindexed FKs | FR-02 |
| `run_full_index_analysis` | indexes | Complete index health check | FR-02 |
| `identify_tables_needing_vacuum` | maintenance | Dead tuple analysis | FR-03 |
| `schedule_vacuum_analyze` | maintenance | VACUUM ANALYZE (replaces pg_cron) | FR-03 |
| `schedule_vacuum_full` | maintenance | VACUUM FULL with lock awareness | FR-03 |
| `check_txid_wraparound_risk` | maintenance | XID age monitoring | FR-03 |
| `tune_autovacuum_parameters` | maintenance | Per-table threshold tuning | UC-09 |
| `analyze_slow_queries_with_ai` | optimization | LLM-powered query analysis | UC-12 |
| `forecast_capacity_needs` | optimization | ML-based capacity planning | UC-15 |

### Agent 3: Health & Self-Recovery (16 tools)

Continuous monitoring with **8 alerting thresholds**, **pg_stat_io/wal collection**, and **automated self-healing**:

| Tool | Module | Description | PRD Reference |
|------|--------|-------------|---------------|
| `monitor_system_health` | monitoring | Collect pg_stat + pg_stat_io + pg_stat_wal metrics | FR-04 |
| `evaluate_alert_thresholds` | monitoring | Check 8 metrics vs thresholds | FR-04 |
| `execute_low_risk_sop` | monitoring | Auto-remediate safe issues | FR-04 |
| `validate_sync_completeness` | sync | Row count + timestamp check | FR-05 |
| `validate_sync_integrity` | sync | Checksum verification | FR-05 |
| `run_full_sync_validation` | sync | Complete sync cycle | FR-05 |
| `identify_cold_data` | archival | Find rows > 90 days old | FR-07 |
| `archive_cold_data_to_delta` | archival | Full archival pipeline | FR-07 |
| `create_unified_access_view` | archival | Hot+cold unified view | FR-07 |
| `monitor_connections` | connections | Active/idle tracking | UC-10 |
| `terminate_idle_connections` | connections | Kill idle > 30 min | UC-10 |
| `track_cost_attribution` | operations | Billing analysis | UC-11 |
| `recommend_scale_to_zero_timeout` | operations | Optimize idle timeout | UC-11 |
| `diagnose_root_cause` | operations | Correlate metrics for RCA | UC-13 |
| `self_heal` | operations | Execute approved auto-fix | UC-13 |
| `natural_language_dba` | operations | "Why is my query slow?" | UC-14 |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.10 | Backend, agents, simulation |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |
| [Bun](https://bun.sh/) | latest | Frontend package manager |
| [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) | >= 0.200 | Workspace deployment and job management |

## Quick Start

### Local Simulation (no external dependencies)

```bash
cd lakebase-ops-platform
uv sync
uv run python main.py
```

Output demonstrates all 5 PRD phases:
1. **Foundation** - Ops catalog creation, metric collection, alerting
2. **Index & Vacuum** - Index analysis, vacuum scheduling, autovacuum tuning
3. **Sync & Branches** - OLTP-to-OLAP validation, branch lifecycle
4. **Cold Archival** - Data archival pipeline, unified access views
5. **AI Operations** - Query optimization, self-healing, NL DBA, capacity planning

### Deploy to Databricks Apps

1. **Configure environment** - Copy `.env.example` to `.env` and fill in your workspace values:

```bash
cp .env.example .env
```

Required variables (see `.env.example` for full list):

| Variable | Description |
|----------|-------------|
| `DATABRICKS_HOST` | Workspace URL (e.g., `your-workspace.cloud.databricks.com`) |
| `LAKEBASE_PROJECT_ID` | Lakebase project ID |
| `SQL_WAREHOUSE_ID` | SQL warehouse for Delta queries |
| `LAKEBASE_ENDPOINT_HOST` | Lakebase endpoint hostname |

2. **Build the frontend**:

```bash
cd app/frontend
bun install
bun run build
cd ../..
```

3. **Deploy** - Upload the `app/` directory to your Databricks workspace and deploy:

```bash
databricks apps deploy <app-name> \
  --source-code-path /Workspace/Users/<you>/<app-source> \
  --profile <your-profile>
```

4. **Create scheduled jobs** (optional) - Deploy the 7 Databricks Jobs for continuous monitoring:

```bash
uv run python jobs/databricks_job_definitions.py
```

### Monitoring App Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | KPI overview, latest assessment summary, migration timeline Gantt, cost comparison |
| Agents | `/agents` | Agent status and tool inventory |
| Performance | `/performance` | Slow query analysis and regression detection |
| Indexes | `/indexes` | Index recommendations |
| Operations | `/operations` | Vacuum, sync, branches, archival |
| Live Stats | `/live` | Real-time Lakebase pg_stat metrics |
| Assessment | `/assessment` | Migration assessment pipeline (4-step wizard) with enrichments |

### Assessment Page Enrichments

After running the 4-step assessment pipeline, the Assessment page displays three additional widgets:

- **Extension Compatibility Matrix** - Color-coded table showing each source extension's Lakebase status (supported / workaround available / unsupported) with workaround descriptions on hover. Appears after Step 1 (Discover).
- **Migration Timeline Gantt** - Horizontal bar chart showing the 4 migration phases with start day, duration, total effort, strategy, and risk level. Appears after Step 4 (Blueprint).
- **Cost Estimation** - Side-by-side stacked bar chart comparing source engine monthly cost vs Lakebase DBU pricing. Includes per-region rates, formula tooltips on hover, reference instance details, pricing source links, and a disclaimer directing customers to their Databricks account team for precise estimates. Appears after Step 4 (Blueprint).

---

## Project Structure (V2.2 - Modular Mixin Architecture)

```
lakebase-ops-platform/
├── pyproject.toml                       # Python project config (uv/pip, ruff, pytest)
├── uv.lock                              # Locked dependency versions
├── main.py                              # Full 5-phase simulation orchestrator
├── deploy_and_test.py                   # Real deployment + test suite
├── test_assessment.py                   # Assessment pipeline unit tests
├── .env.example                         # Environment variable template
├── README.md                            # This file
├── PRD_V2_ARCHITECTURE.md              # V2 architecture reference
├── ENHANCED_PROMPT.md                   # Original PRD (historical reference)
|
├── app/                                 # Databricks App (FastAPI + React)
│   ├── app.yaml                         # Databricks Apps deployment config
│   ├── backend/
│   │   ├── main.py                      # FastAPI entry point (SPA + API)
│   │   ├── routers/
│   │   │   ├── assessment.py            # Migration assessment + enrichment endpoints
│   │   │   ├── health.py, agents.py, metrics.py, ...
│   │   └── services/
│   │       ├── sql_service.py           # Databricks SQL Statement API
│   │       └── lakebase_service.py      # Direct Lakebase psycopg connection
│   └── frontend/                        # React + MUI + Vite + Recharts
│       └── src/
│           ├── pages/
│           │   ├── Dashboard.tsx         # KPI overview + assessment summary + Gantt + cost
│           │   ├── Assessment.tsx        # 4-step wizard + enrichment widgets
│           │   ├── Agents.tsx, Performance.tsx, Indexes.tsx, ...
│           │   └── NotFound.tsx
│           ├── components/
│           │   ├── GanttChart.tsx        # Migration timeline Gantt (recharts BarChart)
│           │   ├── ExtensionMatrix.tsx   # Extension compatibility matrix table
│           │   ├── CostEstimate.tsx      # Cost comparison with formulas + disclaimer
│           │   ├── MetricsChart.tsx      # Time-series area chart
│           │   ├── DataTable.tsx         # Generic data table
│           │   ├── KPICard.tsx, Sidebar.tsx, ErrorBoundary.tsx, ...
│           │   └── AnimatedLayout.tsx
│           └── hooks/
│               └── useApiData.ts        # Polling data fetcher with retry
|
├── sql/
│   ├── queries.py                       # 21 named SQL constants (PG17)
│   └── assessment_queries.py            # Assessment discovery + profiling SQL
|
├── agents/
│   ├── provisioning/                    # 21 tools across 7 mixins
│   │   ├── assessment.py                # AssessmentMixin: 7 engine mocks + live discover
│   │   ├── project.py, branching.py, migration.py, cicd.py, governance.py
│   ├── performance/                     # 14 tools across 4 mixins
│   └── health/                          # 16 tools across 5 mixins
|
├── config/
│   ├── settings.py                      # All configs (env-var driven)
│   ├── migration_profiles.py            # Assessment dataclasses + SourceEngine enum (8 engines)
│   └── pricing.py                       # Per-engine, per-region pricing registry with formulas
|
├── utils/
│   ├── readiness_scorer.py              # 6-dimension readiness scoring + extension workarounds
│   ├── blueprint_generator.py           # Engine-aware 4-phase migration blueprint
│   ├── lakebase_client.py               # OAuth-aware PostgreSQL client
│   ├── delta_writer.py                  # Unity Catalog Delta writer
│   └── alerting.py                      # Multi-channel alert manager
|
├── jobs/
│   ├── databricks_job_definitions.py    # 7 Databricks Job specs
│   └── *_notebook.py                    # Individual job notebooks
|
├── dashboards/
│   └── lakebase_ops_dashboard.sql       # 8 AI/BI dashboard query sets
|
└── github_actions/
    ├── create_branch_on_pr.yml          # Auto-create branch on PR open
    └── delete_branch_on_pr_close.yml    # Auto-delete + replay migrations
```

---

## Alert Thresholds (FR-04)

| Metric | Warning | Critical | Auto-SOP |
|--------|---------|----------|----------|
| Cache hit ratio | < 99% | < 95% | Recommend CU increase |
| Connection util | > 70% | > 85% | Auto-terminate idle > 30min |
| Dead tuple ratio | > 10% | > 25% | Schedule VACUUM ANALYZE |
| Lock wait time | > 30s | > 120s | Log lock chain |
| Deadlocks/hour | > 2 | > 5 | Capture blocking queries |
| Slow query | > 5s | > 30s | Log EXPLAIN plan |
| TXID age | > 500M | > 1B | Emergency VACUUM FREEZE |
| Replication lag | > 10s | > 60s | Investigate network |

---

## Success Metrics

| Metric | Before | V1 Target |
|--------|--------|-----------|
| DBA toil hours/week | 20+ | < 5 |
| MTTD | 30+ min | < 5 min |
| MTTR | 4+ hours | < 30 min |
| Auto-remediation | 0% | 50% |
| pg_stat Delta retention | 0 days | 90 days |
| Orphaned branches | Unknown | 0 |

---

## PG17 Features Leveraged

| Feature | Available Since | Usage |
|---------|----------------|-------|
| Persistent cumulative statistics | PG15 | Stats survive scale-to-zero; Delta used for 90-day trending |
| `pg_stat_checkpointer` | PG17 | Dedicated checkpoint stats (replaces bgwriter columns) |
| Extended `pg_stat_statements` | PG17 | WAL + JIT columns for full query profiling |
| `pg_stat_io` | PG16 | I/O stats by backend type (hit ratio, read/write times) |
| `pg_stat_wal` | PG14 | WAL generation stats (bytes, buffers full, write time) |
| `pg_stat_statements_info` | PG14 | Deallocation count and stats reset tracking |

---

## Scheduled Jobs (Databricks Jobs)

All 7 jobs replace pg_cron (unavailable in Lakebase) and can be triggered on-demand from the monitoring app's **Operations** page. Job IDs are workspace-specific - configure via the `LAKEBASE_JOB_IDS` environment variable after deploying jobs.

| Job | Agent | Tool(s) | Schedule | Timeout |
|-----|-------|---------|----------|---------|
| Metric Collector | Performance + Health | `persist_pg_stat_statements` + `monitor_system_health` | Every 5 min | 5 min |
| Index Analyzer | Performance | `run_full_index_analysis` | Hourly | 10 min |
| Vacuum Scheduler | Performance | `identify_tables_needing_vacuum` + `schedule_vacuum_analyze` | Daily 2 AM UTC | 60 min |
| Sync Validator | Health | `run_full_sync_validation` | Every 15 min | 5 min |
| Branch Manager | Provisioning | `enforce_ttl_policies` + `reset_branch_from_parent` | Every 6 hours | 10 min |
| Cold Data Archiver | Health | `identify_cold_data` + `archive_cold_data_to_delta` | Weekly Sun 3 AM UTC | 120 min |
| Cost Tracker | Health | `track_cost_attribution` | Daily 6 AM UTC | 10 min |

### Job API Endpoints (App Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jobs/list` | List all 7 jobs with current status |
| `POST` | `/api/jobs/sync` | Trigger all 7 jobs simultaneously |
| `GET` | `/api/jobs/sync/status?run_ids=...` | Poll run status (comma-separated run IDs) |

### Assessment API Endpoints (App Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/assessment/discover` | Run discovery on source DB (schema, extensions, edge cases) |
| `POST` | `/api/assessment/profile/{profile_id}` | Profile workload (QPS, TPS, connections) |
| `POST` | `/api/assessment/readiness/{profile_id}` | Score readiness across 6 dimensions |
| `POST` | `/api/assessment/blueprint/{profile_id}` | Generate 4-phase migration blueprint |
| `GET` | `/api/assessment/extension-matrix/{profile_id}` | Extension compatibility matrix |
| `GET` | `/api/assessment/timeline/{profile_id}` | Migration timeline phases for Gantt chart |
| `GET` | `/api/assessment/cost-estimate/{profile_id}` | Region-aware cost comparison (source vs Lakebase) |
| `GET` | `/api/assessment/regions/{engine}` | Available regions for a source engine |
| `GET` | `/api/assessment/history` | List all past assessment profiles |

---

## Pricing Configuration (`config/pricing.py`)

Cost estimates use a **static pricing registry** - rates are sourced from official cloud provider pricing pages and stored in `config/pricing.py`. This approach was chosen over live API integration for reliability and auditability.

**Key properties:**
- `PRICING_VERSION` - date-stamped version (e.g., `"2026-03"`) for tracking when rates were last verified
- `PRICING_DISCLAIMER` - displayed on all cost widgets directing customers to their Databricks account team
- Per-engine, per-region rates for compute ($/hr), storage ($/GB/mo), and I/O ($/million requests)
- Lakebase rates in DBU/hr and DSU/GB/mo per region
- Human-readable formula strings exposed as hover tooltips in the UI
- Source URLs linking to official pricing pages for each engine

**Supported regions:**

| Cloud | Regions |
|-------|---------|
| AWS | us-east-1, us-west-2, eu-west-1 |
| GCP | us-central1, us-east1, europe-west1 |
| Azure | eastus, westus2, westeurope |

Each engine maps to its cloud provider, and the region selector in the Assessment UI dynamically updates based on the selected engine. A `default` fallback rate is provided for engines when a specific region is not listed.

**Updating prices:** Edit `config/pricing.py`, update the `last_verified` date for each engine, and bump `PRICING_VERSION`. No code changes needed elsewhere.

---

## Key Design Decisions

1. **Databricks Jobs replace pg_cron** - All scheduling via native workspace integration
2. **Delta Lake enables long-term analysis** - pg_stat_statements persisted for 90-day trending and cross-branch comparison (stats are persistent in PG15+ but Delta adds historical depth)
3. **Native PG catalogs over information_schema** - `pg_class`/`pg_attribute` for faster, richer schema introspection
4. **Real index detection via pg_catalog** - `pg_index` self-join for duplicates, `pg_constraint` for missing FK indexes
5. **Centralized SQL in `sql/queries.py`** - 21 named constants as single source of truth, auditable without touching agent logic
6. **Mixin-based modular agents** - Each agent composed of focused mixins (5-7 per agent) for maintainability
7. **OAuth token management is transparent** - Auto-refresh at 50 min (before 1h expiry)
8. **Mock mode enables local development** - All external calls wrapped in mock-capable clients
9. **Event-driven agent coordination** - Provisioning -> Performance -> Health via EventType subscriptions
10. **Risk-stratified remediation** - Low-risk auto-executes, medium/high requires approval
11. **Static pricing registry over live APIs** - Rates sourced from official pricing pages, stored in `config/pricing.py` with version tracking and disclaimers. Avoids runtime API dependencies and rate-limit issues while remaining auditable and easy to update.
12. **Engine-specific mock discovery** - Each of the 8 source engines has a dedicated mock method producing realistic extension/feature profiles, edge cases, and workload characteristics unique to that platform
13. **Region-aware cost estimation** - Pricing varies by cloud region; the UI dynamically adjusts available regions based on the selected source engine's cloud provider

---

## Development

### Running Tests

```bash
# Backend unit tests
uv run pytest

# Frontend tests
cd app/frontend
bun run test
```

### Linting

```bash
# Python (ruff)
uv run ruff check .
uv run ruff format --check .

# TypeScript (via Vite build)
cd app/frontend
bun run build
```

### Frontend Development

```bash
cd app/frontend
bun install
bun run dev          # Vite dev server with HMR
```

### Adding a New Source Engine

1. Add the engine value to `SourceEngine` enum in `config/migration_profiles.py`
2. Add a `_mock_discover_<engine>()` method in `agents/provisioning/assessment.py`
3. Update `utils/blueprint_generator.py` - add entries to `_ENGINE_LABELS`, `_AUTH_MIGRATION_NOTES`, `_POOLING_NOTES`, `_DECOMMISSION_STEPS`, `_NETWORK_PREREQS`
4. Add any engine-specific extension workarounds to `utils/readiness_scorer.py`
5. Add pricing data to `config/pricing.py` under `SOURCE_ENGINES` and update `ENGINE_CLOUD_MAP`
6. Update the `ENGINE_LABELS` map in `app/frontend/src/pages/Assessment.tsx`

### Updating Pricing Data

1. Edit `config/pricing.py` - update rates under `SOURCE_ENGINES` and/or `LAKEBASE_PRICING`
2. Update `last_verified` date for each modified engine
3. Bump `PRICING_VERSION` to the current month
4. No backend or frontend code changes needed - the UI reads everything from the registry

---

## Changelog

### v2.2 (2026-03-11)

- Added Amazon DynamoDB as source engine (7 -> 8 total) - first NoSQL cross-engine migration path
- Introduced `ENGINE_KIND` discriminator to route assessment logic for PostgreSQL (`pg`) vs NoSQL (`nosql`) engines
- Added `_mock_discover_dynamodb()` and `_mock_workload_dynamodb()` with GSI/LSI, billing mode, Streams, TTL, PITR simulation
- Added DynamoDB-specific readiness scoring: feature compatibility, single-table design penalty, Streams/TTL/DAX/Global Tables dimensions
- Added DynamoDB cross-engine blueprint phases: relational modeling, S3 export, ETL, application rewrite (SDK to SQL)
- Added DynamoDB on-demand pricing (WRU/RRU) to `config/pricing.py`
- Extension matrix endpoint now returns feature compatibility matrix for NoSQL sources
- Frontend conditionally renders DynamoDB-specific discovery fields and feature matrix title
- Added 4 new DynamoDB test cases to `test_assessment.py`

### v2.1 (2026-03-11)

- Added AlloyDB PostgreSQL and Supabase PostgreSQL as source engines (5 -> 7 total)
- Added Extension Compatibility Matrix widget (appears after discovery step)
- Added Migration Timeline Gantt chart widget (appears after blueprint step)
- Added Cost Estimation widget with per-region pricing, formula tooltips, and disclaimer
- Introduced `config/pricing.py` static pricing registry with rates sourced from official cloud pricing pages
- Added dynamic region selector that updates based on selected source engine
- Added 5 new backend API endpoints: timeline, extension-matrix, cost-estimate, regions, history
- Updated README.md and PRD_V2_ARCHITECTURE.md to v2.1

### v2.0 (2026-02-21)

- Refactored 3 monolithic agents into mixin-based sub-packages (7 mixins for Provisioning, 4 for Performance, 5 for Health)
- Fixed pg_stat_statements scale-to-zero assumption (persistent since PG15)
- Added PG17 extended columns (WAL, JIT) to pg_stat_statements persistence
- Added pg_stat_io, pg_stat_wal, pg_stat_checkpointer, pg_stat_statements_info collection
- Replaced information_schema with native pg_catalog queries
- Implemented real duplicate index and missing FK index detection via pg_catalog
- Centralized all SQL into `sql/queries.py` (21 named constants)
- Added migration assessment pipeline (4-step wizard: discover, profile, readiness, blueprint)
- Added 5 source engines: Aurora, RDS, Cloud SQL, Azure, Self-Managed PostgreSQL

### v1.0 (2026-01-15)

- Initial release: 3 agents, 47 tools, 7 scheduled Databricks Jobs
- Full-stack monitoring app (FastAPI + React + MUI)
- 8 AI/BI dashboard query sets
- GitHub Actions CI/CD integration for branch lifecycle
