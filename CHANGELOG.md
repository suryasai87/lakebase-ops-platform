# Changelog

All notable changes to the lakebase-ops-platform are documented here.

## [Unreleased] - 2026-04-05

### Added

- **GAP-032**: Lakehouse Sync CDC monitoring (`agents/health/lakehouse_sync.py`)
  - `configure_lakehouse_sync()` -- set up CDC pipeline configuration
  - `monitor_replication_lag()` -- check replication lag via pg_stat_replication
  - `validate_scd_history()` -- verify SCD Type 2 integrity in Delta targets
  - Backend route: `GET /api/operations/lakehouse-sync`
  - SQL constants: `LAKEHOUSE_SYNC_REPLICATION_LAG`, `LAKEHOUSE_SYNC_SLOT_STATUS`, `LAKEHOUSE_SYNC_WAL_SENDERS`
  - Delta table: `lakehouse_sync_status`

- **GAP-033**: Budget policies and tags on project creation
  - `provision_lakebase_project()` now accepts `tags` and `budget_policy_id` parameters
  - Default tags applied: `domain`, `environment`, `managed_by`
  - `update_project_tags()` and `get_project_tags()` added to `LakebaseClient`

- **GAP-034**: Catalog registration via Lakebase API
  - `register_lakebase_catalog()` tool in `GovernanceMixin`
  - `register_catalog()` and `get_catalog_status()` in `LakebaseClient`
  - Uses `POST /api/2.0/postgres/catalogs` endpoint

- **GAP-036**: Synced Tables API integration
  - `get_synced_table_api_status()` in `SyncMixin` queries official API
  - `get_synced_table_status()` in `LakebaseClient`
  - `run_full_sync_validation()` now includes API status alongside row count checks

- **GAP-046**: Operational documentation
  - `docs/DEPLOYMENT.md` -- deployment runbook for FEVM HLS AMER
  - `docs/CONTRIBUTING.md` -- contribution guidelines
  - `CHANGELOG.md` -- this file

- **GAP-047**: Methodology documentation
  - `docs/playbook/branch-based-development.md` -- branch workflow patterns
  - `docs/playbook/dba-transition-guide.md` -- DBA-to-platform transition

- **GAP-048**: Naming conventions
  - `docs/naming-conventions.md` -- UC + Lakebase naming reference

- **GAP-049**: Demo workflow
  - `demo/agile_workflow_demo.py` -- end-to-end demo script

### Changed

- `agents/provisioning/project.py`: `provision_lakebase_project()` signature extended with `tags` and `budget_policy_id`
- `agents/health/sync.py`: `run_full_sync_validation()` includes Synced Tables API check
- `sql/queries.py`: Added Lakehouse Sync monitoring queries
- `config/settings.py`: Added `lakehouse_sync_status` to `DELTA_TABLES`
- `utils/lakebase_client.py`: Added tag management, catalog registration, and synced table methods
- `app/backend/routers/operations.py`: Added `/api/operations/lakehouse-sync` endpoint
