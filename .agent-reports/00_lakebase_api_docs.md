# Databricks Lakebase API Reference

> Comprehensive reference extracted from official Databricks documentation. Last updated: April 2026.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Resource Hierarchy](#architecture--resource-hierarchy)
3. [Autoscaling vs Provisioned Tiers](#autoscaling-vs-provisioned-tiers)
4. [REST API Endpoints (Platform Management)](#rest-api-endpoints-platform-management)
5. [Data API (PostgREST)](#data-api-postgrest)
6. [SDK Support](#sdk-support)
7. [Authentication & Authorization](#authentication--authorization)
8. [Connection Management](#connection-management)
9. [Autoscaling Configuration](#autoscaling-configuration)
10. [Branching & Instant Restore](#branching--instant-restore)
11. [Data Integration (Synced Tables & Lakehouse Sync)](#data-integration-synced-tables--lakehouse-sync)
12. [Monitoring & Metrics](#monitoring--metrics)
13. [Project Limits & Quotas](#project-limits--quotas)
14. [Regional Availability](#regional-availability)
15. [New Features in 2026](#new-features-in-2026)
16. [Limitations & Known Issues](#limitations--known-issues)
17. [Sources](#sources)

---

## Overview

Lakebase Postgres is a fully managed, cloud-native PostgreSQL database that brings OLTP capabilities to the Databricks Lakehouse. It supports PostgreSQL versions 16 and 17.

**Two API surfaces exist:**

| API Type | Purpose | Base Path |
|----------|---------|-----------|
| **Platform Management API** | Manage projects, branches, computes, roles | `/api/2.0/postgres/` |
| **Data API (PostgREST)** | CRUD operations on database tables via HTTP | Per-endpoint URL + `/public` |

**GA Timeline:**
- Public Preview: Data + AI Summit 2025
- General Availability: January 22, 2026
- Autoscaling as default: March 12, 2026

---

## Architecture & Resource Hierarchy

```
Databricks Workspace
└── Project (top-level container, up to 1,000 per workspace)
    ├── Tags (key-value for cost attribution)
    ├── Budget Policy
    └── Branch (up to 500 per project)
        ├── Compute - Primary (read-write, 1 per branch)
        ├── Compute - Read Replicas (read-only, up to 6 per branch)
        ├── Roles (up to 500 per branch)
        ├── Databases (up to 500 per branch)
        │   └── Schemas
        └── Data API endpoint
```

**Key architectural principles:**
- **Separated compute and storage**: Scale independently for cost efficiency
- **Copy-on-write storage**: Branches share storage; you pay only for changed data
- **Project-based organization**: Each project maps to a single application or workload

---

## Autoscaling vs Provisioned Tiers

| Feature | Autoscaling (Current Default) | Provisioned (Legacy) |
|---------|-------------------------------|----------------------|
| **Status** | GA (default since Mar 12, 2026) | Supported, no new development |
| **Compute scaling** | Automatic (0.5-32 CU) | Manual |
| **RAM per CU** | 2 GB | 16 GB |
| **Scale-to-zero** | Yes | No |
| **Branching** | Yes (copy-on-write) | No |
| **Instant restore** | Yes (0-30 day window) | Point-in-time restore only |
| **Read replicas** | Yes (shared storage) | Yes (readable secondaries) |
| **High availability** | Yes (auto-failover across AZs) | Yes |
| **Data API** | Yes (PostgREST) | No |
| **Budget policies & tags** | Yes | No |
| **Max compute** | 112 CU (fixed), 32 CU (autoscaling) | Varies |
| **Storage limit** | 8 TB per branch | Varies |
| **Migration path** | N/A | pg_dump / pg_restore (no direct migration) |

---

## REST API Endpoints (Platform Management)

**Base path:** `/api/2.0/postgres/`

### Projects

| Operation | Method | Path |
|-----------|--------|------|
| Create project | `POST` | `/projects` |
| Get project | `GET` | `/projects/{project_id}` |
| List projects | `GET` | `/projects` |
| Update project | `PATCH` | `/projects/{project_id}` |
| Delete project | `DELETE` | `/projects/{project_id}` |

### Branches

| Operation | Method | Path |
|-----------|--------|------|
| Create branch | `POST` | `/projects/{project_id}/branches` |
| Get branch | `GET` | `/projects/{project_id}/branches/{branch_id}` |
| List branches | `GET` | `/projects/{project_id}/branches` |
| Update branch | `PATCH` | `/projects/{project_id}/branches/{branch_id}` |
| Delete branch | `DELETE` | `/projects/{project_id}/branches/{branch_id}` |

### Endpoints (Computes / Read Replicas)

| Operation | Method | Path |
|-----------|--------|------|
| Create endpoint | `POST` | `/projects/{project_id}/branches/{branch_id}/endpoints` |
| Get endpoint | `GET` | `/projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}` |
| List endpoints | `GET` | `/projects/{project_id}/branches/{branch_id}/endpoints` |
| Update endpoint | `PATCH` | `/projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}` |
| Delete endpoint | `DELETE` | `/projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}` |

### Roles

| Operation | Method | Path |
|-----------|--------|------|
| Create role | `POST` | `/projects/{project_id}/branches/{branch_id}/roles` |
| Get role | `GET` | `/projects/{project_id}/branches/{branch_id}/roles/{role_id}` |
| List roles | `GET` | `/projects/{project_id}/branches/{branch_id}/roles` |
| Update role | `PATCH` | `/projects/{project_id}/branches/{branch_id}/roles/{role_id}` |
| Delete role | `DELETE` | `/projects/{project_id}/branches/{branch_id}/roles/{role_id}` |

### Catalogs (Unity Catalog Registration)

| Operation | Method | Path |
|-----------|--------|------|
| Register catalog | `POST` | `/catalogs` |
| Get catalog status | `GET` | `/catalogs/{catalog_id}` |
| Delete registration | `DELETE` | `/catalogs/{catalog_id}` |

### Synced Tables

| Operation | Method | Path |
|-----------|--------|------|
| Create synced table | `POST` | `/synced_tables` |
| Get synced table status | `GET` | `/synced_tables/{table_name}` |
| Delete synced table | `DELETE` | `/synced_tables/{table_name}` |

### Database Credentials

| Operation | Method | Path |
|-----------|--------|------|
| Generate credential | `POST` | `/credentials` |

### Operations (Long-Running)

| Operation | Method | Path |
|-----------|--------|------|
| Get operation status | `GET` | `/projects/{project_id}/operations/{operation_id}` |

### Permissions

| Operation | Method | Path |
|-----------|--------|------|
| Get permissions | `GET` | `/api/2.0/permissions/database-projects/{project_id}` |
| Update permissions | `PATCH` | `/api/2.0/permissions/database-projects/{project_id}` |
| Replace permissions | `PUT` | `/api/2.0/permissions/database-projects/{project_id}` |

### Long-Running Operation Response Format

```json
{
  "name": "projects/{project_id}/operations/{operation_id}",
  "done": false,
  "response": {
    "@type": "type.googleapis.com/databricks.postgres.v1.<ResourceType>"
  },
  "error": {}
}
```

**Key patterns:**
- Poll `GET /operations/{operation_id}` until `done: true`
- PATCH operations require update masks (e.g., `spec.display_name`)
- Resource IDs: 1-63 chars, lowercase letters/digits/hyphens only
- 409 Conflict: Retry with exponential backoff

---

## Data API (PostgREST)

The Data API is a PostgREST-compatible RESTful interface that auto-generates endpoints from your database schema. Available only for Lakebase Autoscaling.

### CRUD Operations

| Operation | HTTP Method | Example |
|-----------|-------------|---------|
| Read records | `GET` | `GET /public/table_name` |
| Create records | `POST` | `POST /public/table_name` (JSON body) |
| Update records | `PATCH` | `PATCH /public/table_name?id=eq.1` (JSON body) |
| Replace records | `PUT` | `PUT /public/table_name?id=eq.1` (JSON body) |
| Delete records | `DELETE` | `DELETE /public/table_name?status=eq.archived` |

### Query Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `select` | Column selection & joins | `?select=id,name,projects(id,name)` |
| `order` | Sort results | `?order=due_date.desc` |
| `limit` | Limit results | `?limit=10` |
| `offset` | Pagination offset | `?offset=20` |

### Filter Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `eq` | Equals | `?status=eq.active` |
| `neq` | Not equal | `?status=neq.archived` |
| `gt` / `gte` | Greater than (or equal) | `?price=gte.100` |
| `lt` / `lte` | Less than (or equal) | `?price=lt.50` |
| `like` | Pattern match | `?name=like.*smith*` |
| `in` | In list | `?id=in.(1,2,3)` |

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| Exposed schemas | Which schemas are accessible | `public` |
| Maximum rows | Hard limit on response size | None (unlimited) |
| CORS origins | Allowed origins for cross-origin requests | Empty (all allowed) |
| OpenAPI spec | Auto-generated at `/openapi.json` | Enabled |
| Server timing headers | Request processing breakdown | Configurable |

### Row-Level Security (RLS)

RLS policies enforce fine-grained access control. When RLS is enabled, all rows become inaccessible by default until policies grant access.

```sql
-- Example: User can only see their own records
CREATE POLICY user_policy ON orders USING (assigned_to = current_user);
```

Common patterns: user ownership, tenant isolation, team membership, read-only restrictions.

### PostgREST Limitations

**Unsupported features:**
- Computed relationships
- Inner join embedding
- Custom media type handlers
- Stripped nulls
- Planned/estimated count preferences
- Transaction control via headers
- Query plan exposure

**Partially supported:**
- PostGIS geometry columns (no auto GeoJSON formatting)

### Setup Requirements

1. Create the `databricks_auth` extension
2. Register Postgres roles for Databricks identities
3. Grant schema and table permissions
4. Implement RLS policies for production use

**Important:** Database owners cannot access the Data API due to permission escalation restrictions.

---

## SDK Support

### Python SDK

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(
    host=os.environ["DATABRICKS_HOST"],
    client_id=os.environ["DATABRICKS_CLIENT_ID"],
    client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
)

# Create a project (long-running operation)
op = w.postgres.create_project(...)
result = op.wait()

# Generate database credential
cred = w.postgres.generate_database_credential(endpoint=endpoint_name)

# Create a role
w.postgres.create_role(parent=branch_path, role=Role(spec=RoleRoleSpec(...)))
```

### Java SDK

```java
WorkspaceClient w = new WorkspaceClient(...);
DatabaseCredential cred = w.postgres().generateDatabaseCredential(
    new GenerateDatabaseCredentialRequest().setEndpoint(endpointName)
);
```

### Go SDK

```go
credential, err := w.Postgres.GenerateDatabaseCredential(ctx,
    postgres.GenerateDatabaseCredentialRequest{
        Endpoint: os.Getenv("ENDPOINT_NAME"),
    })
```

### Databricks CLI

```bash
# Browser-based OAuth login
databricks auth login --host <workspace-url>

# List projects
databricks postgres projects list

# Create project
databricks postgres projects create --json '{...}'
```

### Terraform

Lakebase resources can be managed via the Databricks Terraform provider (Beta).

### Asset Bundles

Lakebase infrastructure can be defined as code using Databricks Asset Bundles (Beta).

---

## Authentication & Authorization

### Platform API Authentication

- **Method:** Workspace-level OAuth
- **Token location:** `~/.databricks/token-cache.json`
- **Token lifetime:** 60 minutes
- **SDKs:** Handle authentication automatically via unified auth system

### Database Connection Authentication

Two-step token exchange for external applications:

1. **Step 1 - Get workspace OAuth token:**
   ```
   POST ${DATABRICKS_HOST}/oidc/v1/token
   Authorization: Basic <base64(client_id:client_secret)>
   Body: grant_type=client_credentials&scope=all-apis
   ```

2. **Step 2 - Get database credential:**
   ```
   POST ${DATABRICKS_HOST}/api/2.0/postgres/credentials
   Authorization: Bearer <oauth_token>
   Body: { "endpoint": "projects/<id>/branches/<id>/endpoints/<id>" }
   ```

### Token Lifetimes

| Token Type | Lifetime |
|------------|----------|
| Service Principal secret | Up to 730 days |
| Workspace OAuth token | 60 minutes |
| Database credential | 60 minutes |

### Authorization Model

- Workspace ACLs control project-level access
- Postgres roles control database-level access
- OAuth roles can be created via UI, REST API, or SQL (as of Mar 2026)
- `databricks_create_role('{client-id}', 'SERVICE_PRINCIPAL')` creates SP-linked roles
- Required grants: CONNECT, USAGE, SELECT/INSERT/UPDATE/DELETE as needed

---

## Connection Management

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_CLIENT_ID` | Service principal client ID |
| `DATABRICKS_CLIENT_SECRET` | Service principal secret |
| `ENDPOINT_NAME` | Format: `projects/<id>/branches/<id>/endpoints/<id>` |
| `PGHOST` | PostgreSQL host |
| `PGDATABASE` | Database name (default: `databricks_postgres`) |
| `PGUSER` | PostgreSQL user |
| `PGPORT` | Port (default: 5432) |

### Connection Patterns

- **Single connection:** Simple scripts, generate credential per connection
- **Connection pool:** Production workloads, use custom connect class that generates fresh OAuth tokens per connection
- **HikariCP (Java):** Set max lifetime to 45 minutes (recycle before 60-min token expiry)
- **pgxpool (Go):** BeforeConnect callback for token refresh

### Connection Limits by Compute Size

| Compute Size (CU) | Max Connections |
|--------------------|-----------------|
| 0.5 | 104 |
| 1-23 | Scales proportionally |
| 24+ | 4,000 |

---

## Autoscaling Configuration

### Compute Sizes

**Autoscaling range (dynamic):**
- Minimum: 0.5 CU
- Maximum: 32 CU
- Available increments: 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 24, 28, 32
- Constraint: `max - min <= 16 CU`
- Each CU = 2 GB RAM

**Fixed-size computes (no autoscaling):**
- Range: 36 to 112 CU
- Available sizes: 36, 40, 44, 48, 52, 56, 60, 64, 72, 80, 88, 96, 104, 112

### Default Compute Settings (New Projects)

| Setting | Default |
|---------|---------|
| Autoscaling range | 2-4 CU |
| Scale-to-zero | Enabled (5-min timeout) |
| High Availability | Disabled |

### Scaling Metrics

Three metrics drive autoscaling decisions:
1. **CPU load** - Processor utilization
2. **Memory usage** - RAM consumption
3. **Working set size** - Frequently accessed data pages

Scaling adjustments occur without compute restarts or connection interruptions. Changing min/max configuration may cause brief interruptions.

### Scale-to-Zero

- Compute suspends entirely after inactivity timeout
- Minimum timeout: 60 seconds
- Default timeout: 5 minutes
- Production branch computes have scale-to-zero disabled by default
- **Not available** with high availability configurations
- Secondaries cannot scale below primary's current CU in HA setups

---

## Branching & Instant Restore

### Branch Model

- Analogous to Git branching for databases
- Default `production` branch created automatically
- Parent-child hierarchy: changes in child do not affect parent and vice versa
- Copy-on-write: instant creation regardless of database size

### Branch Types

| Type | Properties |
|------|------------|
| **Default branch** | Exempt from concurrent compute limits; always available |
| **Protected branch** | Cannot be deleted or reset; blocks project deletion; exempt from auto-archival |
| **Regular branch** | Standard lifecycle; subject to archival |

### Branch Operations

- **Create:** Instant, inherits schema + data from parent via copy-on-write
- **Reset:** Synchronize child branch with parent's current state
- **Point-in-time restore:** Create branch from any moment in restore window (0-30 days)
- **Delete:** Remove branch and its data

### Organizational Patterns

- **Simple:** production + development
- **Staged:** production -> staging -> development
- **Per-developer:** production -> dev-alice, dev-bob, etc.

### Limits

- Max 500 branches per project
- Max 10 unarchived branches
- Max 3 root branches
- Max 1 protected branch
- Restore window: 2-30 days (configurable)

---

## Data Integration (Synced Tables & Lakehouse Sync)

### Synced Tables (Lakehouse -> Lakebase)

Move lakehouse Delta table data into Lakebase for low-latency OLTP queries.

**API:**
- `POST /api/2.0/postgres/synced_tables` - Create
- `GET /api/2.0/postgres/synced_tables/{table_name}` - Get status
- `DELETE /api/2.0/postgres/synced_tables/{table_name}` - Delete

### Lakehouse Sync (Lakebase -> Lakehouse) [Beta - AWS]

Continuous, low-latency CDC replication of Lakebase Postgres tables into Unity Catalog managed Delta tables.

- Uses Change Data Capture (CDC)
- Writes as SCD Type 2 history
- Announced March 12, 2026

### Unity Catalog Registration

Register Lakebase databases as catalogs in Unity Catalog for federated queries.

**API:**
- `POST /api/2.0/postgres/catalogs` - Register
- `GET /api/2.0/postgres/catalogs/{catalog_id}` - Get status
- `DELETE /api/2.0/postgres/catalogs/{catalog_id}` - Delete

---

## Monitoring & Metrics

### Available Metrics (Dashboard)

| Metric | Description |
|--------|-------------|
| **RAM** | Allocated, used, and cached memory over time |
| **CPU** | Allocated and used CPU in Compute Units |
| **Connections Count** | Active, idle, total, and maximum connections |
| **Database Size** | Logical data size (tables + indexes); active compute only |
| **Deadlocks** | Deadlock occurrences over time |
| **Rows** | Inserted, updated, and deleted row operations (excludes TRUNCATE) |
| **Replication Delay (Bytes)** | Data backlog not yet applied to replicas |
| **Replication Delay (Seconds)** | Time lag between primary and replica |
| **Local File Cache Hit Rate** | % reads from cache; target 99%+ for OLTP |
| **Working Set Size** | Distinct Postgres pages accessed at 5m, 15m, 1h intervals |

### Time Periods

- Predefined: Last hour, Last day, Last 7 days
- Custom: Last 3/6/12 hours, Last 2 days, or custom ranges

### Access

Metrics dashboard is accessible from the Lakebase App sidebar. No programmatic API access to metrics is documented at this time.

---

## Project Limits & Quotas

| Resource | Limit |
|----------|-------|
| Projects per workspace | 1,000 |
| Branches per project | 500 |
| Unarchived branches | 10 |
| Root branches | 3 |
| Protected branches | 1 |
| Concurrently active computes | 20 |
| Read replicas per branch | 6 |
| Postgres roles per branch | 500 |
| Postgres databases per branch | 500 |
| Logical data size per branch | 8 TB |
| Manual snapshots | 10 |
| History retention period | 30 days max |
| Scale-to-zero minimum time | 60 seconds |
| Autoscaling max CU | 32 CU |
| Fixed-size max CU | 112 CU |
| Autoscaling range constraint | max - min <= 16 CU |
| Max connections (24+ CU) | 4,000 |

---

## Regional Availability

### AWS Regions (Lakebase Autoscaling)

| Region Code | Location |
|-------------|----------|
| `us-east-1` | N. Virginia |
| `us-east-2` | Ohio |
| `us-west-2` | Oregon |
| `ca-central-1` | Canada Central (added Mar 2026) |
| `sa-east-1` | Sao Paulo (added Mar 2026) |
| `eu-central-1` | Frankfurt |
| `eu-west-1` | Ireland |
| `eu-west-2` | London (added Mar 2026) |
| `ap-south-1` | Mumbai |
| `ap-southeast-1` | Singapore |
| `ap-southeast-2` | Sydney |

### Azure Regions

Lakebase is also GA on Azure Databricks. See Azure documentation for region list.

---

## New Features in 2026

### January 2026

| Date | Feature | Status |
|------|---------|--------|
| Jan 15 | Unified Lakebase interface (Provisioned + Autoscaling in one UI) | GA |
| Jan 22 | **Lakebase GA** - autoscaling, scale-to-zero, branching, backups, PITR, 8TB storage | GA |

### March 2026

| Date | Feature | Status |
|------|---------|--------|
| Mar 2 | High availability with automatic failover across AZs | GA |
| Mar 2 | Three additional regions (ca-central-1, eu-west-2, sa-east-1) | GA |
| Mar 4 | Compliance security profile support (HIPAA, C5, TISAX) | GA |
| Mar 12 | OAuth role management via UI/REST API (not just SQL) | GA |
| Mar 12 | Budget policies and custom tags for cost attribution | GA |
| Mar 12 | Lakehouse Sync (CDC replication to Delta tables) | Beta |
| Mar 12 | Autoscaling projects as default for new instances | GA |
| Mar 16 | Lakebase as Databricks Apps resource | GA |

### Preview / Beta Features (Current)

| Feature | Status | Notes |
|---------|--------|-------|
| Lakehouse Sync | Beta (AWS) | CDC-based replication to Unity Catalog Delta tables |
| Infrastructure as Code (Asset Bundles, Terraform) | Beta | Define Lakebase resources declaratively |
| REST API, CLI, SDKs | Beta | Platform management API surface |
| Data API (PostgREST) | GA | CRUD via HTTP |

---

## Limitations & Known Issues

### Migration

- No direct migration path between Provisioned and Autoscaling
- Must use `pg_dump` and `pg_restore` for data transfer

### Compliance

- Only supports HIPAA, C5, TISAX, or None compliance profiles
- Other compliance standards are not supported

### Autoscaling

- Scale-to-zero unavailable with high availability enabled
- Secondaries cannot scale below primary's current CU in HA setups
- Autoscaling capped at 32 CU; larger workloads must use fixed-size computes

### Data API (PostgREST)

- Database owners cannot access the Data API (permission escalation restriction)
- No computed relationships, inner join embedding, or transaction control via headers
- Schema cache refresh required after database changes
- PostGIS geometry columns do not auto-format as GeoJSON

### General

- Compute names are read-only and cannot be renamed
- Branches cannot have multiple read-write computes
- Changing min/max autoscaling configuration may cause brief interruptions
- 409 Conflict errors require retry with exponential backoff

---

## Sources

- [Lakebase Postgres Overview](https://docs.databricks.com/aws/en/oltp/)
- [What is Lakebase Autoscaling?](https://docs.databricks.com/aws/en/oltp/projects/about)
- [Lakebase Autoscaling API Guide](https://docs.databricks.com/aws/en/oltp/projects/api-usage)
- [Lakebase Data API](https://docs.databricks.com/aws/en/oltp/projects/data-api)
- [Autoscaling Configuration](https://docs.databricks.com/aws/en/oltp/projects/autoscaling)
- [Manage Projects](https://docs.databricks.com/aws/en/oltp/projects/manage-projects)
- [Manage Computes](https://docs.databricks.com/aws/en/oltp/projects/manage-computes)
- [Branches](https://docs.databricks.com/aws/en/oltp/projects/branches)
- [Metrics Dashboard](https://docs.databricks.com/aws/en/oltp/projects/metrics)
- [Lakebase Autoscaling Limitations](https://docs.databricks.com/aws/en/oltp/projects/limitations)
- [Connect External App (API)](https://docs.databricks.com/aws/en/oltp/projects/external-apps-manual-api)
- [Connect External App (SDK)](https://docs.databricks.com/aws/en/oltp/projects/external-apps-connect)
- [Lakebase Provisioned](https://docs.databricks.com/aws/en/oltp/instances/)
- [March 2026 Release Notes (AWS)](https://docs.databricks.com/aws/en/release-notes/product/2026/march)
- [January 2026 Release Notes (AWS)](https://docs.databricks.com/aws/en/release-notes/product/2026/january)
- [Azure Databricks Lakebase GA Blog](https://www.databricks.com/blog/azure-databricks-lakebase-generally-available)
- [FabCon 2026 Blog](https://www.databricks.com/blog/whats-new-azure-databricks-fabcon-2026-lakebase-lakeflow-and-genie)
- [Databricks REST API Reference](https://docs.databricks.com/api/workspace/introduction)
