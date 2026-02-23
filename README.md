# LakebaseOps: Autonomous Lakebase Database Operations Platform

**Automated DBA Operations, Monitoring & OLTP-to-OLAP Lifecycle Management**

> A multi-agent system that automates critical DBA tasks for Databricks Lakebase (managed PostgreSQL 17), reducing DBA toil from 20+ hours/week to under 5 hours and MTTR from 4+ hours to under 30 minutes.

---

## Architecture

The platform consists of **3 collaborative AI agents** (47 tools total) coordinated by an `AgentFramework`, with a modular mixin-based architecture:

```
                         ┌──────────────────────┐
                         │    AgentFramework     │
                         │     (Coordinator)     │
                         │  Event Bus + Scheduler│
                         └──────────┬───────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
    ┌──────────┴──────────┐  ┌─────┴──────────┐  ┌─────┴──────────┐
    │  Provisioning Agent │  │ Performance    │  │  Health Agent   │
    │     (17 tools)      │  │ Agent (14)     │  │    (16 tools)   │
    │     Day 0 / Day 1   │  │  Day 1+        │  │    Day 2        │
    ├─────────────────────┤  ├────────────────┤  ├────────────────┤
    │ ProjectMixin        │  │ MetricsMixin   │  │ MonitoringMixin│
    │ BranchingMixin      │  │ IndexMixin     │  │ SyncMixin      │
    │ MigrationMixin      │  │ MaintenanceMix │  │ ArchivalMixin  │
    │ CICDMixin           │  │ OptimizationMix│  │ ConnectionMixin│
    │ GovernanceMixin     │  │                │  │ OperationsMixin│
    └──────────┬──────────┘  └──────┬─────────┘  └──────┬─────────┘
               │                    │                    │
               ▼                    ▼                    ▼
    ┌──────────────────────────────────────────────────────────────┐
    │      sql/queries.py — 21 Named SQL Constants (PG17)         │
    ├──────────────────────────────────────────────────────────────┤
    │  Lakebase (PostgreSQL 17)      │    Delta Lake (Unity Catalog)│
    │  psycopg3 + OAuth auto-refresh │    Spark SQL via SDK         │
    └──────────────────────────────────────────────────────────────┘
```

### Agent 1: Provisioning & DevOps (17 tools)

Automates "Day 0" and "Day 1" — the 59 setup tasks from the Enterprise Lakebase Design Guide:

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

## Quick Start

```bash
# Run the full simulation (mock mode - no external dependencies)
cd lakebase-ops-platform
python main.py
```

Output demonstrates all 5 PRD phases:
1. **Foundation** — Ops catalog creation, metric collection, alerting
2. **Index & Vacuum** — Index analysis, vacuum scheduling, autovacuum tuning
3. **Sync & Branches** — OLTP-to-OLAP validation, branch lifecycle
4. **Cold Archival** — Data archival pipeline, unified access views
5. **AI Operations** — Query optimization, self-healing, NL DBA, capacity planning

---

## Project Structure (V2 — Modular Mixin Architecture)

```
lakebase-ops-platform/
├── main.py                              # Full 5-phase simulation orchestrator
├── deploy_and_test.py                   # Real deployment + 81+ test suite
├── ENHANCED_PROMPT.md                   # Agent prompt specification (PG17 updated)
├── PRD_V2_ARCHITECTURE.md              # V2 architecture & implementation reference
├── README.md                            # This file
│
├── sql/
│   ├── __init__.py
│   └── queries.py                       # 21 named SQL constants (single source of truth)
│
├── framework/
│   └── agent_framework.py               # AgentFramework, BaseAgent, events
│
├── agents/
│   ├── __init__.py                      # Re-exports: ProvisioningAgent, PerformanceAgent, HealthAgent
│   ├── provisioning/                    # 17 tools across 5 mixins
│   │   ├── agent.py                     # ProvisioningAgent class + register_tools + run_cycle
│   │   ├── project.py                   # ProjectMixin: provision, create_ops_catalog
│   │   ├── branching.py                 # BranchingMixin: 7 branch lifecycle tools
│   │   ├── migration.py                 # MigrationMixin: migration, schema diff, testing
│   │   ├── cicd.py                      # CICDMixin: GitHub Actions generation
│   │   └── governance.py                # GovernanceMixin: RLS, UC, AI branching
│   ├── performance/                     # 14 tools across 4 mixins
│   │   ├── agent.py                     # PerformanceAgent class
│   │   ├── metrics.py                   # MetricsMixin: pg_stat persistence (PG17)
│   │   ├── indexes.py                   # IndexMixin: 6 detection + full analysis
│   │   ├── maintenance.py               # MaintenanceMixin: vacuum, TXID, autovacuum
│   │   └── optimization.py              # OptimizationMixin: AI queries, forecasting
│   └── health/                          # 16 tools across 5 mixins
│       ├── agent.py                     # HealthAgent class
│       ├── monitoring.py                # MonitoringMixin: health + io + wal + alerts
│       ├── sync.py                      # SyncMixin: OLTP-to-OLAP validation
│       ├── archival.py                  # ArchivalMixin: cold data lifecycle
│       ├── connections.py               # ConnectionMixin: pool monitoring
│       └── operations.py                # OperationsMixin: cost, self-heal, NL DBA
│
├── utils/
│   ├── lakebase_client.py               # OAuth-aware PostgreSQL client + mock data
│   ├── delta_writer.py                  # Unity Catalog Delta writer with PG17 schema
│   └── alerting.py                      # Multi-channel alert manager (Slack, PagerDuty, DBSQL)
│
├── config/
│   └── settings.py                      # All configs, thresholds, TTL policies
│
├── jobs/
│   └── databricks_job_definitions.py    # 7 Databricks Job specs + Asset Bundle YAML
│
├── dashboards/
│   └── lakebase_ops_dashboard.sql       # 8 AI/BI dashboard query sets
│
├── github_actions/
│   ├── create_branch_on_pr.yml          # Auto-create branch on PR open
│   └── delete_branch_on_pr_close.yml    # Auto-delete + replay migrations
│
└── tests/
    └── (test files)
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

All 7 jobs replace pg_cron (unavailable in Lakebase) and can be triggered on-demand from the monitoring app's **Operations** page via the **"Sync Tables in Unity Catalog Schema Lakebase_Ops"** button.

| Job | Job ID | Agent | Tool(s) | Schedule | Timeout |
|-----|--------|-------|---------|----------|---------|
| Metric Collector | `205010800477517` | Performance + Health | `persist_pg_stat_statements` + `monitor_system_health` | Every 5 min | 5 min |
| Index Analyzer | `405039178411009` | Performance | `run_full_index_analysis` | Hourly | 10 min |
| Vacuum Scheduler | `594266613956568` | Performance | `identify_tables_needing_vacuum` + `schedule_vacuum_analyze` | Daily 2 AM UTC | 60 min |
| Sync Validator | `462158184008431` | Health | `run_full_sync_validation` | Every 15 min | 5 min |
| Branch Manager | `676577590162017` | Provisioning | `enforce_ttl_policies` + `reset_branch_from_parent` | Every 6 hours | 10 min |
| Cold Data Archiver | `120897564762964` | Health | `identify_cold_data` + `archive_cold_data_to_delta` | Weekly Sun 3 AM UTC | 120 min |
| Cost Tracker | `1114339309161416` | Health | `track_cost_attribution` | Daily 6 AM UTC | 10 min |

### Job API Endpoints (App Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jobs/list` | List all 7 jobs with current status |
| `POST` | `/api/jobs/sync` | Trigger all 7 jobs simultaneously |
| `GET` | `/api/jobs/sync/status?run_ids=...` | Poll run status (comma-separated run IDs) |

---

## Key Design Decisions

1. **Databricks Jobs replace pg_cron** — All scheduling via native workspace integration
2. **Delta Lake enables long-term analysis** — pg_stat_statements persisted for 90-day trending and cross-branch comparison (stats are persistent in PG15+ but Delta adds historical depth)
3. **Native PG catalogs over information_schema** — `pg_class`/`pg_attribute` for faster, richer schema introspection
4. **Real index detection via pg_catalog** — `pg_index` self-join for duplicates, `pg_constraint` for missing FK indexes
5. **Centralized SQL in `sql/queries.py`** — 21 named constants as single source of truth, auditable without touching agent logic
6. **Mixin-based modular agents** — Each agent composed of focused mixins (5-7 per agent) for maintainability
7. **OAuth token management is transparent** — Auto-refresh at 50 min (before 1h expiry)
8. **Mock mode enables local development** — All external calls wrapped in mock-capable clients
9. **Event-driven agent coordination** — Provisioning → Performance → Health via EventType subscriptions
10. **Risk-stratified remediation** — Low-risk auto-executes, medium/high requires approval
