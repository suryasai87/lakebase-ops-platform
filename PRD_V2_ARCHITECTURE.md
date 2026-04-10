# LakebaseOps Platform — V2 Architecture & Implementation Reference

**Version:** 2.6
**Last Updated:** 2026-03-11
**Status:** Implemented & Tested (51 tools, 3 agents, 10 source engines, 3 dashboard enrichments, cross-cloud tier-aware pricing, environment sizing, AWS live pricing)

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

## I-C4. Summary of Changes from V2.5 to V2.6

### 23. Cost Estimator Audit & Rate Corrections

All source engine rates audited against public pricing APIs. Corrections applied:

| Engine | Old Rate | Corrected Rate | Source |
|--------|---------|---------------|--------|
| Aurora PostgreSQL (Standard) | $0.48/hr | $0.519/hr | AWS Price List API |
| RDS PostgreSQL | $0.48/hr | $0.45/hr | AWS Price List API |
| Azure Flexible Server | $0.37/hr | $0.356/hr | Azure Retail Prices API |

### 24. Aurora I/O-Optimized Engine

Added `aurora-postgresql-io` as a separate engine entry: $0.675/hr compute, $0.225/GB storage, $0/IO. ~40% of production Aurora customers use this tier, which bundles I/O into compute and storage pricing.

### 25. DynamoDB Pricing Model Restructure

Replaced the conflated `compute_per_hour` + `io_per_million` model with separate WRU ($1.25/M) and RRU ($0.25/M) rates. The cost formula now uses the workload's `reads_pct` / `writes_pct` to split QPS into reads vs writes, producing a 5x-accurate I/O cost estimate.

### 26. Azure Lakebase Cross-Cloud Uplift

Applied ~15% Azure uplift to Lakebase DBU rates:
- Azure Premium: $0.40 -> $0.46/DBU (vs AWS $0.40)
- Azure Enterprise: $0.52 -> $0.60/DBU (vs AWS $0.52)

Documented cross-cloud tier equivalence: Azure Premium = AWS Enterprise in feature set.

### 27. CU Estimate Formula Fix

Replaced the naive `avg_connections / 50` divisor with the assessment's actual `recommended_cu_min` / `recommended_cu_max` (or `connections / 209` as fallback). The previous formula overestimated CU by ~4x.

### 28. AWS Live Pricing Fetcher

Extended `config/pricing_fetcher.py` to fetch live pricing from the AWS Price List Bulk API for Aurora, RDS, and DynamoDB. Same 3-tier architecture as CosmosDB: live -> cache -> static.

### 29. Committed-Use Discount References

Added Lakebase committed-use discount reference lines to the cost estimate response: 1-year (~25%), 3-year (~40%) savings with estimated totals per commitment level.

### 30. Confidence Indicators & Documentation

Added `confidence` field to each engine (`verified` / `estimated` / `stale`) and `last_verified` dates. Added "Rate Validation" section to README with curl commands for verifying rates against public APIs.

## I-C3. Summary of Changes from V2.4 to V2.5

### 18. Corrected Lakebase Pricing Model

The Lakebase DBU rate was incorrectly set to `$0.070/DBU` (Model Serving rate). Corrected to use the **Database Serverless Compute** SKU:

| Tier | DBU Rate (US) | SKU Pattern |
|------|---------------|-------------|
| Premium | $0.40/DBU | `PREMIUM_DATABASE_SERVERLESS_COMPUTE_{REGION}` |
| Enterprise | $0.52/DBU | `ENTERPRISE_DATABASE_SERVERLESS_COMPUTE_{REGION}` |

The compute formula was corrected from `CU x 2 DBU/CU x rate x 730` to `CU x 1 DBU/CU/hr x rate x 730` (Lakebase bills at 1 DBU per CU per hour).

**Pricing provenance** added to the registry: `source_url`, `sku_pattern`, `last_verified`, `dbu_per_cu_hour` constants.

### 19. Tier-Aware Cost Estimation

The cost estimate API now accepts `?tier=premium|enterprise` (default: `premium`). Response includes:

- `tier` and `tier_label` fields
- `sku_name` (resolved SKU for the region)
- Correct DBU rate for the selected tier
- `LAKEBASE_COST_DISCLAIMER` with explicit "contact your Databricks account team" guidance

### 20. Environment-Aware Sizing Recommendations

New `EnvironmentSizing` dataclass and `CU_TO_MAX_CONNECTIONS` mapping based on official Lakebase specs:

| Metric | Dev | Staging | Prod |
|--------|-----|---------|------|
| CU range | prod_min/4 - prod_min/2 | prod_min - prod_min+4 | Workload-derived |
| Scale-to-zero | Yes (15 min) | Yes (30 min) | No (always-on) |
| Autoscaling | Yes | Yes | Yes |

Prod sizing is derived from peak connections (209 conns/CU), QPS, and working set size (2 GB/CU).

The readiness API now returns `sizing_by_env` with per-environment CU ranges, scale-to-zero, max connections, RAM, and notes.

### 21. Per-Environment Cost Breakdown

Cost estimate API now returns `env_cost_breakdown` with per-environment monthly cost estimates:
- Dev: ~35% utilization (scale-to-zero during idle)
- Staging: ~60% utilization (scale-to-zero with moderate usage)
- Prod: 100% utilization (always-on, average of CU range)

### 22. Frontend Enhancements

- **CostEstimate.tsx:** Displays tier label (`Premium`/`Enterprise`), SKU reference, 1 DBU/CU/hr assumption, stronger disclaimer
- **Assessment.tsx:** New "Environment Sizing" card with dev/staging/prod recommendation table and Premium/Enterprise tier toggle
- Tier selector dynamically refetches cost estimates with the selected tier

**Files changed:**
- `config/pricing.py` - Tier-aware `LAKEBASE_PRICING`, corrected DBU rates, `LAKEBASE_COST_DISCLAIMER`
- `config/migration_profiles.py` - `EnvironmentSizing` dataclass, `CU_TO_MAX_CONNECTIONS`, `max_connections_for_cu()`
- `utils/readiness_scorer.py` - `_recommend_sizing()` returns per-env sizing, `_snap_cu()` helper
- `agents/provisioning/assessment.py` - `sizing_by_env` in assessment summary
- `app/backend/routers/assessment.py` - Tier param, corrected formula, env cost breakdown, sizing in readiness
- `app/frontend/src/components/CostEstimate.tsx` - Tier label, SKU, enhanced disclaimer
- `app/frontend/src/pages/Assessment.tsx` - Environment Sizing table, tier selector
- `tests/test_assessment.py` - Pricing registry, environment sizing, cost formula tests
- `app/backend/tests/test_routers.py` - Tier param, enterprise tier, sizing_by_env tests

---

## I-C2. Summary of Changes from V2.3 to V2.4

### 13. Live Cosmos DB Discovery Adapter

Added a live discovery adapter (`agents/provisioning/cosmos_adapter.py`) that connects to a real Azure Cosmos DB account using the `azure-cosmos` Python SDK:

- Extracts account properties: consistency level, multi-region writes, regions, backup policy
- Discovers containers: partition keys, throughput (provisioned/autoscale), indexing policies, item counts
- Derives `DatabaseProfile` directly from live data, no mock required
- Graceful fallback: if `azure-cosmos` is not installed or discovery fails, routes to CosmosDB-specific mock data (not PostgreSQL mock)

**Engine-aware routing in `assessment.py`:** When `mock=False` and `source_engine == "cosmosdb-nosql"`, `connect_and_discover` and `profile_workload` call the live adapter. The workload profile is derived from discovered RU capacity.

### 14. 3-Tier Dynamic Pricing Architecture

Replaced static-only pricing for CosmosDB with a layered fetch strategy (`config/pricing_fetcher.py`):

| Tier | Source | TTL | Fallback |
|------|--------|-----|----------|
| 1. Live | Azure Retail Prices API (`prices.azure.com`) | N/A | -> Tier 2 |
| 2. Cache | `~/.lakebase-ops/pricing_cache.json` | 24 hours | -> Tier 3 |
| 3. Static | `config/pricing.py` registry | N/A | Always available |

The API response now includes `pricing_source` ("live", "cached", or "static") so the UI can display a pricing provenance indicator.

### 15. Enhanced CosmosDB Cost Model

The cost estimator for CosmosDB now accounts for:

- **Multi-region writes:** multiplier based on region count (default 1.0 for single-region)
- **Autoscale throughput:** models utilization at ~66% of max RU for cost estimation
- **Backup policy:** continuous backup adds ~20% surcharge vs periodic
- **Reserved capacity:** reference line showing potential savings with 1-year reservation
- **Detailed breakdown:** API returns `cosmos_cost_detail` with per-component costs

### 16. Readiness Warnings Propagation Fix

Fixed a bug where readiness scorer warnings were aliased to `unsupported_extensions` instead of being passed through as distinct, human-readable strings.

**Backend:** `assess_readiness` summary now includes `"warnings": list(assessment.warnings)`.
**API:** `/api/assessment/readiness` returns both `unsupported_extensions` and `warnings` as separate fields.
**UI:** New "Migration Warnings" `Accordion` (default expanded) in `Assessment.tsx` with severity-aware Alert components.

### 17. New DatabaseProfile Fields

| Field | Type | Purpose |
|-------|------|---------|
| `cosmos_autoscale_max_ru` | `int | None` | Autoscale max throughput for cost model |
| `cosmos_backup_policy` | `str | None` | "continuous" or "periodic" for backup cost |

**Files changed:**
- `agents/provisioning/cosmos_adapter.py` (new) - Live CosmosDB discovery adapter
- `config/pricing_fetcher.py` (new) - 3-tier pricing fetch/cache/fallback
- `config/migration_profiles.py` - New `DatabaseProfile` fields
- `agents/provisioning/assessment.py` - Engine-aware routing, live discovery/workload methods, warnings in summary
- `app/backend/routers/assessment.py` - Live pricing integration, enhanced cost model, warnings fix
- `app/frontend/src/pages/Assessment.tsx` - Migration Warnings section, pricing source pass-through
- `app/frontend/src/components/CostEstimate.tsx` - Pricing source indicator chip
- `app/backend/tests/test_routers.py` - CosmosDB cost, feature matrix, warnings tests
- `tests/test_assessment.py` - Live discover fallback, pricing fetcher, warnings propagation tests
- `app/frontend/src/__tests__/Assessment.test.tsx` (new) - CosmosDB discovery & warnings rendering tests

---

## I-C. Summary of Changes from V2.2 to V2.3

### 12. Azure Cosmos DB Source Engine (8 -> 9)

Added Azure Cosmos DB (NoSQL API) as the second NoSQL source engine, extending the cross-engine migration pattern established by DynamoDB:

| Engine | Cloud | Type | Key Features |
|--------|-------|------|-------------|
| Azure Cosmos DB (NoSQL) | Azure | NoSQL | Partition keys, RU-based throughput, Change Feed, Multi-region writes, 5 consistency levels, Container-level indexing policies |

**CosmosDB-specific DatabaseProfile fields:** `cosmos_throughput_mode`, `cosmos_ru_per_sec`, `cosmos_partition_key_paths`, `cosmos_consistency_level`, `cosmos_change_feed_enabled`, `cosmos_multi_region_writes`, `cosmos_regions`, `cosmos_container_details` (all `Optional`, `None` for non-CosmosDB engines).

**Files changed:**
- `config/migration_profiles.py` - Added `COSMOSDB_NOSQL` to `SourceEngine`, `ENGINE_KIND` map, CosmosDB-specific fields to `DatabaseProfile`
- `agents/provisioning/assessment.py` - Added `_mock_discover_cosmosdb()`, `_mock_workload_cosmosdb()`, conditional summary fields for CosmosDB
- `utils/readiness_scorer.py` - Added `COSMOSDB_FEATURE_SUPPORT`, `COSMOSDB_FEATURE_WORKAROUNDS`, CosmosDB scoring paths (features, complexity, replication, operational)
- `utils/blueprint_generator.py` - CosmosDB engine maps, CosmosDB-specific phases (relational modeling from partition keys, ADF/Spark export, SDK rewrite)
- `config/pricing.py` - CosmosDB provisioned throughput pricing entry (RU/s-based compute, GB-based storage)
- `app/backend/routers/assessment.py` - CosmosDB feature matrix, RU-based cost estimation, pricing URLs, enhanced disclaimer
- `app/frontend/src/pages/Assessment.tsx` - CosmosDB engine option, conditional discovery display (RU/s, consistency, Change Feed)
- `app/frontend/src/components/CostEstimate.tsx` - Pricing URLs display, prominent cost disclaimer banner
- `test_assessment.py` - 4 new CosmosDB tests (discovery, readiness, blueprint, end-to-end)

---

## I-D. Summary of Changes from V2.1 to V2.2

### 11. Amazon DynamoDB Source Engine (7 -> 8)

Added DynamoDB as the first NoSQL source engine, introducing cross-engine (NoSQL-to-relational) migration assessment:

| Engine | Cloud | Type | Key Features |
|--------|-------|------|-------------|
| Amazon DynamoDB | AWS | NoSQL | GSI/LSI, Streams, TTL, PITR, DAX, Global Tables, on-demand/provisioned billing |

**ENGINE_KIND discriminator:** New `ENGINE_KIND` dictionary in `config/migration_profiles.py` classifies engines as `pg` or `nosql`, enabling conditional logic throughout the assessment pipeline.

**DynamoDB-specific DatabaseProfile fields:** `billing_mode`, `gsi_count`, `lsi_count`, `streams_enabled`, `ttl_enabled`, `pitr_enabled`, `global_table_regions`, `item_size_avg_bytes`, `dynamo_table_details` (all `Optional`, `None` for PostgreSQL engines).

**Files changed:**
- `config/migration_profiles.py` - Added `DYNAMODB` to `SourceEngine`, `ENGINE_KIND` map, DynamoDB-specific fields to `DatabaseProfile`
- `agents/provisioning/assessment.py` - Added `_mock_discover_dynamodb()`, `_mock_workload_dynamodb()`, conditional summary fields for NoSQL
- `utils/readiness_scorer.py` - Added `DYNAMODB_FEATURE_SUPPORT`, `DYNAMODB_FEATURE_WORKAROUNDS`, NoSQL scoring paths for all 6 dimensions
- `utils/blueprint_generator.py` - DynamoDB engine maps, `CROSS_ENGINE` strategy, DynamoDB-specific phases (relational modeling, S3 export, ETL, app rewrite)
- `config/pricing.py` - DynamoDB on-demand pricing entry with WRU/RRU formulas
- `app/backend/routers/assessment.py` - Feature matrix for NoSQL, DynamoDB cost estimation
- `app/frontend/src/pages/Assessment.tsx` - DynamoDB engine option, conditional discovery display, `NOSQL_ENGINES` set
- `app/frontend/src/components/ExtensionMatrix.tsx` - Conditional "Feature Compatibility" title for NoSQL
- `test_assessment.py` - 4 new DynamoDB tests (discovery, readiness, blueprint, end-to-end)

---

## I-B. Summary of Changes from V2.0 to V2.1

### 7. Expanded Source Engine Support (5 -> 7)

Added two new source database engines to the `SourceEngine` enum and all dependent modules:

| Engine | Cloud | Key Extensions / Features |
|--------|-------|--------------------------|
| AlloyDB for PostgreSQL | GCP | `google_ml_integration`, `pgvector`, columnar engine, IAM auth |
| Supabase PostgreSQL | Multi | `pg_graphql`, `pgjwt`, `supautils`, platform-managed auth/storage/realtime schemas |

**Files changed:**
- `config/migration_profiles.py` - Added `ALLOYDB_POSTGRESQL` and `SUPABASE_POSTGRESQL` to `SourceEngine` enum
- `agents/provisioning/assessment.py` - Added `_mock_discover_alloydb()` and `_mock_discover_supabase()` with engine-specific extension profiles and edge cases
- `utils/blueprint_generator.py` - Updated engine labels, auth migration notes, pooling notes, decommission steps, and network prerequisites for both engines
- `utils/readiness_scorer.py` - Added `pgjwt` and `supautils` to `EXTENSION_WORKAROUNDS`

### 8. Dashboard Enrichment Widgets

Three new visualization components added to the Assessment and Dashboard pages:

**Extension Compatibility Matrix** (`app/frontend/src/components/ExtensionMatrix.tsx`)
- Displays each discovered extension with version, Lakebase support status (supported / workaround / unsupported), and detailed notes
- Color-coded status chips with summary counts
- Backend endpoint: `GET /api/assessment/extension-matrix/{profile_id}`

**Migration Timeline Gantt** (`app/frontend/src/components/GanttChart.tsx`)
- Horizontal bar chart (Recharts) showing 4 migration phases with start day, duration, total effort
- Displays strategy and risk level per phase with color-coded chips
- Backend endpoint: `GET /api/assessment/timeline/{profile_id}`

**Cost Estimation Widget** (`app/frontend/src/components/CostEstimate.tsx`)
- Side-by-side cost comparison: source engine monthly cost vs Lakebase DBU pricing
- Breakdown by compute, storage, and I/O with formula tooltips on hover
- Displays pricing disclaimer, version, region, instance reference, and source URL links
- Backend endpoint: `GET /api/assessment/cost-estimate/{profile_id}`

### 9. Static Pricing Registry (`config/pricing.py`)

Centralized, auditable pricing configuration replacing hardcoded values:

- `PRICING_VERSION` - date-stamped version for tracking when rates were last verified
- `PRICING_DISCLAIMER` - standard disclaimer text displayed on all cost widgets
- `SOURCE_ENGINES` - per-engine pricing with `instance_ref`, `source_url`, `last_verified`, and per-region rates (compute/storage/I/O)
- `LAKEBASE_PRICING` - DBU and DSU rates per region with formulas
- `CLOUD_REGIONS` - available regions per cloud provider (AWS, GCP, Azure)
- `ENGINE_CLOUD_MAP` - maps each engine to its cloud provider
- Helper functions: `get_source_rates()`, `get_lakebase_rates()`, `get_regions_for_engine()`

### 10. Dynamic Region Selection

The Assessment UI dynamically updates available regions based on the selected source engine:
- Engine selection triggers `GET /api/assessment/regions/{engine}` to fetch available regions
- Region dropdown populates with cloud-specific regions (e.g., AWS regions for Aurora, GCP regions for AlloyDB)
- Selected region flows through to cost estimation for accurate per-region pricing
- A `default` fallback rate is provided when a specific region is not in the registry

---

## II. Project Structure

```
lakebase-ops-platform/
├── main.py                          # Orchestrator - runs full 5-phase simulation
├── deploy_and_test.py               # Real deployment & test suite
├── test_assessment.py               # Assessment pipeline unit tests
├── ENHANCED_PROMPT.md               # Original PRD (updated for PG17)
├── PRD_V2_ARCHITECTURE.md           # This document
|
├── config/
│   ├── __init__.py
│   ├── settings.py                  # All constants: workspace, catalog, tables, thresholds
│   ├── migration_profiles.py        # Assessment dataclasses + SourceEngine enum (9 engines)
│   ├── pricing.py                   # Static pricing registry: per-engine, per-region rates + formulas
│   └── pricing_fetcher.py           # Live pricing: Azure Retail API fetch, file cache (24h TTL), static fallback
|
├── framework/
│   ├── __init__.py
│   └── agent_framework.py           # BaseAgent, AgentFramework, EventType, TaskResult
|
├── sql/
│   ├── __init__.py
│   ├── queries.py                   # 21 named SQL constants (single source of truth)
│   └── assessment_queries.py        # Assessment discovery + profiling SQL
|
├── agents/
│   ├── __init__.py                  # Re-exports: ProvisioningAgent, PerformanceAgent, HealthAgent
│   |
│   ├── provisioning/                # 17+ tools
│   │   ├── __init__.py
│   │   ├── agent.py                 # ProvisioningAgent class, register_tools(), run_cycle()
│   │   ├── project.py               # ProjectMixin: provision_lakebase_project, create_ops_catalog
│   │   ├── branching.py             # BranchingMixin: create/protect/enforce_ttl/monitor/reset branches
│   │   ├── migration.py             # MigrationMixin: apply_migration, capture_schema_diff, test_migration
│   │   ├── cicd.py                  # CICDMixin: setup_cicd_pipeline
│   │   ├── governance.py            # GovernanceMixin: configure_rls, uc_integration, ai_branching
│   │   ├── assessment.py            # AssessmentMixin: 4-step pipeline, 7 engine-specific mocks, live routing
│   │   └── cosmos_adapter.py        # CosmosDiscoveryAdapter: live azure-cosmos SDK discovery
│   |
│   ├── performance/                 # 14 tools
│   │   ├── __init__.py
│   │   ├── agent.py                 # PerformanceAgent class, register_tools(), run_cycle()
│   │   ├── metrics.py               # MetricsMixin: persist_pg_stat_statements, collect_pg_stat_statements_info
│   │   ├── indexes.py               # IndexMixin: 6 detect methods + run_full_index_analysis
│   │   ├── maintenance.py           # MaintenanceMixin: vacuum, txid wraparound, autovacuum tuning
│   │   └── optimization.py          # OptimizationMixin: AI query analysis, capacity forecasting
│   |
│   └── health/                      # 16 tools
│       ├── __init__.py
│       ├── agent.py                 # HealthAgent class, register_tools(), run_cycle()
│       ├── monitoring.py            # MonitoringMixin: system_health, alerts, SOPs
│       ├── sync.py                  # SyncMixin: completeness, integrity, full_sync_validation
│       ├── archival.py              # ArchivalMixin: cold_data, archive_to_delta, unified_view
│       ├── connections.py           # ConnectionMixin: monitor, terminate_idle
│       └── operations.py            # OperationsMixin: cost, scale_to_zero, diagnose, self_heal, nl_dba
|
├── utils/
│   ├── __init__.py
│   ├── lakebase_client.py           # OAuth-aware PG client with mock mode
│   ├── delta_writer.py              # Unity Catalog Delta writer with mock mode
│   ├── alerting.py                  # Multi-channel alert manager (Slack, PagerDuty, DBSQL)
│   ├── readiness_scorer.py          # 6-dimension readiness scoring + extension workarounds
│   └── blueprint_generator.py       # Engine-aware 4-phase migration blueprint
|
├── app/                             # Databricks App (FastAPI + React)
│   ├── app.yaml
│   ├── backend/
│   │   ├── main.py                  # FastAPI entry point (SPA + API)
│   │   └── routers/
│   │       └── assessment.py        # Assessment + enrichment endpoints (9 routes)
│   └── frontend/
│       └── src/
│           ├── pages/
│           │   ├── Dashboard.tsx     # KPI overview + Gantt + cost summary
│           │   └── Assessment.tsx    # 4-step wizard + enrichment widgets
│           ├── components/
│           │   ├── GanttChart.tsx    # Migration timeline Gantt (Recharts)
│           │   ├── ExtensionMatrix.tsx # Extension compatibility matrix
│           │   └── CostEstimate.tsx  # Cost comparison with formulas + disclaimer
│           └── hooks/
│               └── useApiData.ts    # Polling data fetcher with retry
|
├── jobs/
│   ├── __init__.py
│   └── databricks_job_definitions.py # Databricks Jobs configurations
|
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
| | AssessmentMixin | `assessment.py` | connect_and_discover, profile_workload, assess_readiness, generate_migration_blueprint |
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

## VII. Tool Inventory (51 Total)

### Provisioning & DevOps Agent (21 tools)

| Tool | Schedule | Risk | Approval | Module |
|------|----------|------|----------|--------|
| `provision_lakebase_project` | - | low | no | project.py |
| `create_ops_catalog` | - | low | no | project.py |
| `create_branch` | - | low | no | branching.py |
| `protect_branch` | - | medium | no | branching.py |
| `enforce_ttl_policies` | `0 */6 * * *` | low | no | branching.py |
| `monitor_branch_count` | `0 */6 * * *` | low | no | branching.py |
| `reset_branch_from_parent` | `0 2 * * *` | low | no | branching.py |
| `create_branch_on_pr` | - | low | no | branching.py |
| `delete_branch_on_pr_close` | - | low | no | branching.py |
| `apply_schema_migration` | - | medium | no | migration.py |
| `capture_schema_diff` | - | low | no | migration.py |
| `test_migration_on_branch` | - | low | no | migration.py |
| `setup_cicd_pipeline` | - | low | no | cicd.py |
| `configure_rls` | - | high | **yes** | governance.py |
| `setup_unity_catalog_integration` | - | low | no | governance.py |
| `setup_ai_agent_branching` | - | low | no | governance.py |
| `provision_with_governance` | - | low | no | governance.py |
| `connect_and_discover` | - | low | no | assessment.py |
| `profile_workload` | - | low | no | assessment.py |
| `assess_readiness` | - | low | no | assessment.py |
| `generate_migration_blueprint` | - | low | no | assessment.py |

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
  3 Agents | 51 Tools | 8 Events | 59 Records Written

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

Assessment Coverage:
  - 9 source engines tested (Aurora, RDS, Cloud SQL, Azure, Self-Managed, AlloyDB, Supabase, DynamoDB, CosmosDB)
  - Per-engine extension/feature profiles verified (unique extensions per PG engine, feature matrix for DynamoDB and CosmosDB)
  - Region-aware cost estimation verified across AWS, GCP, Azure regions
  - Extension compatibility matrix validated (supported/workaround/unsupported)
  - DynamoDB feature compatibility matrix validated (Streams, TTL, DAX, Global Tables)
  - DynamoDB cross-engine blueprint verified (relational modeling, S3 export, ETL, app rewrite)
  - CosmosDB feature compatibility matrix validated (Change Feed, Multi-region writes, Consistency levels, Integrated cache)
  - CosmosDB cross-engine blueprint verified (relational modeling, ADF/Spark export, SDK rewrite)
  - Pricing formulas verified against config/pricing.py registry (including DynamoDB WRU/RRU, CosmosDB RU/s)

Verification:
  - No information_schema references in agents/
  - No "lost on scale" references in codebase
  - No compute_status in agents/ or utils/
  - All imports resolve from sub-packages
```

---

## IX. Assessment API & Enrichment Architecture

### Endpoint Map

| Method | Route | Source | Description |
|--------|-------|--------|-------------|
| `POST` | `/api/assessment/discover` | `assessment.py` | Run discovery (schema, extensions, edge cases) |
| `POST` | `/api/assessment/profile/{id}` | `assessment.py` | Profile workload (QPS, TPS, connections) |
| `POST` | `/api/assessment/readiness/{id}` | `assessment.py` | Score readiness (6 dimensions) |
| `POST` | `/api/assessment/blueprint/{id}` | `assessment.py` | Generate 4-phase migration blueprint |
| `GET` | `/api/assessment/extension-matrix/{id}` | `assessment.py` | Extension (PG) or feature (DynamoDB/CosmosDB) compatibility matrix |
| `GET` | `/api/assessment/timeline/{id}` | `assessment.py` | Migration timeline for Gantt chart |
| `GET` | `/api/assessment/cost-estimate/{id}` | `assessment.py` | Region-aware cost comparison |
| `GET` | `/api/assessment/regions/{engine}` | `assessment.py` | Available regions for engine |
| `GET` | `/api/assessment/history` | `assessment.py` | List past assessment profiles |

### Cost Estimation Data Flow

```
Assessment.tsx                    Backend                         Pricing (3-tier)
+------------------+    POST     +--------------------+
| Select engine    |------------>| /discover          |          Tier 1: Live
| Select region    |    GET      | /regions/{engine}  |          +------------------+
| Select tier      |------------>| /blueprint/{id}    |     +--->| Azure Retail API |
| (Premium/Ent.)   |    GET      | /cost-estimate/{id}|-+   |    | prices.azure.com |
|                  |    ?tier=   |  pricing_source    | |   |    +------------------+
|                  |<------------|  tier, tier_label   | +---+         |
| CostEstimate.tsx |             |  sku_name          |     |    Tier 2: Cache
| - Tier label     |             |  env_cost_breakdown|     |    +------------------+
| - SKU reference  |             |  cosmos_cost_detail|     +--->| ~/.lakebase-ops/ |
| - Disclaimer     |             |                    |     |    | pricing_cache    |
| - Formula tips   |             | Formula (v2.5):    |     |    | (24h TTL)        |
| - Pricing source |             |  CU x 1 DBU/CU/hr |     |    +------------------+
|                  |             |  x dbu_rate x 730  |     |         |
| Env Sizing Table |             |                    |     |    Tier 3: Static
| - dev/stg/prod   |             | LAKEBASE_PRICING:  |     |    +------------------+
| - CU ranges      |             |  premium:  $0.40   |     +--->| config/pricing.py|
| - scale-to-zero  |             |  enterprise: $0.52 |          | SOURCE_ENGINES   |
| - max connections |             +--------------------+          | LAKEBASE_PRICING |
+------------------+                                             | (tier-aware)     |
                                                                 +------------------+
```

### Pricing Registry Schema (`config/pricing.py`)

```python
SOURCE_ENGINES = {
    "aurora-postgresql": {
        "label": "Aurora PostgreSQL",
        "cloud": "aws",
        "instance_ref": "db.r6g.xlarge",
        "source_url": "https://aws.amazon.com/rds/aurora/pricing/",
        "last_verified": "2026-03",
        "regions": {
            "us-east-1": {"compute_per_hour": ..., "storage_per_gb_month": ..., "io_per_million": ...},
            "default": {...}
        },
        "formulas": {...}
    },
    ...
}

LAKEBASE_PRICING = {
    "source_url": "https://www.databricks.com/product/pricing/lakebase",
    "sku_pattern": "{PREMIUM|ENTERPRISE}_DATABASE_SERVERLESS_COMPUTE_{REGION}",
    "last_verified": "2026-03",
    "dbu_per_cu_hour": 1,
    "tiers": {
        "premium": {"label": "Premium", "regions": {"aws-us-east-1": {"dbu_rate": 0.40, ...}, ...}},
        "enterprise": {"label": "Enterprise", "regions": {"aws-us-east-1": {"dbu_rate": 0.52, ...}, ...}},
    },
    "formulas": {
        "compute": "CU x 1 DBU/CU/hr x dbu_rate x 730 hrs/month",
        "storage": "storage_gb x dsu_rate_per_gb_month",
    },
}
```

### SourceEngine Enum (9 engines)

```python
class SourceEngine(Enum):
    AURORA_POSTGRESQL = "aurora-postgresql"
    RDS_POSTGRESQL = "rds-postgresql"
    CLOUD_SQL_POSTGRESQL = "cloud-sql-postgresql"
    AZURE_POSTGRESQL = "azure-postgresql"
    SELF_MANAGED_POSTGRESQL = "self-managed-postgresql"
    ALLOYDB_POSTGRESQL = "alloydb-postgresql"
    SUPABASE_POSTGRESQL = "supabase-postgresql"
    AURORA_MYSQL = "aurora-mysql"
    DYNAMODB = "dynamodb"
    COSMOSDB_NOSQL = "cosmosdb-nosql"
```

### ENGINE_KIND Discriminator

```python
ENGINE_KIND: dict[str, str] = {
    "dynamodb": "nosql",
    "cosmosdb-nosql": "nosql",
    "aurora-postgresql": "pg",
    "rds-postgresql": "pg",
    "cloud-sql-postgresql": "pg",
    "azure-postgresql": "pg",
    "self-managed-postgresql": "pg",
    "alloydb-postgresql": "pg",
    "supabase-postgresql": "pg",
    "aurora-mysql": "pg",
}
```

Used throughout the assessment pipeline to branch between PostgreSQL and NoSQL logic.

---

## X. Migration Guide (V1 -> V2)

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
