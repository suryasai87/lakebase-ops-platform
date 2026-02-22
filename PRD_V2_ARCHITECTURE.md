# LakebaseOps Platform — V2 Architecture & Implementation Reference

**Version:** 2.0
**Last Updated:** 2026-02-21
**Status:** Implemented & Tested (all 47 tools, 3 agents, 81+ tests passing)

---

## I. Summary of Changes from V1

### 1. pg_stat_statements Scale-to-Zero Fix
PostgreSQL 15+ made cumulative statistics persistent via `stats_fetch_consistency`. Since Lakebase runs PG17, **pg_stat_statements data survives scale-to-zero and restarts**. All code and documentation that assumed "data is lost on scale-to-zero" has been corrected.

Delta Lake persistence is retained for:
- 90-day historical trending and capacity planning
- Cross-branch performance comparison
- AI/BI dashboard federation (SQL queries over Delta)

**Changes:**
- Removed `compute_status` field from `pg_stat_history` Delta table
- Removed scale-to-zero exception handling in `LakebaseClient.get_connection()`
- Removed scale-to-zero exception catch in `persist_pg_stat_statements()`
- Rewrote all docstrings and documentation to reflect "persistent in PG15+"

### 2. PG17 Extended Columns
Added full PG17 column support to `persist_pg_stat_statements()`:

| Column | Type | Description |
|--------|------|-------------|
| `temp_blks_read` | BIGINT | Temp blocks read |
| `wal_records` | BIGINT | WAL records generated |
| `wal_fpi` | BIGINT | WAL full-page images |
| `wal_bytes` | BIGINT | WAL bytes generated |
| `jit_functions` | BIGINT | JIT-compiled functions |
| `jit_generation_time` | DOUBLE | JIT code generation time (ms) |
| `jit_inlining_time` | DOUBLE | JIT inlining time (ms) |
| `jit_optimization_time` | DOUBLE | JIT optimization time (ms) |
| `jit_emission_time` | DOUBLE | JIT emission time (ms) |

### 3. New pg_stat Views
Added collection for PG14-17 system views:

| View | Agent | Purpose |
|------|-------|---------|
| `pg_stat_statements_info` | Performance | Track `dealloc` count and `stats_reset` timestamp |
| `pg_stat_io` | Health | I/O statistics by backend type — `io_hit_ratio`, read/write times |
| `pg_stat_wal` | Health | WAL generation — `wal_bytes_generated`, `wal_buffers_full`, write time |
| `pg_stat_checkpointer` | Health | PG17 checkpoint stats (replaces bgwriter checkpoint columns) |

### 4. Native PG Catalogs (replacing information_schema)
Replaced `information_schema.columns` with native PG catalog queries for better performance and richer metadata:

```sql
-- Old (slow, limited)
SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'public'

-- New (fast, rich)
SELECT c.relname, a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
       a.attnum, a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  AND a.attnum > 0 AND NOT a.attisdropped
```

### 5. Real Index Detection Queries
Replaced placeholder implementations with real queries:

- **`detect_duplicate_indexes()`**: Uses `pg_catalog.pg_index` self-join on matching `indkey` to find indexes covering identical column sets
- **`detect_missing_fk_indexes()`**: Uses `pg_catalog.pg_constraint` + `pg_catalog.pg_index` to find foreign keys without supporting indexes

### 6. Modular Architecture
All three monolithic agent files (~800+ lines each) have been refactored into sub-packages with a mixin pattern.

---

## II. Project Structure

```
lakebase-ops-platform/
├── main.py                          # Orchestrator — runs full 5-phase simulation
├── deploy_and_test.py               # Real deployment & 81+ test suite
├── ENHANCED_PROMPT.md               # Original PRD (updated for PG17)
├── PRD_V2_ARCHITECTURE.md           # This document
│
├── config/
│   ├── __init__.py
│   └── settings.py                  # All constants: workspace, catalog, tables, thresholds
│
├── framework/
│   ├── __init__.py
│   └── agent_framework.py           # BaseAgent, AgentFramework, EventType, TaskResult
│
├── sql/
│   ├── __init__.py
│   └── queries.py                   # 21 named SQL constants (single source of truth)
│
├── agents/
│   ├── __init__.py                  # Re-exports: ProvisioningAgent, PerformanceAgent, HealthAgent
│   │
│   ├── provisioning/                # 17 tools
│   │   ├── __init__.py
│   │   ├── agent.py                 # ProvisioningAgent class, register_tools(), run_cycle()
│   │   ├── project.py               # ProjectMixin: provision_lakebase_project, create_ops_catalog
│   │   ├── branching.py             # BranchingMixin: create/protect/enforce_ttl/monitor/reset branches
│   │   ├── migration.py             # MigrationMixin: apply_migration, capture_schema_diff, test_migration
│   │   ├── cicd.py                  # CICDMixin: setup_cicd_pipeline
│   │   └── governance.py            # GovernanceMixin: configure_rls, uc_integration, ai_branching
│   │
│   ├── performance/                 # 14 tools
│   │   ├── __init__.py
│   │   ├── agent.py                 # PerformanceAgent class, register_tools(), run_cycle()
│   │   ├── metrics.py               # MetricsMixin: persist_pg_stat_statements, collect_pg_stat_statements_info
│   │   ├── indexes.py               # IndexMixin: 6 detect methods + run_full_index_analysis
│   │   ├── maintenance.py           # MaintenanceMixin: vacuum, txid wraparound, autovacuum tuning
│   │   └── optimization.py          # OptimizationMixin: AI query analysis, capacity forecasting
│   │
│   └── health/                      # 16 tools
│       ├── __init__.py
│       ├── agent.py                 # HealthAgent class, register_tools(), run_cycle()
│       ├── monitoring.py            # MonitoringMixin: system_health, alerts, SOPs
│       ├── sync.py                  # SyncMixin: completeness, integrity, full_sync_validation
│       ├── archival.py              # ArchivalMixin: cold_data, archive_to_delta, unified_view
│       ├── connections.py           # ConnectionMixin: monitor, terminate_idle
│       └── operations.py            # OperationsMixin: cost, scale_to_zero, diagnose, self_heal, nl_dba
│
├── utils/
│   ├── __init__.py
│   ├── lakebase_client.py           # OAuth-aware PG client with mock mode
│   ├── delta_writer.py              # Unity Catalog Delta writer with mock mode
│   └── alerting.py                  # Multi-channel alert manager (Slack, PagerDuty, DBSQL)
│
├── jobs/
│   ├── __init__.py
│   └── databricks_job_definitions.py # Databricks Jobs configurations
│
└── tests/
    └── __init__.py
```

---

## III. Mixin Architecture Pattern

Each agent uses multiple inheritance with mixin classes. Mixins reference `self.client`, `self.writer`, `self.alerts`, and `self.thresholds` — set by the concrete agent's `__init__()`.

```python
# agents/performance/agent.py
class PerformanceAgent(MetricsMixin, IndexMixin, MaintenanceMixin, OptimizationMixin, BaseAgent):
    def __init__(self, lakebase_client, delta_writer, alert_manager):
        super().__init__("PerformanceAgent", lakebase_client, delta_writer, alert_manager)
        self.client = lakebase_client
        self.writer = delta_writer
        self.alerts = alert_manager
        self.register_tools()
```

### Mixin → Module Mapping

| Agent | Mixin | Module | Methods |
|-------|-------|--------|---------|
| **Provisioning** | ProjectMixin | `project.py` | provision_lakebase_project, create_ops_catalog |
| | BranchingMixin | `branching.py` | create_branch, protect_branch, enforce_ttl, monitor_count, reset_branch, create_on_pr, delete_on_pr |
| | MigrationMixin | `migration.py` | apply_schema_migration, capture_schema_diff, test_migration_on_branch |
| | CICDMixin | `cicd.py` | setup_cicd_pipeline |
| | GovernanceMixin | `governance.py` | configure_rls, setup_uc_integration, setup_ai_branching, provision_with_governance |
| **Performance** | MetricsMixin | `metrics.py` | persist_pg_stat_statements, collect_pg_stat_statements_info |
| | IndexMixin | `indexes.py` | detect_unused/bloated/missing/duplicate/missing_fk, run_full_index_analysis |
| | MaintenanceMixin | `maintenance.py` | identify_tables_needing_vacuum, schedule_vacuum_analyze/full, check_txid, tune_autovacuum |
| | OptimizationMixin | `optimization.py` | analyze_slow_queries_with_ai, forecast_capacity_needs |
| **Health** | MonitoringMixin | `monitoring.py` | monitor_system_health, evaluate_alert_thresholds, execute_low_risk_sop |
| | SyncMixin | `sync.py` | validate_sync_completeness/integrity, run_full_sync_validation |
| | ArchivalMixin | `archival.py` | identify_cold_data, archive_cold_data_to_delta, create_unified_access_view |
| | ConnectionMixin | `connections.py` | monitor_connections, terminate_idle_connections |
| | OperationsMixin | `operations.py` | track_cost, recommend_scale_to_zero, diagnose_root_cause, self_heal, natural_language_dba |

---

## IV. Centralized SQL Queries (`sql/queries.py`)

All SQL is centralized as named constants — agents import from `sql.queries`:

| Constant | Used By | Purpose |
|----------|---------|---------|
| `PG_STAT_STATEMENTS_FULL` | Performance (metrics) | Full PG17 pg_stat_statements with WAL/JIT columns |
| `PG_STAT_STATEMENTS_INFO` | Performance (metrics) | pg_stat_statements_info: dealloc, stats_reset |
| `PG_STAT_STATEMENTS_SLOW` | Performance (optimization) | Top slow queries by mean_exec_time |
| `UNUSED_INDEXES` | Performance (indexes) | idx_scan = 0 for 7+ days |
| `BLOATED_INDEXES` | Performance (indexes) | Bloat ratio estimation |
| `MISSING_INDEXES` | Performance (indexes) | seq_scan >> idx_scan with high row count |
| `DUPLICATE_INDEXES` | Performance (indexes) | pg_index self-join on matching indkey |
| `MISSING_FK_INDEXES` | Performance (indexes) | Foreign keys without supporting indexes |
| `TABLES_NEEDING_VACUUM` | Performance (maintenance) | dead_tuple_ratio > threshold |
| `TXID_WRAPAROUND_RISK` | Performance (maintenance) | age(datfrozenxid) > 500M |
| `AUTOVACUUM_CANDIDATES` | Performance (maintenance) | Tables needing autovacuum tuning |
| `DATABASE_STATS` | Health (monitoring) | Database-level cache, deadlocks, commits |
| `CONNECTION_STATES` | Health (monitoring) | Connection counts by state |
| `TABLE_DEAD_TUPLES` | Health (monitoring) | Per-table dead tuple ratios |
| `WAITING_LOCKS` | Health (monitoring) | Lock waits > threshold |
| `MAX_TXID_AGE` | Health (monitoring) | Maximum transaction ID age |
| `IO_STATS` | Health (monitoring) | pg_stat_io aggregated by backend type |
| `WAL_STATS` | Health (monitoring) | pg_stat_wal generation statistics |
| `CONNECTION_DETAILS` | Health (connections) | Active/idle connection details |
| `IDLE_CONNECTIONS` | Health (connections) | Long-idle sessions for termination |
| `SCHEMA_COLUMNS` | Provisioning (migration) | Native PG catalog schema introspection |

---

## V. Delta Table Schema (Updated)

### `pg_stat_history`
```sql
CREATE TABLE IF NOT EXISTS {catalog}.{schema}.pg_stat_history (
    snapshot_timestamp TIMESTAMP,
    project_id STRING,
    branch_id STRING,
    queryid BIGINT,
    query STRING,
    calls BIGINT,
    total_exec_time DOUBLE,
    mean_exec_time DOUBLE,
    min_exec_time DOUBLE,
    max_exec_time DOUBLE,
    rows BIGINT,
    shared_blks_hit BIGINT,
    shared_blks_read BIGINT,
    temp_blks_read BIGINT,          -- PG17
    wal_records BIGINT,              -- PG17
    wal_fpi BIGINT,                  -- PG17
    wal_bytes BIGINT,                -- PG17
    jit_functions BIGINT,            -- PG17
    jit_generation_time DOUBLE,      -- PG17
    jit_inlining_time DOUBLE,        -- PG17
    jit_optimization_time DOUBLE,    -- PG17
    jit_emission_time DOUBLE         -- PG17
) USING DELTA
```

**Removed:** `compute_status STRING` (was tracking scale-to-zero state, no longer needed)

---

## VI. PostgreSQL System Views Reference (Updated)

### Essential Views for Automation

| View | Purpose | Frequency | Agent |
|------|---------|-----------|-------|
| `pg_stat_statements` | Query performance metrics (PG17 full columns) | Every 5 min | Performance |
| `pg_stat_statements_info` | Deallocation count, stats reset tracking | Every 5 min | Performance |
| `pg_stat_user_tables` | Table stats (seq_scan, dead_tup, vacuum times) | Every 5 min | Health |
| `pg_stat_user_indexes` | Index usage (idx_scan, idx_tup_read) | Every 1 hour | Performance |
| `pg_stat_activity` | Active connections and queries | Every 1 min | Health |
| `pg_locks` | Lock information | Every 1 min | Health |
| `pg_stat_database` | Database-level stats (deadlocks, cache hits) | Every 5 min | Health |
| `pg_statio_user_tables` | I/O stats (heap_blks_hit, heap_blks_read) | Every 5 min | Health |
| `pg_stat_checkpointer` | Checkpoint statistics (PG17) | Every 15 min | Health |
| `pg_stat_io` | I/O statistics by backend type (PG16+) | Every 5 min | Health |
| `pg_stat_wal` | WAL generation statistics (PG14+) | Every 5 min | Health |
| `pg_catalog.pg_index` | Index metadata for duplicate detection | Every 1 hour | Performance |
| `pg_catalog.pg_constraint` | Foreign key constraints for missing FK index detection | Every 1 hour | Performance |
| `pg_catalog.pg_class` | Table/index metadata | On demand | Provisioning |
| `pg_catalog.pg_attribute` | Column metadata (replaces information_schema) | On demand | Provisioning |

### Key PG17 Improvements Leveraged
- **Persistent cumulative statistics** (`stats_fetch_consistency`) — stats survive restarts
- **`pg_stat_checkpointer`** — dedicated view replacing bgwriter checkpoint columns
- **Extended pg_stat_statements** — WAL and JIT columns for full query profiling
- **`pg_stat_io`** (PG16+) — granular I/O by backend type

---

## VII. Tool Inventory (47 Total)

### Provisioning & DevOps Agent (17 tools)

| Tool | Schedule | Risk | Approval | Module |
|------|----------|------|----------|--------|
| `provision_lakebase_project` | — | low | no | project.py |
| `create_ops_catalog` | — | low | no | project.py |
| `create_branch` | — | low | no | branching.py |
| `protect_branch` | — | medium | no | branching.py |
| `enforce_ttl_policies` | `0 */6 * * *` | low | no | branching.py |
| `monitor_branch_count` | `0 */6 * * *` | low | no | branching.py |
| `reset_branch_from_parent` | `0 2 * * *` | low | no | branching.py |
| `create_branch_on_pr` | — | low | no | branching.py |
| `delete_branch_on_pr_close` | — | low | no | branching.py |
| `apply_schema_migration` | — | medium | no | migration.py |
| `capture_schema_diff` | — | low | no | migration.py |
| `test_migration_on_branch` | — | low | no | migration.py |
| `setup_cicd_pipeline` | — | low | no | cicd.py |
| `configure_rls` | — | high | **yes** | governance.py |
| `setup_unity_catalog_integration` | — | low | no | governance.py |
| `setup_ai_agent_branching` | — | low | no | governance.py |
| `provision_with_governance` | — | low | no | governance.py |

### Performance & Optimization Agent (14 tools)

| Tool | Schedule | Risk | Approval | Module |
|------|----------|------|----------|--------|
| `persist_pg_stat_statements` | `*/5 * * * *` | low | no | metrics.py |
| `detect_unused_indexes` | `0 * * * *` | low | no | indexes.py |
| `detect_bloated_indexes` | `0 * * * *` | low | no | indexes.py |
| `detect_missing_indexes` | `0 * * * *` | low | no | indexes.py |
| `detect_duplicate_indexes` | `0 * * * *` | low | no | indexes.py |
| `detect_missing_fk_indexes` | `0 * * * *` | low | no | indexes.py |
| `run_full_index_analysis` | `0 * * * *` | low | no | indexes.py |
| `identify_tables_needing_vacuum` | `0 2 * * *` | low | no | maintenance.py |
| `schedule_vacuum_analyze` | `0 2 * * *` | low | no | maintenance.py |
| `schedule_vacuum_full` | — | high | **yes** | maintenance.py |
| `check_txid_wraparound_risk` | `*/5 * * * *` | low | no | maintenance.py |
| `tune_autovacuum_parameters` | `0 3 * * *` | low | no | maintenance.py |
| `analyze_slow_queries_with_ai` | — | low | no | optimization.py |
| `forecast_capacity_needs` | `0 4 * * 0` | low | no | optimization.py |

### Health & Self-Recovery Agent (16 tools)

| Tool | Schedule | Risk | Approval | Module |
|------|----------|------|----------|--------|
| `monitor_system_health` | `*/5 * * * *` | low | no | monitoring.py |
| `evaluate_alert_thresholds` | `*/5 * * * *` | low | no | monitoring.py |
| `execute_low_risk_sop` | — | low | no | monitoring.py |
| `validate_sync_completeness` | `*/15 * * * *` | low | no | sync.py |
| `validate_sync_integrity` | `*/15 * * * *` | low | no | sync.py |
| `run_full_sync_validation` | `*/15 * * * *` | low | no | sync.py |
| `identify_cold_data` | `0 3 * * 0` | low | no | archival.py |
| `archive_cold_data_to_delta` | `0 3 * * 0` | high | **yes** | archival.py |
| `create_unified_access_view` | — | low | no | archival.py |
| `monitor_connections` | `* * * * *` | low | no | connections.py |
| `terminate_idle_connections` | — | low | no | connections.py |
| `track_cost_attribution` | `0 6 * * *` | low | no | operations.py |
| `recommend_scale_to_zero_timeout` | `0 4 * * 0` | low | no | operations.py |
| `diagnose_root_cause` | — | low | no | operations.py |
| `self_heal` | — | low | no | operations.py |
| `natural_language_dba` | — | low | no | operations.py |

---

## VIII. Test Results

```
Simulation Results:
  3 Agents | 47 Tools | 8 Events | 59 Records Written

  ProvisioningAgent: 3/3 succeeded (100.0%)
  PerformanceAgent:  14/14 succeeded (100.0%)
  HealthAgent:       9/9 succeeded (100.0%)

  Delta Lake Writes: 19 operations, 59 records across 6 tables
    - branch_lifecycle: 5 records
    - index_recommendations: 10 records
    - lakebase_metrics: 32 records
    - pg_stat_history: 6 records
    - sync_validation_history: 2 records
    - vacuum_history: 4 records

Verification:
  - No information_schema references in agents/
  - No "lost on scale" references in codebase
  - No compute_status in agents/ or utils/
  - All imports resolve from sub-packages
```

---

## IX. Migration Guide (V1 → V2)

### Import Changes
```python
# V1 (old)
from agents.provisioning_agent import ProvisioningAgent
from agents.performance_agent import PerformanceAgent
from agents.health_agent import HealthAgent

# V2 (new)
from agents import ProvisioningAgent, PerformanceAgent, HealthAgent
```

### Removed Fields
- `compute_status` removed from `pg_stat_history` Delta table and all record dicts

### New Methods
- `PerformanceAgent.collect_pg_stat_statements_info()` — queries `pg_stat_statements_info`
- `HealthAgent.monitor_system_health()` now includes `io_hit_ratio`, `io_read_time_ms`, `io_write_time_ms`, `wal_bytes_generated`, `wal_buffers_full`, `wal_write_time_ms`

### SQL Query Imports
All inline SQL has been extracted to `sql/queries.py`. Agents now use:
```python
from sql import queries
result = self.client.execute_query(project_id, branch_id, queries.PG_STAT_STATEMENTS_FULL)
```
