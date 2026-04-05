# DBA Transition Guide: Traditional PostgreSQL to Lakebase

## Who This Is For

Database administrators and platform engineers transitioning from self-managed PostgreSQL (on-prem or IaaS) to Databricks Lakebase. This guide maps familiar DBA operations to their Lakebase equivalents.

## What Changes

| Traditional DBA Task | Lakebase Equivalent |
|---------------------|---------------------|
| Provision servers, install PG | `POST /api/2.0/postgres/projects` (one API call) |
| Configure `postgresql.conf` | Autoscaling handles most tuning automatically |
| Manage replication | Built-in HA with automatic failover (GA) |
| Backup/restore | Instant branching + point-in-time restore (0-30 days) |
| Schema migrations | Branch-based: test on branch, diff, promote |
| Monitor via `pg_stat_*` | Same `pg_stat_*` views + Databricks Metrics Dashboard |
| Connection pooling | OAuth-based credentials, auto-managed pool |
| VACUUM management | Autovacuum runs automatically; manual vacuum still available |
| Index management | Same `CREATE INDEX CONCURRENTLY` workflow |
| Security/RLS | Standard PG RLS + UC governance + OAuth roles |
| Cost management | Budget policies + custom tags (GA since Mar 2026) |

## What Stays the Same

- PostgreSQL 16/17 wire protocol and SQL syntax
- `pg_stat_statements`, `pg_stat_activity`, `pg_locks` views
- `VACUUM`, `ANALYZE`, `REINDEX` commands
- Row-level security policies
- Foreign keys, constraints, triggers
- `psql`, `pgAdmin`, and other PG tools (via OAuth credential)

## What's New

### Branching (No Traditional Equivalent)

Branches are instant database copies using copy-on-write. Use them for:
- **Testing migrations** without touching production
- **Per-PR environments** in CI/CD pipelines
- **Developer sandboxes** with real production data
- **Point-in-time snapshots** for debugging

### Scale-to-Zero

Non-production branches can scale to zero compute when idle. This eliminates the cost of always-on dev/staging databases.

### Unity Catalog Integration

Lakebase databases can be registered as UC catalogs, enabling:
- Federated queries across Lakebase + Delta Lake
- Centralized access control and audit logging
- Column-level masking and row-level filtering via UC

### Lakehouse Sync (CDC)

Continuous CDC replication from Lakebase to Delta Lake tables with SCD Type 2 history. Replaces custom ETL pipelines for OLTP-to-OLAP data movement.

## Migration Path

There is no in-place migration between self-managed PG and Lakebase. Use:

```bash
# Export from source
pg_dump --no-owner --no-acl -Fc source_db > dump.custom

# Import to Lakebase (connect via OAuth credential)
pg_restore --no-owner --no-acl -d databricks_postgres dump.custom
```

## Operational Runbook Mapping

| Alert/Issue | Traditional Fix | Lakebase Fix |
|-------------|----------------|--------------|
| High CPU | Scale up VM, tune queries | Autoscaling handles it (up to 32 CU) |
| High memory | Add RAM, tune shared_buffers | Autoscaling; 2 GB per CU |
| Disk full | Add storage, archive data | 8 TB per branch; use archival agent |
| Replication lag | Tune WAL settings | Monitor via `pg_stat_replication`; HA auto-failover |
| Too many connections | Tune `max_connections` | Scales with CU (up to 4000 at 24+ CU) |
| Dead tuples | Manual VACUUM | Autovacuum + self-healing agent |
| Lock contention | Kill sessions, fix queries | Same + automated idle connection termination |

## Automation via lakebase-ops-platform

This platform automates the DBA tasks listed above:

- **HealthAgent**: Monitors 8 metrics with warning/critical thresholds
- **PerformanceAgent**: Index recommendations, vacuum scheduling, query analysis
- **ProvisioningAgent**: Branch lifecycle, schema migrations, governance
- **Alerting**: Slack, PagerDuty, email integration
- **Self-healing**: Auto-vacuum, idle connection termination
