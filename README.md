# LakebaseOps: Autonomous Lakebase Database Operations Platform

**Automated DBA Operations, Monitoring & OLTP-to-OLAP Lifecycle Management**

> A multi-agent system that automates critical DBA tasks for Databricks Lakebase (managed PostgreSQL), reducing DBA toil from 20+ hours/week to under 5 hours and MTTR from 4+ hours to under 30 minutes.

---

## Architecture

The platform consists of **3 collaborative AI agents** coordinated by an `AgentFramework`:

```
                    ┌─────────────────────┐
                    │   AgentFramework     │
                    │  (Coordinator)       │
                    └──────┬──────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     ┌────────┴───┐  ┌────┴─────┐  ┌───┴────────┐
     │Provisioning│  │Performance│  │   Health    │
     │   Agent    │  │  Agent   │  │   Agent     │
     │ (Day 0/1)  │  │ (Day 1+) │  │  (Day 2)   │
     └────────────┘  └──────────┘  └────────────┘
           │              │              │
           ▼              ▼              ▼
     ┌──────────────────────────────────────┐
     │  Lakebase (PostgreSQL)  │  Delta Lake │
     │  via psycopg3 + OAuth   │  via Spark  │
     └──────────────────────────────────────┘
```

### Agent 1: Provisioning & DevOps (14 tools)

Automates "Day 0" and "Day 1" — the 59 setup tasks from the Enterprise Lakebase Design Guide:

| Tool | Description | PRD Reference |
|------|-------------|---------------|
| `provision_lakebase_project` | Create project with full branch hierarchy | Tasks 1-15 |
| `create_ops_catalog` | Create Unity Catalog ops tables | Phase 1.1 |
| `create_branch` | Branch with naming conventions + TTL | Tasks 5-15 |
| `protect_branch` | Mark branch as protected | Tasks 16-17 |
| `enforce_ttl_policies` | Scan and delete expired branches | Task 18, FR-06 |
| `monitor_branch_count` | Alert on approaching 10-branch limit | Task 19, FR-06 |
| `reset_branch_from_parent` | Nightly staging reset | Task 40 |
| `apply_schema_migration` | Idempotent DDL migrations | Tasks 22-25 |
| `capture_schema_diff` | Schema diff between branches | FR-08 |
| `test_migration_on_branch` | Full 9-step migration testing | FR-08 |
| `setup_cicd_pipeline` | Generate GitHub Actions YAML | Tasks 26-32 |
| `configure_rls` | Row-level security setup | Tasks 33-36 |
| `setup_unity_catalog_integration` | UC governance alignment | Tasks 50-54 |
| `setup_ai_agent_branching` | AI agent branching config | Tasks 55-57 |

### Agent 2: Performance & Optimization (14 tools)

Addresses the core problem that **pg_cron is unavailable** and **pg_stat_statements is lost on scale-to-zero**:

| Tool | Description | PRD Reference |
|------|-------------|---------------|
| `persist_pg_stat_statements` | Capture to Delta every 5 min | FR-01 |
| `detect_unused_indexes` | idx_scan=0 for 7+ days | FR-02 |
| `detect_bloated_indexes` | Bloat ratio > 2.0x | FR-02 |
| `detect_missing_indexes` | seq_scan >> idx_scan | FR-02 |
| `detect_duplicate_indexes` | Overlapping column sets | FR-02 |
| `detect_missing_fk_indexes` | Unindexed foreign keys | FR-02 |
| `run_full_index_analysis` | Complete index health check | FR-02 |
| `identify_tables_needing_vacuum` | Dead tuple analysis | FR-03 |
| `schedule_vacuum_analyze` | VACUUM ANALYZE (replaces pg_cron) | FR-03 |
| `schedule_vacuum_full` | VACUUM FULL with lock awareness | FR-03 |
| `check_txid_wraparound_risk` | XID age monitoring | FR-03 |
| `tune_autovacuum_parameters` | Per-table threshold tuning | UC-09 |
| `analyze_slow_queries_with_ai` | LLM-powered query analysis | UC-12 |
| `forecast_capacity_needs` | ML-based capacity planning | UC-15 |

### Agent 3: Health & Self-Recovery (17 tools)

Continuous monitoring with **8 alerting thresholds** and **automated self-healing**:

| Tool | Description | PRD Reference |
|------|-------------|---------------|
| `monitor_system_health` | Collect all pg_stat metrics | FR-04 |
| `evaluate_alert_thresholds` | Check 8 metrics vs thresholds | FR-04 |
| `execute_low_risk_sop` | Auto-remediate safe issues | FR-04 |
| `validate_sync_completeness` | Row count + timestamp check | FR-05 |
| `validate_sync_integrity` | Checksum verification | FR-05 |
| `run_full_sync_validation` | Complete sync cycle | FR-05 |
| `identify_cold_data` | Find rows > 90 days old | FR-07 |
| `archive_cold_data_to_delta` | Full archival pipeline | FR-07 |
| `create_unified_access_view` | Hot+cold unified view | FR-07 |
| `monitor_connections` | Active/idle tracking | UC-10 |
| `terminate_idle_connections` | Kill idle > 30 min | UC-10 |
| `track_cost_attribution` | Billing analysis | UC-11 |
| `recommend_scale_to_zero_timeout` | Optimize idle timeout | UC-11 |
| `diagnose_root_cause` | Correlate metrics for RCA | UC-13 |
| `self_heal` | Execute approved auto-fix | UC-13 |
| `natural_language_dba` | "Why is my query slow?" | UC-14 |

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

## Project Structure

```
lakebase-ops-platform/
├── main.py                              # Full simulation orchestrator
├── ENHANCED_PROMPT.md                   # Complete agent prompt specification
├── requirements.txt                     # Dependencies
├── README.md                            # This file
├── framework/
│   └── agent_framework.py               # AgentFramework, BaseAgent, events
├── agents/
│   ├── provisioning_agent.py            # 14 tools, 59 setup tasks
│   ├── performance_agent.py             # 14 tools, FR-01/02/03
│   └── health_agent.py                  # 17 tools, FR-04/05/07
├── utils/
│   ├── lakebase_client.py               # OAuth-aware PostgreSQL client
│   ├── delta_writer.py                  # Delta Lake writer with schemas
│   └── alerting.py                      # Multi-channel alert manager
├── config/
│   └── settings.py                      # All configs, thresholds, TTL policies
├── jobs/
│   └── databricks_job_definitions.py    # 7 Databricks Job specs + Asset Bundle YAML
├── dashboards/
│   └── lakebase_ops_dashboard.sql       # 8 AI/BI dashboard query sets
├── github_actions/
│   ├── create_branch_on_pr.yml          # Auto-create branch on PR open
│   └── delete_branch_on_pr_close.yml    # Auto-delete + replay migrations
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
| pg_stat retention | 0 days | 90 days |
| Orphaned branches | Unknown | 0 |

---

## Key Design Decisions

1. **Databricks Jobs replace pg_cron** — All scheduling via native workspace integration
2. **Delta Lake persists volatile metrics** — pg_stat_statements survives scale-to-zero
3. **OAuth token management is transparent** — Auto-refresh at 50 min (before 1h expiry)
4. **Mock mode enables local development** — All external calls wrapped in mock-capable clients
5. **Event-driven agent coordination** — Provisioning → Performance → Health via EventType subscriptions
6. **Risk-stratified remediation** — Low-risk auto-executes, medium/high requires approval
7. **Idempotent DDL enforcement** — All migrations validated before execution
