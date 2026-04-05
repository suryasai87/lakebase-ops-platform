# Naming Conventions

## Lakebase Resource Names

All Lakebase resource names must be **RFC 1123 compliant**:
- Lowercase letters, digits, and hyphens only
- 1-63 characters
- Must start and end with alphanumeric character

### Projects

Format: `{domain}-{environment}`

| Example | Domain | Environment |
|---------|--------|-------------|
| `supply-chain-prod` | supply-chain | production |
| `hls-amer-staging` | hls-amer | staging |
| `retail-analytics-dev` | retail-analytics | development |

### Branches

See `config/settings.py` `BRANCH_NAMING` for the full mapping.

| Type | Pattern | Example |
|------|---------|---------|
| CI/CD | `ci-pr-{number}` | `ci-pr-142` |
| Hotfix | `hotfix-{ticket_id}` | `hotfix-jira-5271` |
| Performance | `perf-{test_name}` | `perf-load-test-q4` |
| Feature | `feat-{description}` | `feat-cdc-monitor` |
| Developer | `dev-{firstname}` | `dev-surya` |
| Demo | `demo-{customer}` | `demo-stryker` |
| QA | `qa-release-{version}` | `qa-release-2-1` |
| Audit | `audit-{date}` | `audit-20260405` |
| AI Agent | `ai-agent-test` | `ai-agent-test` |

## Unity Catalog Names

UC uses **underscores** (not hyphens). When mapping between Lakebase and UC:

```
Lakebase:  supply-chain-prod    (hyphens)
UC:        supply_chain_prod    (underscores)
```

### Catalog Naming

Format: `{domain}_{environment}_catalog` or just `{domain}_catalog`

| Lakebase Project | UC Catalog |
|-----------------|------------|
| `hls-amer-prod` | `hls_amer_catalog` |
| `supply-chain-prod` | `supply_chain_catalog` |

### Schema Naming

Format: `{purpose}` within the catalog

| Schema | Purpose |
|--------|---------|
| `lakebase_ops` | Operational metrics and lifecycle data |
| `lakebase_archive` | Cold data archive tables |
| `gold` | Business-ready analytics tables |

### Delta Table Naming

Format: `{catalog}.{schema}.{table_name}`

Operational tables follow `{entity}_{type}` convention:

| Table | Purpose |
|-------|---------|
| `pg_stat_history` | Historical pg_stat_statements snapshots |
| `index_recommendations` | Index analysis results |
| `vacuum_history` | Vacuum operation records |
| `sync_validation_history` | OLTP-to-OLAP sync checks |
| `branch_lifecycle` | Branch create/delete/archive events |
| `lakehouse_sync_status` | CDC replication monitoring |
| `data_archival_history` | Cold data archival records |
| `migration_assessments` | Migration readiness assessments |

## Tags

Custom tags on Lakebase projects (GA since March 2026):

| Key | Example Value | Purpose |
|-----|---------------|---------|
| `domain` | `supply-chain` | Business domain |
| `environment` | `production` | Deployment target |
| `managed_by` | `lakebase-ops-platform` | Automation attribution |
| `cost_center` | `eng-platform` | Finance/billing |
| `team` | `hls-amer` | Owning team |
