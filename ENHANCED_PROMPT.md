# Enhanced Claude Code Prompt: Lakebase Automation Agent System

## Prompt Title: Build a Multi-Agent System for Autonomous Lakebase DBA Automation

---

## I. Role and Goal

You are an expert AI Architect specializing in designing and implementing autonomous multi-agent systems for modern cloud-native data platforms, specifically the Databricks Lakehouse and Lakebase transactional layer. Your goal is to design and write the complete, runnable Python code for a system that automates critical, repetitive, or complex tasks typically handled manually by Postgres Database Administrators (DBAs) for Lakebase environments.

The system must address the following core problems:
- **pg_cron is NOT available** in Lakebase — all scheduling must use Databricks Jobs
- **pg_stat_statements is persistent in PG15+** but Delta enables 90-day historical trending, cross-branch comparison, and AI/BI dashboards
- **No built-in CDC sync** — OLTP-to-OLAP validation must be implemented
- **DBAs spend 60%+ of time on routine tasks** — vacuum tuning, index management, performance triage, backup validation
- **Average MTTR is 4+ hours** for preventable database incidents with manual observation
- **Max 10 unarchived branches per project** — lifecycle automation is essential
- **OAuth tokens expire in 1 hour** — all connections require automatic refresh

---

## II. Architecture & Framework

* **Language/Framework:** Python 3.10+ with `dataclasses`, `enum`, `abc`, `asyncio`, and type hints
* **External Dependencies:** `databricks-sdk>=0.81.0`, `psycopg>=3.0`, `pyspark`
* **Mock Mode:** All external calls wrapped in mock-capable clients for local testing
* **System Components:** Three distinct, collaborative AI Agents with a shared coordination framework

### Data Architecture

All operational data persists in Unity Catalog under `ops_catalog.lakebase_ops`:

| Delta Table | Purpose | Write Frequency |
|---|---|---|
| `pg_stat_history` | Query performance metrics from pg_stat_statements | Every 5 min |
| `index_recommendations` | Index health analysis results | Every 1 hour |
| `vacuum_history` | VACUUM/ANALYZE operation logs | Daily |
| `lakebase_metrics` | Health metrics (connections, cache, locks, dead tuples) | Every 5 min |
| `sync_validation_history` | OLTP-to-OLAP sync freshness & completeness | Every 15 min |
| `branch_lifecycle` | Branch create/delete/protect events | On event |
| `data_archival_history` | Cold data archival operations | Weekly |

---

## III. Agent Definitions and Automation Targets

### Agent 1: Provisioning & DevOps Agent

**Core Mission:** Automate "Day 0" and "Day 1" tasks — database setup, branching, schema management, CI/CD integration, and governance. Democratize database creation for App Developers.

**Automation Targets from Lakebase Setup Guide (59 tasks):**

#### Project Setup & Architecture (4 tasks)
1. Define Lakebase project name using `domain-env` convention (e.g., `supply-chain-prod`)
2. Select branching pattern (Simple Dev/Prod, Multi-Environment Pipeline, Per-Developer, CI/CD Ephemeral, Multi-Tenant Project-Level, Multi-Tenant Schema-Level)
3. Decide project-level vs. schema-level isolation for multi-tenant scenarios
4. Plan full branch hierarchy before provisioning (production → staging → development → per-developer/CI)

#### Branch Creation & Configuration (11 tasks)
5. Create default production branch (always-on, protected, no TTL)
6. Create staging branch (protected, no TTL, regular reset from production)
7. Create development branch (child of staging, shared dev environment)
8. Create per-developer branches (`dev-firstname`, 7-day TTL)
9. Configure CI/CD ephemeral branches (`ci-pr-{number}`, 2-4 hour TTL)
10. Configure feature branches (`feat-short-desc`, 7-day TTL)
11. Configure hotfix branches (`hotfix-{ticket-id}`, 24-hour TTL)
12. Configure QA/release branches (`qa-release-{version}`, 14-day TTL)
13. Configure performance test branches (`perf-{test-name}`, 48-hour TTL)
14. Configure audit/point-in-time branches (`audit-{YYYY-MM-DD}`, 30-day TTL max)
15. Configure demo branches (`demo-{customer}`, 7-14 day TTL)

#### Branch Protection & Governance (6 tasks)
16. Mark production branch as protected (`is_protected: true`)
17. Mark staging branch as protected
18. Enforce TTL policies on ALL non-protected branches
19. Monitor branch count (max 10 unarchived per project)
20. Configure auto-archive for idle branches
21. Enforce Databricks OAuth identity (never password-based)

#### Schema Migration Workflow (4 tasks + 9-step workflow)
22. Integrate migration tool (Flyway, Liquibase, Prisma, or plain SQL)
23. Write ALL DDL as idempotent SQL (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
24. Never use non-idempotent DDL
25. Execute 9-step safe migration testing workflow:
    - Step 1: Developer writes migration files locally
    - Step 2: PR opened triggers CI/CD pipeline
    - Step 3: Pipeline creates Lakebase branch from staging (TTL: 4h)
    - Step 4: Migrations applied to branch
    - Step 5: Schema Diff captured
    - Step 6: Integration tests run against migrated branch
    - Step 7: Code review includes code + schema diff
    - Step 8: On PR merge, replay migrations on staging then production
    - Step 9: Branch auto-deletes after TTL

#### CI/CD Pipeline Integration (7 tasks)
26. Create GitHub Actions workflow for `pull_request: [opened, reopened]` to auto-create branches
27. Store `DATABRICKS_HOST` and `DATABRICKS_TOKEN` as GitHub secrets
28. Store `LAKEBASE_PROJECT` as GitHub Actions variable
29. Install Databricks CLI in CI runner
30. Apply migrations to ephemeral branch in CI
31. Run integration tests against ephemeral branch endpoint
32. Create GitHub Actions workflow for `pull_request: [closed]` to auto-delete branches

#### Row-Level Security (4 tasks)
33. Define PostgreSQL schemas per tenant
34. Implement RLS policies for data isolation
35. Configure Lakebase Data API for RLS enforcement
36. Configure Data API exposed schemas and CORS origins

#### Branch Operations via CLI/SDK (7 tasks)
37. `databricks postgres create-branch` with full spec JSON
38. `databricks postgres list-branches` for regular auditing
39. `databricks postgres get-branch` for state inspection
40. `databricks postgres reset-branch` for dev/staging sync
41. `databricks postgres update-branch` for protection changes
42. `databricks postgres delete-branch` for cleanup
43. Python SDK (`WorkspaceClient().postgres.*`) for programmatic automation

#### Unity Catalog Integration (5 tasks)
50. Align Lakebase project names with UC domain names (UC: `_`, Lakebase: `-`)
51. Map environments consistently across UC catalogs and Lakebase projects
52. Track data lineage from Lakebase OLTP to Delta Lake analytics
53. Audit operations via `system.access.audit`
54. Single CI/CD pipeline managing both Lakebase branches AND UC permissions

#### AI Agent Integration (3 tasks)
55. Add branching instructions to CLAUDE.md/AGENTS.md
56. Configure AI agents to create 1-hour TTL branches for schema testing
57. Enforce AI workflow: create → wait ACTIVE → apply → validate → review → auto-delete

#### PRD Functional Requirements (FR-06, FR-08)
- **FR-06:** Branch lifecycle automation (create on PR, delete on merge, TTL enforcement, branch count alerting)
- **FR-08:** Schema migration testing on branches (auto-create, apply, diff, test, post PR comment)

**Tool/Method Inventory:**

| Method | Description | Source |
|---|---|---|
| `provision_lakebase_project(name, config)` | Create new Lakebase project with full hierarchy | Setup Guide tasks 1-4 |
| `create_branch(parent, name, branch_type, ttl)` | Create any branch type with naming conventions | Setup Guide tasks 5-15 |
| `protect_branch(project, branch)` | Mark branch as protected | Setup Guide tasks 16-17 |
| `enforce_ttl_policies(project)` | Scan and delete branches exceeding TTL | Setup Guide task 18, PRD FR-06 |
| `monitor_branch_count(project, max_limit=10)` | Alert on branch count approaching limit | Setup Guide task 19, PRD FR-06 |
| `apply_schema_migration(branch, migration_files)` | Apply idempotent DDL migrations | Setup Guide tasks 22-25 |
| `capture_schema_diff(source_branch, target_branch)` | Generate schema diff between branches | PRD FR-08 |
| `post_schema_diff_to_pr(pr_number, diff_result)` | Post diff as GitHub PR comment | PRD FR-08 |
| `setup_cicd_pipeline(project, repo_config)` | Generate GitHub Actions YAML | Setup Guide tasks 26-32 |
| `configure_rls(project, tenants, policies)` | Setup row-level security | Setup Guide tasks 33-36 |
| `setup_unity_catalog_integration(project, catalog)` | Align Lakebase with UC governance | Setup Guide tasks 50-54 |
| `reset_branch_from_parent(project, branch)` | Sync branch from parent (nightly staging reset) | Setup Guide task 40 |
| `create_ops_catalog_and_schemas()` | Create ops_catalog.lakebase_ops in UC | PRD Phase 1.1 |
| `provision_with_governance(name, branching_pattern, tenants)` | Full project setup with all governance | Combined workflow |

---

### Agent 2: Performance & Optimization Agent

**Core Mission:** Address performance issues by proactively analyzing query patterns, indexing, and runtime configurations. Persist metrics to Delta for 90-day historical trending and cross-branch comparison.

**Automation Targets from PRD:**

#### FR-01: pg_stat_statements Persistence Engine
- Capture ALL columns from pg_stat_statements every 5 minutes
- Persist to `ops_catalog.lakebase_ops.pg_stat_history`
- Capture PG17 extended columns: temp_blks_read, wal_records, wal_fpi, wal_bytes, jit_functions, jit_generation_time, jit_inlining_time, jit_optimization_time, jit_emission_time
- Include metadata: project_id, branch_id, snapshot_timestamp
- Retain 90 days with automatic partition management
- Handle OAuth token refresh (1-hour expiry)

#### FR-02: Automated Index Health Manager
- **Unused indexes:** idx_scan = 0 for 7+ days (excluding PK/unique)
- **Bloated indexes:** bloat ratio > 2.0x
- **Missing indexes:** seq_scan >> idx_scan AND n_live_tup > 10,000
- **Duplicate/redundant indexes:** overlapping column sets
- **Missing foreign key indexes**
- Generate recommendations with confidence scores (high/medium/low) and estimated impact
- Store in `ops_catalog.lakebase_ops.index_recommendations`
- Manual approval workflow before DROP INDEX or REINDEX CONCURRENTLY

#### FR-03: VACUUM/ANALYZE Scheduler
- Identify tables: dead_tuple_ratio > 10% OR last_autovacuum > 24h
- Execute VACUUM ANALYZE during low-traffic windows
- VACUUM FULL for heavily bloated tables (dead_tuple_ratio > 30%) with locking awareness
- Log to `ops_catalog.lakebase_ops.vacuum_history`
- Alert when autovacuum is falling behind
- Monitor transaction ID wraparound: alert when age(datfrozenxid) > 500M

#### UC-09: Autovacuum Parameter Tuning
- Dynamically adjust per-table autovacuum thresholds based on table size and churn patterns

#### UC-12: AI-Powered Query Optimization (V2)
- Analyze slow queries from persisted pg_stat_statements
- Suggest rewrites and index strategies using Foundation Model API (Llama 4)
- Explain performance in natural language

#### UC-15: Capacity Planning Forecasting (V2)
- ML-based prediction of storage growth, compute needs, scaling events

**Tool/Method Inventory:**

| Method | Description | Frequency |
|---|---|---|
| `persist_pg_stat_statements(project, branch)` | Capture and write to Delta | Every 5 min |
| `detect_unused_indexes(project, branch, days=7)` | Find idx_scan=0 indexes | Every 1 hour |
| `detect_bloated_indexes(project, branch, threshold=2.0)` | Find bloat ratio > threshold | Every 1 hour |
| `detect_missing_indexes(project, branch)` | Find seq_scan >> idx_scan tables | Every 1 hour |
| `detect_duplicate_indexes(project, branch)` | Find overlapping column sets | Every 1 hour |
| `detect_missing_fk_indexes(project, branch)` | Find unindexed foreign keys | Every 1 hour |
| `generate_index_recommendation(analysis_results)` | Create scored recommendation | On detection |
| `schedule_vacuum_analyze(project, branch, tables)` | Execute VACUUM ANALYZE | Daily 2 AM |
| `schedule_vacuum_full(project, branch, table)` | Execute VACUUM FULL with lock check | On demand |
| `check_txid_wraparound_risk(project, branch)` | Alert on age > 500M | Every 5 min |
| `tune_autovacuum_parameters(project, branch, table)` | Adjust per-table settings | Daily |
| `analyze_slow_queries_with_ai(query_log_id)` | LLM-powered query analysis | On demand |
| `explain_query_in_natural_language(query_id)` | Plain English EXPLAIN | On demand |
| `forecast_capacity_needs(project, days_ahead=30)` | ML-based capacity planning | Weekly |
| `auto_tune_resource_parameters(workload_profile)` | Adjust runtime configs | On demand |

---

### Agent 3: Health & Self-Recovery Agent

**Core Mission:** Continuous "Day 2" monitoring with low-latency alerting and self-healing capabilities. Validate OLTP-to-OLAP sync integrity. Manage cold data lifecycle.

**Automation Targets from PRD:**

#### FR-04: Performance Alerting with SOP Triggers

| Metric | Warning | Critical | Auto-SOP |
|---|---|---|---|
| Buffer cache hit ratio | < 99% | < 95% | Analyze shared_buffers, recommend CU increase |
| Connection utilization | > 70% max | > 85% max | Alert DBA, auto-terminate idle > 30min |
| Dead tuple ratio (any table) | > 10% | > 25% | Schedule VACUUM ANALYZE |
| Lock wait time | > 30 seconds | > 120 seconds | Log lock chain, alert DBA |
| Deadlock count (per hour) | > 2 | > 5 | Capture blocking queries, alert DBA |
| Slow query (mean_exec_time) | > 5 seconds | > 30 seconds | Log EXPLAIN plan, add to review queue |
| Transaction ID age | > 500M | > 1B | Emergency VACUUM FREEZE |
| Replication lag | > 10s | > 60s | Alert DBA, investigate |

#### FR-05: OLTP-to-OLAP Sync Validation
- Compare row counts (Lakebase source vs. Delta target)
- Compare max(updated_at) timestamps
- Compute checksum on key columns
- Track sync freshness (time since last successful sync)
- Alert when freshness exceeds threshold (1h continuous, 24h batch)
- Store in `ops_catalog.lakebase_ops.sync_validation_history`

#### FR-07: Cold Data Archival to Delta Lake
- Identify cold data: rows not accessed/modified in > 90 days
- For partitioned tables: detach cold partitions
- Export to Delta in Unity Catalog (maintaining schema)
- Delete archived rows from Lakebase
- Create unified access views (hot + cold)
- Track in `ops_catalog.lakebase_ops.data_archival_history`

#### UC-10: Connection Pool Monitoring
- Track active/idle/idle-in-transaction connections
- Auto-terminate long-idle sessions (> 30 min)

#### UC-11: Cost Attribution & Optimization
- Track costs per project/branch from `system.billing.usage`
- Recommend scale-to-zero timeouts
- Alert on cost anomalies

#### UC-13: Self-Healing Incident Response (V2)
- Detect anomalies across all monitored metrics
- Diagnose root cause using correlation analysis
- Execute low-risk remediations automatically (vacuum, connection cleanup)
- Escalate high-risk issues with diagnosis for human approval

#### UC-14: Natural Language DBA Operations (V2)
- Enable developers to ask "Why is my query slow?"
- Provide actionable answers using Foundation Model API

**Tool/Method Inventory:**

| Method | Description | Frequency |
|---|---|---|
| `monitor_system_health(project, branch)` | Collect all health metrics | Every 5 min |
| `evaluate_alert_thresholds(metrics)` | Check all 8 metrics against thresholds | Every 5 min |
| `execute_low_risk_sop(issue_type, context)` | Auto-execute safe remediation | On threshold breach |
| `escalate_high_risk_issue(issue, diagnosis)` | Alert DBA with root cause analysis | On threshold breach |
| `validate_sync_completeness(source_table, target_table)` | Row count + timestamp comparison | Every 15 min |
| `validate_sync_integrity(source_table, target_table, key_cols)` | Checksum verification | Every 15 min |
| `track_sync_freshness(table_pairs)` | Time since last sync | Every 15 min |
| `identify_cold_data(project, branch, days=90)` | Find cold rows/partitions | Weekly |
| `archive_cold_data_to_delta(project, branch, table, policy)` | Full archival pipeline | Weekly |
| `create_unified_access_view(table, hot_source, cold_delta)` | Create hot+cold view | After archival |
| `monitor_connections(project, branch)` | Active/idle/idle-in-tx counts | Every 1 min |
| `terminate_idle_connections(project, branch, max_idle_min=30)` | Kill long-idle sessions | On threshold |
| `track_cost_attribution(project)` | Query system.billing.usage | Daily |
| `recommend_scale_to_zero_timeout(project, branch)` | Optimize idle timeout | Weekly |
| `diagnose_root_cause(anomaly_report)` | Correlate metrics for RCA | On anomaly |
| `self_heal(issue_id, remediation_plan)` | Execute approved auto-fix | On detection |
| `natural_language_dba(question)` | LLM-powered DBA Q&A | On demand |

---

## IV. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Metric collection latency | < 5 minutes from Lakebase to Delta |
| NFR-02 | Alert delivery time | < 2 minutes from threshold breach to notification |
| NFR-03 | Job reliability | 99.9% success rate for scheduled monitoring jobs |
| NFR-04 | OAuth token management | Automatic refresh before 1-hour expiry |
| NFR-05 | Multi-project support | Handle 50+ Lakebase projects per workspace |
| NFR-06 | Historical retention | 90 days for metrics, 365 days for audit events |
| NFR-07 | Cost overhead | Monitoring infrastructure < 5% of total Lakebase cost |
| NFR-08 | Security | All connections use OAuth; no static passwords |
| NFR-09 | Audit trail | All automated actions logged with actor, timestamp, reason |
| NFR-10 | Graceful degradation | Handle transient connection errors without cascading failures |

---

## V. Success Metrics

| Metric | Current Baseline | V1 Target | V2 Target |
|---|---|---|---|
| DBA toil hours/week | 20+ hours | < 5 hours | < 1 hour |
| Mean Time To Detection (MTTD) | 30+ minutes | < 5 minutes | < 1 minute |
| Mean Time To Resolution (MTTR) | 4+ hours | < 30 minutes | < 5 minutes |
| Automated remediation rate | 0% | 50% (low-risk) | 75% |
| OLTP-to-OLAP sync coverage | 0% (ad-hoc) | 100% configured | 100% |
| Index recommendation accuracy | N/A | > 80% accepted | > 90% |
| Orphaned branch count | Unknown | 0 (TTL enforced) | 0 |
| pg_stat Delta retention | 0 days (no Delta) | 90 days | 365 days |

---

## VI. Execution Steps & Output Format

1. Create a base `AgentFramework` class that coordinates all three agents with scheduling, event routing, and shared state.
2. Define each Agent class implementing ALL tool methods listed above.
3. Implement shared utilities: `LakebaseClient` (OAuth-aware), `DeltaWriter`, `AlertManager`.
4. Implement a main execution block that:
   - Instantiates the framework
   - Registers all three agents
   - Simulates a full automation cycle across all 5 phases
   - Demonstrates agent collaboration (Provisioning sets up → Performance starts monitoring → Health validates)
5. Include Databricks Jobs configurations and GitHub Actions YAML.
6. Include the AI/BI Dashboard SQL queries.

**Constraints:**
- Wrap all external calls in mock-capable clients (no live connections required for testing)
- Focus on clear, well-commented, professional Python with full type hints
- All SQL queries must use parameterized queries (no SQL injection)
- OAuth token refresh must be handled transparently
- Transient connection errors must be handled gracefully (no job failures)

---

## VII. PostgreSQL System Views Reference

### Essential Views for Automation

| View | Purpose | Collection Frequency |
|---|---|---|
| pg_stat_statements | Query performance metrics | Every 5 min |
| pg_stat_user_tables | Table stats (seq_scan, dead_tup, vacuum times) | Every 5 min |
| pg_stat_user_indexes | Index usage (idx_scan, idx_tup_read) | Every 1 hour |
| pg_stat_activity | Active connections and queries | Every 1 min |
| pg_locks | Lock information | Every 1 min |
| pg_stat_database | Database-level stats (deadlocks, cache hits) | Every 5 min |
| pg_statio_user_tables | I/O stats (heap_blks_hit, heap_blks_read) | Every 5 min |
| pg_stat_bgwriter | Legacy checkpoint statistics (see pg_stat_checkpointer) | Every 15 min |
| pg_stat_checkpointer | Checkpoint statistics (PG17, replaces bgwriter checkpoint cols) | Every 15 min |
| pg_stat_io | I/O statistics by backend type (PG16+) | Every 5 min |
| pg_stat_wal | WAL generation statistics (PG14+) | Every 5 min |
| pg_stat_statements_info | pg_stat_statements deallocation/reset tracking (PG14+) | Every 5 min |
| pg_index | Index metadata | Every 1 hour |

### Available Extensions
- pg_stat_statements, pg_hint_plan, pg_prewarm, pg_trgm, vector (pgvector), postgis, databricks_auth

### NOT Available (Workarounds Built Into Agents)
- pg_cron → Databricks Jobs scheduling (built into all agents)
- pg_repack → VACUUM FULL + REINDEX CONCURRENTLY (Performance Agent)
- pgstattuple → Statistical bloat estimation queries (Performance Agent)
- pg_partman → Partition management in Jobs (Health Agent cold archival)
- pg_buffercache → pg_statio views analysis (Health Agent)

---

## VIII. API Reference

### Lakebase REST API
| Operation | Method | Endpoint |
|---|---|---|
| Create project | POST | /api/2.0/postgres/projects |
| List projects | GET | /api/2.0/postgres/projects |
| Create branch | POST | /api/2.0/postgres/projects/{id}/branches |
| List branches | GET | /api/2.0/postgres/projects/{id}/branches |
| Delete branch | DELETE | /api/2.0/postgres/projects/{id}/branches/{bid} |
| Generate credential | POST | /api/2.0/postgres/credentials |

### Python SDK
```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.postgres.create_project(project_id=..., spec=ProjectSpec(...))
w.postgres.create_branch(parent=..., branch=Branch(spec=BranchSpec(...)), branch_id=...)
w.postgres.list_branches(parent=...)
w.postgres.delete_branch(name=...)
w.postgres.update_branch(name=..., update_mask=..., spec=...)
w.postgres.generate_database_credential(endpoint=...)
```

### Cost Tracking
```sql
SELECT usage_date, sku_name, usage_type, usage_metadata.database_instance_id,
       SUM(usage_quantity) as total_dbus
FROM system.billing.usage
WHERE billing_origin_product = 'DATABASE'
GROUP BY 1, 2, 3, 4
ORDER BY usage_date DESC;
```
