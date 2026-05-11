# Data Integration Analysis: lakebase-ops-platform

Generated: 2026-04-05

---

## 1. Delta/Lakehouse Table References

### 1.1 Operational Tables (Unity Catalog)

All operational data lands in `hls_amer_catalog.lakebase_ops.*`. Seven Delta tables are defined in `config/settings.py` via the `DELTA_TABLES` dictionary and created by `DeltaWriter.create_ops_catalog_and_schemas()`:

| Table (FQN) | Purpose | Partitioning | Key Properties |
|---|---|---|---|
| `hls_amer_catalog.lakebase_ops.pg_stat_history` | pg_stat_statements snapshots (FR-01) | `project_id, branch_id` | autoOptimize, autoCompact, 90-day log retention |
| `hls_amer_catalog.lakebase_ops.index_recommendations` | Index health recommendations (FR-02) | None | Status workflow: pending_review -> approved -> executed/rejected |
| `hls_amer_catalog.lakebase_ops.vacuum_history` | VACUUM/ANALYZE operation log (FR-03) | None | Tracks before/after dead tuples, duration |
| `hls_amer_catalog.lakebase_ops.lakebase_metrics` | Health KPIs (FR-04) | `project_id, metric_name` | 8+ metric types per snapshot |
| `hls_amer_catalog.lakebase_ops.sync_validation_history` | OLTP-to-OLAP sync checks (FR-05) | None | Row count drift, freshness lag, checksum match |
| `hls_amer_catalog.lakebase_ops.branch_lifecycle` | Branch create/delete/protect events (FR-06) | None | TTL tracking, actor attribution |
| `hls_amer_catalog.lakebase_ops.data_archival_history` | Cold data archival records (FR-07) | None | Rows archived, bytes reclaimed |

### 1.2 Archive Tables

Cold data archives land in `hls_amer_catalog.lakebase_archive.*`. Created dynamically per source table:

- `hls_amer_catalog.lakebase_archive.{table}_cold` -- e.g., `orders_cold`, `events_cold`

### 1.3 Sync Target Tables (OLAP mirrors)

Referenced in sync validation pairs (`agents/health/sync.py`, `main.py`):

- `ops_catalog.lakebase_ops.orders_delta`
- `ops_catalog.lakebase_ops.events_delta`

These are the Delta Lake mirrors of Lakebase (PostgreSQL) source tables.

### 1.4 System Tables Referenced

- `system.billing.usage` -- Cost attribution (UC-11), queried in `dashboards/lakebase_ops_dashboard.sql` with filter `billing_origin_product = 'DATABASE'`
- `system.access.audit` -- Referenced in governance integration for lineage tracking

### 1.5 Catalog/Schema Constants

| Constant | Value | Defined In |
|---|---|---|
| `OPS_CATALOG` | `hls_amer_catalog` | `config/settings.py` |
| `OPS_SCHEMA` | `lakebase_ops` | `config/settings.py` |
| `ARCHIVE_SCHEMA` | `lakebase_archive` | `config/settings.py` |
| `DEFAULT_CATALOG` | `hls_amer_catalog` | `config/settings.py` |

Note: The code originally intended `ops_catalog` as the catalog name but switched to `hls_amer_catalog` because `ops_catalog` requires managed storage credentials. The variable `OPS_CATALOG` is set to `hls_amer_catalog` with a comment explaining this.

---

## 2. Unity Catalog Usage and Permissions Model

### 2.1 Catalog Structure

```
hls_amer_catalog (OPS_CATALOG)
  |-- lakebase_ops (OPS_SCHEMA)        -- 7 operational Delta tables
  |-- lakebase_archive (ARCHIVE_SCHEMA) -- cold data archive tables
```

### 2.2 Naming Alignment

The `GovernanceMixin.setup_unity_catalog_integration()` maps Lakebase project names (hyphenated, RFC 1123) to UC names (underscored):

- Lakebase: `supply-chain-prod` -> UC: `supply_chain_prod`
- Separator mapping: hyphens (Lakebase) <-> underscores (Unity Catalog)

### 2.3 Row-Level Security

`GovernanceMixin.configure_rls()` creates per-tenant schemas and RLS policies in PostgreSQL:

```sql
CREATE SCHEMA IF NOT EXISTS {tenant};
ALTER TABLE {tenant}.orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY {tenant}_isolation ON {tenant}.orders
  USING (tenant_id = current_setting('app.tenant_id'));
```

### 2.4 Permissions and Access Patterns

- **Delta writes**: Service principal (SP) with client ID `9a911650-ffcf-43e3-8ad4-7f75b8c457db` authenticates via Databricks SDK auto-auth
- **SQL execution**: Statement Execution API on warehouse `8e4258d7fe74671b` ("Serverless Demo")
- **Lakebase access**: OAuth token generated via three fallback methods in `lakebase_service.py`:
  1. Explicit `LAKEBASE_OAUTH_TOKEN` env var
  2. `generate-db-credential` API (`POST /api/2.0/lakebase/credentials/generate-db-credential`)
  3. SP's own OAuth token extraction from SDK client

### 2.5 Lineage Tracking

Unity Catalog integration (`governance.py`) enables:
- `lineage_tracking: True`
- Audit via `system.access.audit`

---

## 3. Spark Job Configurations and Cluster Policies

### 3.1 Job Definitions

Seven scheduled Databricks Jobs are defined in `jobs/databricks_job_definitions.py`. Each job runs a notebook task.

| Job | Schedule (Quartz) | Timeout | Notebook |
|---|---|---|---|
| Metric Collector | `0 */5 * * * ?` (every 5 min) | 300s | `metric_collector_notebook.py` |
| Index Analyzer | `0 0 * * * ?` (hourly) | 600s | `index_analyzer_notebook.py` |
| Vacuum Scheduler | `0 0 2 * * ?` (daily 2 AM) | 3600s | `vacuum_scheduler_notebook.py` |
| Sync Validator | `0 */15 * * * ?` (every 15 min) | 300s | `sync_validator_notebook.py` |
| Branch Manager | `0 0 */6 * * ?` (every 6 hours) | 600s (2 dependent tasks) | `branch_manager_notebook.py` |
| Cold Archiver | `0 0 3 ? * SUN` (weekly Sun 3 AM) | 7200s | `cold_archiver_notebook.py` |
| Cost Tracker | `0 0 6 * * ?` (daily 6 AM) | 600s | `cost_tracker_notebook.py` |

### 3.2 Cluster Configuration

Job definitions specify a cluster but `create_all_jobs.py` strips `job_cluster_key` and `job_clusters` to use **serverless compute** instead:

```python
# Original definition:
"new_cluster": {
    "spark_version": "15.4.x-scala2.12",
    "num_workers": 0,
    "node_type_id": "i3.xlarge",
    "runtime_engine": "SERVERLESS",
}
# Actual deployment: serverless (cluster keys removed)
```

All jobs are single-node (`num_workers: 0`), `max_concurrent_runs: 1`.

### 3.3 Asset Bundle Configuration

`generate_databricks_yml()` produces a `databricks.yml` for DABs deployment with three targets:

| Target | Workspace |
|---|---|
| `dev` (default) | `https://fe-vm-hls-amer.cloud.databricks.com` |
| `staging` | `https://fe-vm-hls-amer.cloud.databricks.com` |
| `prod` | `https://fe-vm-hls-amer.cloud.databricks.com` |

All three targets currently point to the same workspace.

### 3.4 Job Tags

All jobs tagged with `team: lakebase-ops` plus a component-specific tag (e.g., `component: metric-collector`).

---

## 4. External API Integrations

### 4.1 Databricks REST APIs

| API | Endpoint | Used By | Purpose |
|---|---|---|---|
| Statement Execution | `POST /api/2.0/sql/statements` | `DeltaWriter._sql_execute()`, `sql_service.py` | Execute SQL on serverless warehouse |
| Statement Poll | `GET /api/2.0/sql/statements/{id}` | `DeltaWriter._sql_execute_and_wait()` | Poll async SQL completion |
| Lakebase Branches | `GET/POST/DELETE /api/2.0/postgres/projects/{id}/branches` | `LakebaseClient.api_*` methods | Branch CRUD |
| Lakebase Credentials | `POST /api/2.0/postgres/credentials/generate` | `LakebaseClient.api_generate_db_credential()` | OAuth DB credential |
| Lakebase DB Credential | `POST /api/2.0/lakebase/credentials/generate-db-credential` | `lakebase_service._get_db_credential()` | Provisioned Lakebase auth |
| Databricks CLI Auth | `databricks auth token --profile DEFAULT` | `LakebaseClient._get_databricks_token()`, `DeltaWriter._get_token()` | Token retrieval |
| Jobs API | SDK `client.jobs.get()`, `client.jobs.run_now()`, `client.jobs.get_run()` | `app/backend/routers/jobs.py` | Trigger/poll jobs |
| Databricks CLI | `databricks jobs create` | `jobs/create_all_jobs.py` | Job deployment |

### 4.2 Databricks SDK Usage

The `databricks-sdk` (>= 0.81.0) is used in two modes:

1. **Core agents (LakebaseClient)**: `WorkspaceClient().postgres.*` methods for Lakebase project/branch management and `generate_database_credential()` for OAuth tokens
2. **App backend (sql_service.py)**: `WorkspaceClient().statement_execution.execute_statement()` for Delta table queries

### 4.3 PostgreSQL (psycopg) Connections

Direct PG connections to Lakebase via `psycopg` (v3):

- **Connection params**: host from endpoint, port 5432, dbname `databricks_postgres`, user `databricks`, sslmode `require`
- **Statement timeout**: 300,000ms (5 min) for agents, 30,000ms (30s) for app live stats
- **Token refresh**: OAuth tokens cached for 50 min of 60 min TTL

### 4.4 Alerting Integrations

| Channel | Integration | Config |
|---|---|---|
| Slack | Webhook POST with Block Kit formatting | `webhook_url` in channel config |
| PagerDuty | Incident creation | `routing_key` in channel config |
| Email | Digest notifications | Not fully implemented |
| DBSQL Alerts | SQL Alerts API definitions | 6 alert queries defined in `alerting.py` |

### 4.5 GitHub Actions

Two workflow files in `github_actions/`:
- `create_branch_on_pr.yml` -- On PR open: creates ephemeral Lakebase branch, applies migrations, runs tests, posts schema diff as PR comment
- `delete_branch_on_pr_close.yml` -- On PR close: deletes ephemeral branch

Secrets required: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`
Variables required: `LAKEBASE_PROJECT`

---

## 5. Data Lineage: Ingestion to Serving

### 5.1 Data Flow Overview

```
[Lakebase PostgreSQL]                [Databricks Delta Lake]              [Serving Layer]
(OLTP - Source of Truth)             (OLAP - Analytics Store)             (API + Dashboard)
                                                                          
pg_stat_statements -------> pg_stat_history ----+
pg_stat_user_tables ----->                      |
pg_stat_user_indexes --->  index_recommendations |
pg_stat_activity -------->                       +---> FastAPI Backend ---> React Frontend
pg_stat_database -------->  lakebase_metrics     |       /api/metrics/*       (6 pages)
pg_stat_io, pg_stat_wal ->                       |       /api/performance/*
pg_locks -------------->                         |       /api/indexes/*
                                                 |       /api/operations/*
                            vacuum_history ------+
                            sync_validation -----+
                            branch_lifecycle ----+
                            data_archival -------+
                                                 |
[Lakebase tables]                                |
  orders, events, users --> orders_delta ---------+---> DBSQL Dashboard
                            events_delta                 (lakebase_ops_dashboard.sql)
                                                 
[Cold Data Path]                                  
  orders (old rows) -----> lakebase_archive.orders_cold
  events (old rows) -----> lakebase_archive.events_cold
                            |
                            v
                        Unified views (vw_{table}_unified)
                        
[Cost Data]
  system.billing.usage ---> Cost attribution dashboard query
  
[Audit Data]
  system.access.audit ----> Lineage tracking (UC integration)
```

### 5.2 Ingestion Paths

**Path A: PG Stat Metrics -> Delta (Batch, every 5 min)**
1. Agent queries PostgreSQL system catalogs (`pg_stat_statements`, `pg_stat_database`, etc.)
2. Results structured as Python dicts
3. `DeltaWriter.write_metrics()` writes to Delta via SQL INSERT (Statement Execution API) or PySpark
4. Batched in groups of 100 records to avoid statement size limits

**Path B: Sync Validation (Batch, every 15 min)**
1. `SyncMixin` queries Lakebase source table counts/timestamps
2. Compares with Delta target table counts (via SQL API)
3. Validation records written to `sync_validation_history`

**Path C: Cold Data Archival (Weekly)**
1. `ArchivalMixin.identify_cold_data()` scans `pg_stat_user_tables` for tables with >100K rows
2. `archive_cold_data_to_delta()` extracts rows older than 90 days
3. Writes to `hls_amer_catalog.lakebase_archive.{table}_cold`
4. Deletes from Lakebase source
5. Creates unified view (`vw_{table}_unified`)

**Path D: Real-time Stats (On-demand)**
1. `lakebase_service.get_realtime_stats()` opens direct psycopg connection
2. Queries `pg_stat_database`, `pg_stat_activity`, `pg_stat_wal`, `pg_stat_user_tables`
3. Returns JSON to `/api/lakebase/realtime` endpoint (no caching)

### 5.3 Serving Paths

**FastAPI Backend** (`app/backend/`): 8 API routers query Delta tables via `sql_service.execute_query()`:
- `/api/metrics/overview` and `/api/metrics/trends` -- from `lakebase_metrics`
- `/api/performance/queries` and `/api/performance/regressions` -- from `pg_stat_history`
- `/api/indexes/recommendations` -- from `index_recommendations`
- `/api/operations/vacuum` -- from `vacuum_history`
- `/api/operations/sync` -- from `sync_validation_history`
- `/api/operations/branches` -- from `branch_lifecycle`
- `/api/operations/archival` -- from `data_archival_history`
- `/api/lakebase/realtime` -- direct PG connection (bypasses Delta)

**DBSQL Dashboard** (`dashboards/lakebase_ops_dashboard.sql`): 8 query sections for AI/BI Dashboard (Lakeview), covering all 7 Delta tables plus `system.billing.usage`.

---

## 6. Schema Definitions and Evolution Strategy

### 6.1 Delta Table Schemas

All table DDL is defined in `utils/delta_writer.py` within `create_ops_catalog_and_schemas()`. Schemas use STRING for IDs, DOUBLE for metrics, TIMESTAMP for times, BIGINT for counts, BOOLEAN for flags.

Key schema properties:
- `delta.autoOptimize.optimizeWrite = true` (on `pg_stat_history`)
- `delta.autoOptimize.autoCompact = true` (on `pg_stat_history`)
- `delta.logRetentionDuration = interval 90 days` (on `pg_stat_history`)

### 6.2 PostgreSQL Schema Introspection

Schema diff capability (`MigrationMixin.capture_schema_diff()`) uses native PG catalogs:
- `pg_catalog.pg_class` + `pg_catalog.pg_namespace` + `pg_catalog.pg_attribute` + `pg_catalog.pg_attrdef` for column definitions
- `pg_catalog.pg_index` for index definitions
- `pg_catalog.pg_constraint` for foreign key relationships

### 6.3 Schema Evolution Strategy

- **Delta tables**: Schema evolution is supported via `CREATE TABLE IF NOT EXISTS` with `USING DELTA`. New columns would require ALTER TABLE statements.
- **PostgreSQL migrations**: Enforced idempotency via `MigrationMixin._is_idempotent_ddl()` -- only allows DDL with `IF NOT EXISTS`, `IF EXISTS`, `OR REPLACE`, or `ADD COLUMN IF NOT EXISTS`. Rejects non-idempotent `CREATE`, `DROP TABLE`, `DROP INDEX`, `TRUNCATE` without safety clauses.
- **9-step migration testing**: Schema changes are tested on ephemeral Lakebase branches (4h TTL) before promotion. Workflow: create branch -> apply migrations -> schema diff -> integration tests -> code review -> replay on merge -> auto-delete branch.

---

## 7. DLT Pipeline Definitions

**No DLT (Delta Live Tables) pipelines are defined in this codebase.** Data movement is handled entirely by:

1. Databricks Jobs running notebook tasks (7 scheduled jobs)
2. Direct Python agent code writing to Delta via SQL Statement Execution API or PySpark
3. `DeltaWriter` class providing a unified write interface

The architecture uses a custom agent framework rather than DLT for data ingestion, likely because the primary data source is PostgreSQL system catalogs (not streaming/file sources that DLT typically handles).

---

## 8. Streaming vs. Batch Processing Patterns

### 8.1 Processing Pattern Summary

| Data Flow | Pattern | Frequency | Implementation |
|---|---|---|---|
| pg_stat_statements persistence | Batch (micro-batch) | Every 5 min | Databricks Job + Agent |
| Health metric collection | Batch (micro-batch) | Every 5 min | Databricks Job + Agent |
| Index analysis | Batch | Hourly | Databricks Job + Agent |
| VACUUM/ANALYZE scheduling | Batch | Daily 2 AM | Databricks Job + Agent |
| Sync validation | Batch | Every 15 min | Databricks Job + Agent |
| Branch lifecycle management | Batch | Every 6 hours | Databricks Job + Agent |
| Cold data archival | Batch | Weekly (Sun 3 AM) | Databricks Job + Agent |
| Cost tracking | Batch | Daily 6 AM | Databricks Job + Agent |
| Connection monitoring | Batch (high-frequency) | Every minute | Agent tool |
| Real-time PG stats | On-demand | Per API request | Direct psycopg connection |

### 8.2 Key Observation

**No streaming is used.** All data ingestion follows batch or micro-batch patterns. The closest to real-time is:

1. **Connection monitoring** (every minute via agent tool) -- but this is still polling, not streaming
2. **Live Stats endpoint** (`/api/lakebase/realtime`) -- opens a fresh psycopg connection per request to Lakebase for instant PG stats. This is the only truly on-demand path and intentionally bypasses Delta.

The absence of streaming is a design choice: PostgreSQL system catalogs (`pg_stat_*`) are point-in-time snapshots, not change streams. The 5-minute micro-batch for metrics and 15-minute interval for sync validation provide sufficient temporal resolution for operational monitoring.

### 8.3 Write Modes

`DeltaWriter` supports three execution backends:
1. **Mock mode** (default) -- logs operations without executing
2. **SQL API mode** -- INSERT statements via Statement Execution API, batched 100 rows per INSERT
3. **PySpark mode** -- `DataFrame.write.mode("append").saveAsTable()` for Spark-native writes

All production writes use **append** mode. No overwrites or upserts are implemented.

---

## 9. Infrastructure Summary

| Component | Technology | Details |
|---|---|---|
| OLTP Database | Databricks Lakebase (PostgreSQL 17) | Project ID: `83eb266d-27f8-4467-a7df-2b048eff09d7`, autoscaling 8-16 CU |
| OLAP Store | Delta Lake on Unity Catalog | `hls_amer_catalog.lakebase_ops.*` (7 tables) |
| SQL Compute | Serverless SQL Warehouse | ID: `8e4258d7fe74671b` ("Serverless Demo") |
| Job Compute | Serverless (no classic clusters) | 7 scheduled jobs, all serverless |
| Web App | FastAPI + React (Databricks Apps) | URL: `https://lakebase-ops-app-1602460480284688.aws.databricksapps.com` |
| Auth | OAuth (SP + PAT fallback) | SP Client ID: `9a911650-ffcf-43e3-8ad4-7f75b8c457db` |
| Workspace | `fe-vm-hls-amer.cloud.databricks.com` | Single workspace for dev/staging/prod |
| Alerting | Slack + PagerDuty | Severity-based routing |
| CI/CD | GitHub Actions + Databricks CLI | Ephemeral branch per PR, auto-cleanup |

---

## 10. Key Files Reference

| File | Role |
|---|---|
| `config/settings.py` | All constants: catalog, schema, table names, job schedules, thresholds, Lakebase infra |
| `utils/lakebase_client.py` | PostgreSQL client with OAuth, mock mode, REST API methods |
| `utils/delta_writer.py` | Delta Lake writer with DDL definitions and 3 execution backends |
| `utils/alerting.py` | Multi-channel alert routing, DBSQL alert definitions |
| `sql/queries.py` | All PostgreSQL system catalog queries (single source of truth) |
| `framework/agent_framework.py` | Base agent, event system, orchestration |
| `agents/health/sync.py` | OLTP-to-OLAP sync validation logic |
| `agents/health/archival.py` | Cold data archival pipeline |
| `agents/provisioning/governance.py` | Unity Catalog integration, RLS setup |
| `agents/provisioning/migration.py` | Schema migration with idempotency enforcement |
| `jobs/databricks_job_definitions.py` | All 7 job definitions + Asset Bundle YAML generator |
| `dashboards/lakebase_ops_dashboard.sql` | 8 DBSQL dashboard queries |
| `app/backend/services/sql_service.py` | Delta query execution via SDK |
| `app/backend/services/lakebase_service.py` | Direct PG connection for real-time stats |
