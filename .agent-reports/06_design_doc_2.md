# Design Document Analysis: Enterprise Lakebase Design Guide

**Source:** `.agent-reports/raw_design_doc_2.txt`
**Full Title:** Enterprise Lakebase Design Guide: Naming Standards, Branching Best Practices & Governance Framework inspired by Unity Catalog
**Authors:** Jonathan Katz, Surya S Turaga, Uday Satapathy, Ryan DeCosmo
**Analyzed:** 2026-04-05
**Document Structure:** 5 major parts, 28+ reference tables, 8 reviewer comment threads

---

## 1. Document Overview

This is a comprehensive enterprise design guide covering two interrelated systems -- Unity Catalog (analytical/OLAP layer) and Lakebase Autoscaling (OLTP/PostgreSQL layer) -- with a unified governance framework bridging them. The document provides prescriptive naming standards, branching workflows, access control patterns, cost optimization strategies, and CI/CD automation templates.

**Parts:**
1. Unity Catalog Design Considerations (Sections 1.1-1.6)
2. Lakebase Branching Design for Enterprise (Sections 2.1-2.7)
3. Unified Governance Framework (Sections 3.1-3.4)
4. Neon-Inspired Patterns for Lakebase (Sections 4.1-4.3)
5. Quick Reference (Sections 5.1-5.4)

---

## 2. Unity Catalog Three-Level Namespace Architecture

### Hierarchy

| Level | Purpose | Typical Mapping |
|-------|---------|-----------------|
| Metastore | Regional container (one per cloud region) | Cloud region (us-east-1, eu-west-1) |
| Catalog | Primary isolation unit | Environment, domain, business unit, or hybrid |
| Schema | Logical grouping within catalog | Data layer, functional area, data product |
| Table/View | Individual data asset | Business entity or analytical artifact |

### Addressing Format

```
catalog.schema.table_or_view
```

### Reviewer Commentary (Comment [a])

Jonathan Katz notes this hierarchy may change in a "near-to-middle-state" leveraging a proposed UC "folders" hierarchy, which could enable full automation. He suggests refocusing this section on naming core objects within a Lakebase Project (Postgres database, schema, table) rather than the UC namespace itself. This indicates the UC namespace architecture is in flux and the platform should be designed for extensibility.

---

## 3. Catalog Naming Conventions

### Pattern 1: Environment-Based Catalogs

Best for organizations with strict SDLC separation requirements.

Format: `env_domain` or `env_domain_qualifier`

| Catalog Name | Purpose |
|-------------|---------|
| `dev_finance` | Development environment for finance domain |
| `staging_finance` | Pre-production validation |
| `prod_finance` | Production finance data |

Additional examples: `dev_sales`, `staging_hr_sensitive`, `prod_marketing`

### Pattern 2: Domain-Based Catalogs (Data Mesh)

Best for decentralized data ownership and data mesh architectures.

Format: `domain` or `domain_qualifier`

| Catalog Name | Owner | Purpose |
|-------------|-------|---------|
| `finance` | Finance Data Team | All finance data assets |
| `supply_chain` | Supply Chain Team | Operational and analytical data |
| `clinical_trials` | Clinical Ops | Trial data and analytics |

### Pattern 3: Hybrid (Environment + Domain) -- Most Common

The most common enterprise pattern combining both approaches.

Format: `env_domain_optional_suffix`

| Catalog Name | Environment | Domain |
|-------------|-------------|--------|
| `prod_finance` | Production | Finance |
| `dev_finance` | Development | Finance |
| `prod_supply_chain` | Production | Supply Chain |
| `sandbox_analytics` | Sandbox | Cross-domain analytics |

### Catalog Naming Rules (8 rules)

1. Use lowercase with underscores as separators
2. Keep names under 30 characters
3. Avoid special characters except underscores
4. Start with environment prefix (`dev_`, `stg_`, `prod_`) OR domain name
5. Avoid generic names (`data`, `catalog1`, `test`)
6. Assign ownership to groups, not individuals
7. Document purpose using tags and comments
8. (Implicit) Use consistent naming across environments for the same domain

---

## 4. Schema Naming Patterns

### Medallion Architecture Schemas (Most Widely Adopted)

| Schema | Purpose | Example Tables |
|--------|---------|----------------|
| `bronze` | Raw/landing zone data | `customer_raw`, `orders_raw` |
| `silver` | Cleansed and enriched data | `customer_cleaned`, `orders_enriched` |
| `gold` | Business-ready reporting layer | `dim_customer`, `fact_sales` |
| `staging` | Intermediate processing | `stg_customer_transform` |
| `reference` | Reference/lookup tables | `ref_country_codes`, `ref_icd10` |

### Functional Schemas

| Schema | Purpose |
|--------|---------|
| `data_vault` | Hub, satellite, and link tables |
| `mart` | Business-specific data marts |
| `ml_features` | Feature store tables |
| `audit` | Audit and compliance tables |
| `scratch` | Temporary exploration space |

### Data Product Schemas

Format: `dp_productname` or `product_domain`

| Schema | Published By | Consumers |
|--------|-------------|-----------|
| `dp_customer_360` | Customer Analytics | Marketing, Sales, Support |
| `dp_revenue_metrics` | Finance | Executive, Sales |
| `dp_clinical_outcomes` | Clinical Ops | R&D, Regulatory |

### Table and View Naming Conventions

**General Rules:**
- Use `lower_snake_case` for all table and view names
- Prefix with the table type for analytical models
- Include SCD type suffix for dimension tables with history

**Reviewer Note (Comment [b]):** Jonathan Katz clarifies these conventions are for OLAP/analytical tables. Postgres (OLTP) tables are typically named after the objects they represent since they are normalized to them.

**12 Naming Patterns by Type:**

| Type | Prefix/Suffix | Example |
|------|---------------|---------|
| Dimension table | `dim_` | `dim_customer`, `dim_product` |
| Fact table | `fact_` | `fact_sales_orders`, `fact_claims` |
| Slowly Changing Dimension | `_scd2` | `dim_customer_scd2` |
| Hub table (Data Vault) | `hub_` | `hub_customer`, `hub_provider` |
| Satellite table | `sat_` | `sat_customer_profile` |
| Link table | `link_` | `link_order_customer` |
| Staging table | `stg_` | `stg_customer_transform` |
| View (curated) | `vw_` | `vw_active_customers` |
| Materialized view | `mv_` | `mv_daily_revenue` |
| Streaming table | `st_` | `st_iot_events` |
| Raw/landing table | `_raw` | `customer_raw`, `claims_raw` |

### Volume Naming

| Type | Convention | Example |
|------|-----------|---------|
| Managed volume | `vol_purpose` | `vol_raw_files`, `vol_exports` |
| External volume | `ext_vol_source` | `ext_vol_sftp_landing` |
| Model artifacts | `vol_ml_artifacts` | `vol_ml_artifacts` |

---

## 5. Multi-Catalog Strategy Decision Framework

### When to Use Separate Catalogs

| Scenario | Recommendation |
|----------|---------------|
| Different environments (dev/staging/prod) | Separate catalogs per environment |
| Different business domains with distinct governance | Separate catalogs per domain |
| Regulatory isolation requirements (HIPAA, PCI) | Separate catalogs for sensitive data |
| Cross-team shared data products | Dedicated catalog for published products |
| Sandbox/exploration work | Dedicated sandbox catalog per team |

### When to Use Schemas Within a Single Catalog

| Scenario | Recommendation |
|----------|---------------|
| Single team with multiple data layers | Multiple schemas (bronze/silver/gold) |
| Closely related data products from same team | Schema per product within domain catalog |
| Small organization with limited data assets | Single catalog, multiple schemas |

### Enterprise Reference Architecture (7 Catalogs)

| Catalog | Purpose | Access Pattern |
|---------|---------|----------------|
| `prod_core` | Production core business data | Read: analysts, data scientists. Write: pipelines only |
| `prod_analytics` | Production analytics and BI | Read: business users. Write: analytics team |
| `prod_ml` | Production ML features and models | Read: serving endpoints. Write: ML engineers |
| `dev_core` | Development environment | Read/Write: developers |
| `stg_core` | Staging/UAT environment | Read: QA. Write: CI/CD pipelines |
| `sandbox_team_name` | Team exploration space | Read/Write: specific team |
| `shared_reference` | Cross-domain reference data | Read: all. Write: data stewards |

---

## 6. Lakebase Branching Best Practices

### 6.1 Foundation -- Neon Architecture Principles

Databricks acquired Neon in May 2025. Key architectural principles inherited:

| Principle | Description |
|-----------|-------------|
| Copy-on-Write (CoW) | Branches share base storage; only modified pages stored separately |
| Instant creation | O(1) metadata operation regardless of database size |
| Zero impact on parent | Branch creation does not affect parent performance |
| Scale-to-zero | Idle branch compute suspends automatically |
| Point-in-time branching | Create from any historical timestamp within restore window |

### 6.2 Branch Hierarchy

```
production (default, protected)
  |-- staging (protected)
  |     |-- development
  |     |     |-- dev/alice (TTL: 7d)
  |     |     |-- dev/bob (TTL: 7d)
  |     |     |-- ci/pr-142 (TTL: 4h)
  |     |     |-- ci/pr-155 (TTL: 4h)
  |     |-- qa/release-3.2 (TTL: 14d)
  |-- hotfix/critical-fix (TTL: 24h)
```

### 6.3 Branch Types

| Type | Behavior | Use Case |
|------|----------|----------|
| Default Branch | Always-on, cannot be deleted, exempt from compute limits | Production workloads |
| Protected Branch | Cannot be deleted, reset, or auto-archived | Staging, critical environments |
| Ephemeral Branch | Has TTL (max 30 days), auto-deletes on expiry | CI/CD, feature development |
| Point-in-Time Branch | Created from historical timestamp (0-30 days) | Disaster recovery, auditing |

### 6.4 Branch Naming Standards (RFC 1123)

**Technical Constraints:**
- 1 to 63 characters
- Must start with a lowercase letter
- Lowercase alphanumeric and hyphens only
- No underscores, uppercase, or special characters

**Reviewer Notes (Comments [c][d]):** Reviewer asked whether Neon docs were consulted for naming requirements. Response confirms `https://neon.com/docs/manage/branches#branch-naming-requirements` was referenced.

**11 Naming Conventions:**

| Pattern | Convention | Example | Use Case |
|---------|-----------|---------|----------|
| Production | `production` | `production` | Default branch, always protected |
| Staging | `staging` | `staging` | Pre-production validation |
| Development | `development` | `development` | Shared development branch |
| Developer | `dev-firstname` | `dev-alice`, `dev-bob` | Per-developer isolation |
| CI/CD | `ci-pr-number` | `ci-pr-142`, `ci-pr-287` | Ephemeral PR branches |
| Feature | `feat-short-desc` | `feat-add-auth`, `feat-patient-api` | Feature development |
| Hotfix | `hotfix-ticket` | `hotfix-jira-1234` | Emergency production fixes |
| QA/Release | `qa-release-version` | `qa-release-3-2` | Release validation |
| Load Test | `perf-test-name` | `perf-baseline-feb` | Performance testing |
| Audit | `audit-date` | `audit-2026-02-21` | Point-in-time audit snapshots |
| Demo | `demo-customer` | `demo-acme-corp` | Customer-specific demos |

**Decision Tree (8 steps):**

1. Is this the main database? -> `production` (protected)
2. Is this for pre-prod validation? -> `staging` (protected)
3. Is this for a specific developer? -> `dev-firstname`
4. Is this for a pull request? -> `ci-pr-number` (TTL: 2-4 hours)
5. Is this for a feature? -> `feat-short-desc` (TTL: 7 days)
6. Is this for a hotfix? -> `hotfix-ticket-id` (TTL: 24 hours)
7. Is this for a release? -> `qa-release-version` (TTL: 14 days)
8. Is this for performance testing? -> `perf-test-name` (TTL: 48 hours)

### 6.5 TTL Policies

| Branch Type | Recommended TTL | Rationale |
|-------------|----------------|-----------|
| CI/CD (per-PR) | 2-4 hours | Tests complete within minutes; auto-cleanup |
| Hotfix | 24 hours | Urgent fixes applied quickly |
| Performance test | 48 hours | Load tests + analysis window |
| Feature development | 7 days | Sprint-length development cycles |
| Demo | 7-14 days | Customer demo + follow-up window |
| QA/Release | 14 days | Release validation + regression testing |
| Developer (personal) | 7 days | Reset weekly from development branch |
| Audit snapshot | 30 days | Maximum TTL for compliance review |
| Staging | No TTL (protected) | Long-lived, reset from production regularly |
| Production | No TTL (protected) | Default branch, never expires |

### 6.6 Current Limitations

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| No merge capability | Cannot auto-merge branch changes to parent | Replay idempotent DDL on parent |
| No schema-only branches | All branches include data | Use RLS to restrict data access |
| Max 10 unarchived branches | Branch sprawl management required | Use TTLs and CI/CD automation |
| No CI/CD PR comment integration | Schema diff is UI-only | Build custom GitHub Action wrapper |
| Branch naming: RFC 1123 | 1-63 chars, lowercase, starts with letter | Plan naming conventions carefully |
| Max-min autoscale range <= 8 CU | Limited autoscaling flexibility | Right-size for expected workload |

### 6.7 "Git-like Branching" Debate (Comments [e]-[h])

This is a significant unresolved debate within the document:

- **Chris (Comment [e]):** Questions whether the phrase "Git-like branching" should be dropped given there is no merge capability. Every developer and customer assumes merge exists when they hear "Git-like." He suggests alternatives like "CoW Replicas" or "Shallow Clones."
- **Author Response (Comment [f]):** Defends the phrase as a resonant analogy for meetings, especially for legacy DBAs and those new to the concept. "Git-like branching" produces an immediate "light bulb moment."
- **Comment [g]:** Marked as resolved.
- **Comment [h]:** Re-opened by Chris, who reiterates that in every conversation -- both with customers and internally with other FE folks -- people assume merge is included. He worries the phrase is accidentally misleading customers.

**Platform implication:** Documentation and UI language should be precise about capabilities. Consider using "Copy-on-Write branching" or "CoW branches" in technical documentation while reserving "Git-like" for high-level analogies only.

---

## 7. Enterprise Branching Patterns (6 Patterns)

### Pattern 1: Simple Dev/Prod (Small Teams, 1-5 developers)

```
production (protected)
  |-- development
```

Two branches. Development resets from production weekly. Migrations tested on development, replayed on production.

### Pattern 2: Multi-Environment Pipeline (Medium Teams, 5-20)

```
production (protected)
  |-- staging (protected)
  |     |-- development
  |-- hotfix-ticket (ephemeral, TTL: 24h)
```

Three tiers. Staging is protected. Hotfix branches from production for urgent fixes.

### Pattern 3: Per-Developer Isolation (Large Teams, 20+)

```
production (protected)
  |-- staging (protected)
  |     |-- development
  |           |-- dev-alice (TTL: 7d)
  |           |-- dev-jordan (TTL: 7d)
  |           |-- dev-sam (TTL: 7d)
```

Each developer gets an isolated branch. Personal branches reset from development when starting new work. Schema Diff validates changes before promotion.

### Pattern 4: CI/CD Ephemeral Branches (DevOps Teams)

```
production (protected)
  |-- staging (protected)
  |     |-- ci-pr-123 (TTL: 4h)
  |     |-- ci-pr-124 (TTL: 4h)
  |     |-- ci-pr-125 (TTL: 4h)
```

Each PR gets its own database clone. TTL handles cleanup. Eliminates shared test database flakiness.

### Pattern 5: Multi-Tenant Project-Level Isolation (SaaS)

```
Project: tenant-alpha
  |-- production (protected)
  |     |-- development

Project: tenant-beta
  |-- production (protected)
  |     |-- development
```

Separate Lakebase projects per tenant. Each has own branch hierarchy, compute, and storage. UC enforces cross-tenant access control.

### Pattern 6: Multi-Tenant Schema-Level Isolation (Cost-Sensitive)

```
Project: multi-tenant-app
  |-- production (protected)
  |     |-- development

PostgreSQL Schemas:
  - tenant_alpha (with RLS policies)
  - tenant_beta (with RLS policies)
  - shared (common reference data)
```

Single project, multiple PostgreSQL schemas. Row-Level Security enforces tenant isolation. Data API enforces RLS automatically via Databricks identity.

---

## 8. Governance Framework Requirements

### 8.1 Unity Catalog Governance (7 Items)

1. Assign production catalog ownership to groups, not individuals
2. Grant USE CATALOG and USE SCHEMA only to authorized users
3. Implement row-level filtering and column masking for sensitive data
4. Use deployment scripts (Terraform, DABs) for privilege assignments
5. Audit permissions regularly using `system.access.audit`
6. Bind catalogs to specific workspaces for isolation
7. Document all catalogs and schemas with tags and comments

### 8.2 Lakebase Governance (9 Items)

1. Mark production and staging branches as protected
2. Enforce TTL policies on all non-protected branches
3. Use CI/CD automation for branch creation and deletion
4. Validate all schema changes via Schema Diff before promotion
5. Write idempotent DDL for all migrations
6. Monitor branch count (max 10 unarchived per project)
7. Use Databricks identity (OAuth) instead of password-based access
8. Enable Row-Level Security for multi-tenant applications
9. Configure the Data API with appropriate exposed schemas and CORS origins

### 8.3 Combined Cross-System Governance (5 Items)

1. Align Lakebase project names with Unity Catalog domain names
2. Use consistent environment prefixes across both systems (accounting for separator differences: `_` for UC, `-` for Lakebase)
3. Centralize access control through Unity Catalog groups
4. Track data lineage from Lakebase OLTP to Delta Lake analytics
5. Implement a single CI/CD pipeline that manages both Lakebase branches and UC permissions

---

## 9. Configuration Changes Required for the Platform

Based on cross-referencing with the existing repo architecture (`01_repo_architecture.md`):

### 9.1 Branch Naming Validation

The existing `agents/provisioning/branching.py` (BranchingMixin) must enforce:
- RFC 1123 naming constraints (1-63 chars, lowercase alphanumeric + hyphens, starts with letter)
- The 8-step naming convention decision tree
- Rejection of non-compliant names before any API call

### 9.2 TTL Policy Defaults

Embed recommended TTL policies as configurable defaults per branch type. Currently TTLs are passed ad-hoc. The platform should:
- Provide typed defaults: CI=4h, hotfix=24h, perf=48h, feature=7d, demo=14d, qa=14d, dev=7d, audit=30d
- Warn when a non-protected branch has no TTL set
- Alert when branches approach TTL expiration

### 9.3 Cross-System Naming Translation

A mapping configuration translating between UC naming and Lakebase naming:

| Rule | Unity Catalog | Lakebase Branches | Lakebase Projects |
|------|-------------|-------------------|-------------------|
| Case | lowercase | lowercase | lowercase |
| Separator | underscore (`_`) | hyphen (`-`) | hyphen (`-`) |
| Max length | 255 chars | 63 chars | 63 chars |
| Start with | letter or underscore | lowercase letter | lowercase letter |
| Environment prefix | `dev_`, `stg_`, `prod_` | `dev-`, `staging`, `production` | `domain-env` |

**Mapping example (supply_chain domain):**

| Environment | UC Catalog | Lakebase Project | Lakebase Branch |
|------------|-----------|-----------------|----------------|
| Production | `prod_supply_chain` | `supply-chain-prod` | `production` |
| Staging | `stg_supply_chain` | `supply-chain-prod` | `staging` |
| Development | `dev_supply_chain` | `supply-chain-prod` | `development` |
| Developer | `dev_supply_chain` | `supply-chain-prod` | `dev-alice` |
| CI/CD | `dev_supply_chain` | `supply-chain-prod` | `ci-pr-142` |

**Key insight:** A single Lakebase project with branches replaces what previously required separate database instances per environment, while UC catalogs continue to separate the analytical layer.

### 9.4 Multi-Catalog Strategy Support

The `agents/provisioning/governance.py` (GovernanceMixin) should support the 7-catalog Enterprise Reference Architecture: `prod_core`, `prod_analytics`, `prod_ml`, `dev_core`, `stg_core`, `sandbox_team_name`, `shared_reference`.

### 9.5 Branch Protection Configuration

Production and staging branches must be automatically marked as protected (`is_protected: true`). The platform should enforce this as policy, not leave it to user discretion.

### 9.6 Data API Configuration

New configuration needed for:
- Exposed schemas list
- CORS origins whitelist
- RLS policy enforcement settings

---

## 10. New Modules or Services to Build

### 10.1 Branch Naming Validator

A utility module validating branch names against RFC 1123 rules and the convention decision tree. Must be invoked by ProvisioningAgent before any `create-branch` call.

**Input:** proposed branch name, branch type (ci, feature, hotfix, etc.)
**Output:** valid/invalid + suggested correction if invalid

### 10.2 Naming Alignment Service

Converts between UC naming conventions and Lakebase naming conventions:
- `prod_finance` (UC) <-> `finance-prod` (Lakebase project)
- Handles separator difference (underscore vs. hyphen)
- Handles prefix ordering (env-first in UC, domain-first in Lakebase projects)

### 10.3 Schema Migration Workflow Orchestrator

A 9-step migration testing pipeline (Section 2.6):

1. Developer writes migration files locally (Flyway, Liquibase, Prisma, or plain SQL)
2. PR triggers CI/CD pipeline
3. Pipeline creates Lakebase branch from staging (`ci-pr-NNN`, TTL: 4h)
4. Migrations applied to branch
5. Schema Diff captured (Lakebase App UI or API)
6. Integration tests run against migrated branch
7. Code review includes both code changes AND schema diff
8. On merge, migrations replayed on staging, then production
9. Branch auto-deletes after TTL

The existing `agents/provisioning/migration.py` already has a 9-step testing flow but should be aligned with this specific workflow.

### 10.4 GitHub Actions Generator -- Schema Diff in PR Comments

Section 4.2 calls for a custom GitHub Action that:

1. Creates branch from staging
2. Applies migrations
3. Uses Lakebase Schema Diff API (or `pg_dump` comparison) to generate diff
4. Posts diff as a PR comment via GitHub API
5. Cleans up branch

The existing `agents/provisioning/cicd.py` generates GitHub Actions YAML but needs this specific pattern.

### 10.5 Nightly Reset Automation

A Databricks Job that resets staging from production on a nightly schedule (Section 4.2):

```python
# Schedule: 0 2 * * * (2 AM daily)
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.postgres.reset_branch(name="projects/my-project/branches/staging")
```

### 10.6 Branch Observability Dashboard

Section 4.2 specifies a monitoring dashboard tracking:
- Active branch count per project
- Branch age distribution
- Branch storage consumption (divergence from parent)
- Branch creation/deletion rate
- TTL compliance (branches approaching expiration)

This should be integrated into the existing LakebaseOps monitoring app (currently 6 pages).

### 10.7 AI Agent Database Branching Module

Section 4.3 describes AI coding agents creating database branches for safe testing. The platform should provide a tool that:

1. Creates a Lakebase branch with 1-hour TTL
2. Waits for ACTIVE state
3. Applies and tests migrations against branch endpoint
4. Validates with Schema Diff
5. Returns migration SQL for human review
6. Branch auto-deletes after 1 hour

Instructions stored in `CLAUDE.md` or `AGENTS.md`.

### 10.8 Multi-Tenant Isolation Module

Support for both:
- **Pattern 5 (project-level):** Separate Lakebase projects per tenant with own branch hierarchy
- **Pattern 6 (schema-level):** Single project, multiple PostgreSQL schemas with RLS policies

### 10.9 Cross-System Governance View

A unified view mapping UC catalogs/schemas to Lakebase projects/branches, showing:
- Naming alignment compliance
- Access control consistency
- Lineage from OLTP to analytics

---

## 11. Changes to Existing Modules

### 11.1 `agents/provisioning/branching.py` (BranchingMixin)

- Add RFC 1123 branch name validation
- Enforce naming convention decision tree
- Add TTL policy defaults per branch type
- Add branch protection enforcement for production and staging
- Add max-10-branch monitoring and alerting
- Support point-in-time branching for audit snapshots
- Add branch type detection from name prefix (`ci-`, `dev-`, `feat-`, etc.)

### 11.2 `agents/provisioning/governance.py` (GovernanceMixin)

- Implement UC + Lakebase naming alignment mapping
- Add RBAC group naming convention enforcement (`domain_data_owners`, `domain_data_admins`, `domain_data_users`, `domain_data_readonly`)
- Add SQL grant generation aligned with naming (catalog-level, schema-level, data product, service principal)
- Enforce RLS for multi-tenant configurations
- Add Data API configuration (exposed schemas, CORS origins)
- Track data lineage from Lakebase to Delta Lake

### 11.3 `agents/provisioning/migration.py` (MigrationMixin)

- Enforce idempotent DDL patterns (`IF NOT EXISTS` for tables, columns, indexes)
- Align 9-step testing workflow with Section 2.6
- Add schema diff capture step
- Support Flyway, Liquibase, Prisma, and plain SQL migration tools
- Validate DDL idempotency before execution (lint/parse step)

### 11.4 `agents/provisioning/cicd.py` (CICDMixin)

- Generate GitHub Actions for branch-per-PR workflow (create on `opened/reopened`, delete on `closed`)
- Add schema diff PR comment posting
- Add migration replay step on PR merge (staging, then production)
- Include `|| true` for idempotent cleanup on branch deletion

### 11.5 `agents/provisioning/project.py` (ProjectMixin)

- Add multi-catalog strategy support (Enterprise Reference Architecture)
- Enforce project naming conventions (`domain-env` format)
- Add project-level multi-tenancy support
- Validate project names against RFC 1123

### 11.6 Monitoring App (`app/`)

- Add branch observability dashboard page (new page, currently 6 pages)
- Add branch age, storage, creation/deletion rate metrics
- Add TTL compliance alerts
- Add naming convention compliance checks
- Add cross-system governance view (UC + Lakebase alignment)

---

## 12. Testing Requirements

### 12.1 Unit Tests

- Branch name validation against RFC 1123 rules (valid/invalid edge cases)
- Naming convention decision tree logic (all 8 paths)
- TTL policy defaults per branch type (all 10 types)
- UC <-> Lakebase naming translation (separator, prefix ordering, max length)
- Idempotent DDL pattern detection (positive and negative cases)
- RBAC group name generation from domain names
- SQL grant generation for all 4 access levels
- Branch type inference from name prefix

### 12.2 Integration Tests

- Branch creation with proper naming and TTL (against real or mock Lakebase)
- Schema migration workflow end-to-end (create branch, apply DDL, schema diff, cleanup)
- GitHub Actions YAML generation and validation (parseable, correct triggers)
- Multi-tenant RLS enforcement (both project-level and schema-level)
- Data API configuration and request handling
- Branch protection enforcement (prevent deletion/reset of protected branches)
- Nightly reset workflow (staging reset from production)

### 12.3 End-to-End Tests

- Full PR lifecycle: PR open -> branch create -> migrate -> test -> merge -> replay -> cleanup
- Nightly staging reset workflow
- AI agent branching: create branch -> test migration -> validate -> cleanup (1h TTL)
- Multi-environment promotion: development -> staging -> production
- Branch limit enforcement (attempt to exceed 10 unarchived, expect graceful failure)
- Point-in-time audit branch creation and querying
- Multi-tenant isolation verification (cross-tenant data access attempts should fail)

---

## 13. Monitoring and Alerting Requirements

### 13.1 Branch Monitoring

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Active branch count | Per project | Alert at 8/10 (pre-limit warning) |
| Branch age distribution | Age of non-protected branches | Alert when branches exceed TTL |
| Branch storage consumption | Divergence from parent in GB | Alert on rapid growth |
| Branch creation/deletion rate | Operational throughput | Alert on anomalous spikes |
| TTL compliance | Branches approaching expiration | Alert 1 hour before TTL expiry |
| Orphaned branches | Branches with no PR or developer activity | Alert after 24h idle |

### 13.2 Governance Monitoring

| Metric | Description | Source |
|--------|-------------|--------|
| Permission auditing | Track grants/revokes | `system.access.audit` |
| Naming convention compliance | Non-compliant catalogs, schemas, branches | Custom validator |
| Branch protection status | Production + staging protection | Branch API |
| RLS policy compliance | Multi-tenant schemas with active RLS | PostgreSQL metadata |
| OAuth adoption | Detect password-based connections | Connection logs |

### 13.3 Cost Monitoring

| Metric | Description | Source |
|--------|-------------|--------|
| Scale-to-zero compliance | Non-production branches should idle | Compute metrics |
| CoW storage efficiency | Divergence vs. total branch sizes | Storage API |
| Warehouse costs | Expensive query detection | `system.billing.usage` |
| Sandbox data sprawl | Retention policy enforcement | UC metadata |

---

## 14. Performance Benchmarks Expected

The document does not specify explicit numeric benchmarks but implies the following from architectural principles:

| Operation | Expected Performance | Basis |
|-----------|---------------------|-------|
| Branch creation | Near-instant (O(1) metadata operation) | CoW architecture -- independent of DB size |
| Scale-to-zero | Automatic suspend when idle | Built-in Lakebase behavior |
| CoW storage | ~1GB for 1GB change on 100GB database | Only divergent pages stored |
| Branch deletion | Automatic via TTL | No manual intervention required |
| Nightly reset | Seconds (metadata operation) | Reset is lightweight |
| Max autoscale range | 8 CU | Hard limit, right-size for expected workload |

---

## 15. All Internal Links Referenced in the Document

### Google Docs Comment Annotations

| Annotation | Author/Context | Content |
|------------|---------------|---------|
| `[a]` | Jonathan Katz | UC "folders" hierarchy proposal may change the three-level namespace. Suggests refocusing on Lakebase Project core object naming. |
| `[b]` | Jonathan Katz | OLAP naming conventions differ from Postgres; Postgres tables named after objects since they are normalized. |
| `[c]` | Reviewer | Asks whether Neon docs were consulted for branch naming requirements. References: `https://neon.com/docs/manage/branches#branch-naming-requirements` |
| `[d]` | Author | Confirms "this refers the neon docs" |
| `[e]` | Chris | Questions "Git-like branching" phrase -- no merge capability exists, every conversation leads to assumption that merge is available. Suggests "CoW Replicas" or "Shallow Clones." |
| `[f]` | Author | Defends "Git-like branching" as resonant analogy for meetings, legacy DBAs, and newcomers to the concept. |
| `[g]` | Chris | Marked as resolved |
| `[h]` | Chris | Re-opened -- reiterates concern that phrase is misleading customers and internal FE folks |

### External References

| Reference | URL/Identifier |
|-----------|---------------|
| Neon branch naming docs | `https://neon.com/docs/manage/branches#branch-naming-requirements` |
| Databricks CLI installer | `https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh` |
| UC audit system table | `system.access.audit` |
| Billing system table | `system.billing.usage` |

### Tools and Frameworks Referenced (by name, no URLs)

- Databricks CLI (`databricks postgres` commands)
- Databricks Python SDK (`databricks.sdk.service.postgres`)
- Flyway (migration tool)
- Liquibase (migration tool)
- Prisma (migration tool)
- GitHub Actions
- Terraform
- DABs (Databricks Asset Bundles)

---

## 16. Security and Access Control Patterns

### 16.1 RBAC Group Naming Convention

| Group Name | Catalog Access | Schema Access |
|-----------|---------------|---------------|
| `domain_data_owners` | Full ownership of domain catalog | All schemas |
| `domain_data_admins` | USE CATALOG + CREATE SCHEMA | Domain schemas |
| `domain_data_users` | USE CATALOG | Specific schemas (SELECT) |
| `domain_data_readonly` | USE CATALOG | Specific schemas (SELECT only) |

### 16.2 SQL Grant Patterns

```sql
-- Catalog-level access
GRANT USE CATALOG ON CATALOG prod_finance TO finance_data_users;

-- Schema-level access
GRANT USE SCHEMA ON SCHEMA prod_finance.gold TO finance_analysts;
GRANT SELECT ON SCHEMA prod_finance.gold TO finance_analysts;

-- Data product access
GRANT USE SCHEMA ON SCHEMA prod_core.dp_customer_360 TO marketing_team;
GRANT SELECT ON SCHEMA prod_core.dp_customer_360 TO marketing_team;

-- Service Principal access (client ID in backticks)
GRANT USE CATALOG ON CATALOG prod_core TO `42ccfce7-b085-401f-baf3-264dcbd01230`;
```

### 16.3 Lakebase-Specific Security

| Control | Description |
|---------|-------------|
| OAuth-based authentication | Databricks identity, no password management |
| Row-Level Security (RLS) | Enforced automatically via Data API with Databricks identity |
| Branch protection | Prevents deletion/reset of production and staging |
| Data API configuration | Controls exposed schemas and CORS origins |
| Multi-tenant isolation (project) | Separate projects with own compute/storage |
| Multi-tenant isolation (schema) | RLS policies within shared project |

### 16.4 Cross-System Access Control

- Centralize through Unity Catalog groups (single source of truth)
- Single CI/CD pipeline manages both Lakebase branches and UC permissions
- Deployment scripts (Terraform, DABs) for privilege assignments -- no manual grants
- Workspace binding for catalog isolation
- Row-level filtering and column masking for sensitive data (HIPAA, PCI)

---

## 17. Data Lifecycle Management Rules

### 17.1 Branch Lifecycle

| Phase | Action | Applies To |
|-------|--------|-----------|
| Creation | Automated via CI/CD or developer request with enforced TTL | All ephemeral branches |
| Active use | Compute runs while active, scales to zero when idle | All branches |
| Expiration | TTL triggers automatic deletion (max 30 days) | Ephemeral branches only |
| Protection | Exempt from TTL, deletion, reset, and auto-archive | Production, staging |
| Reset | Staging resets nightly from production; dev branches reset weekly | Staging, developer branches |
| Promotion | Idempotent DDL replayed on parent (no merge) | All migration workflows |

### 17.2 Storage Lifecycle

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| CoW efficiency | Branches only store divergence from parent | Minimal storage for branches |
| Nightly reset | Keeps branch divergence sizes manageable | Prevents storage bloat |
| Branch limits | Max 10 unarchived per project | Enforces cleanup |
| Auto-archive | Idle branches archived automatically | Recoverable but not consuming resources |

### 17.3 Unity Catalog Data Lifecycle

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| Managed tables | Use managed storage for lifecycle control | Simplified cleanup |
| Sandbox TTL | Set data retention policies on sandbox catalogs | Prevents exploratory data sprawl |
| Delta optimization | OPTIMIZE and VACUUM on gold-layer tables | Reduces storage and query costs |
| Lineage tracking | Track flow from Lakebase OLTP to Delta Lake analytics | Auditability |

### 17.4 Cost Optimization

| Strategy | Implementation | Impact |
|----------|---------------|--------|
| TTL policies | Expiration on all ephemeral branches | Prevents orphaned branch costs |
| Scale-to-zero | Default for non-production branches | Zero compute when idle |
| Branch limits | Max 10 unarchived; auto-archive idle | Controls storage growth |
| CoW efficiency | Only store divergence | 1GB change on 100GB DB ~ 1GB cost |
| Nightly reset | Reset staging from production on schedule | Keeps branch sizes manageable |
| Query governance | Monitor `system.billing.usage` | Controls warehouse costs |

---

## 18. Schema Migration Workflow (Detailed)

### 9-Step Safe Migration Testing Workflow

1. Developer writes migration files locally (Flyway, Liquibase, Prisma, or plain SQL)
2. PR opened, triggering CI/CD pipeline
3. Pipeline creates Lakebase branch from staging:
   ```bash
   databricks postgres create-branch projects/my-project ci-pr-142 \
     --json '{"spec": {"source_branch": "projects/my-project/branches/staging", "ttl": "14400s"}}'
   ```
4. Migrations applied to the branch
5. Schema Diff captured (via Lakebase App UI or API)
6. Integration tests run against the migrated branch
7. Code review includes both code changes AND schema diff
8. On PR merge, migrations replayed on staging, then production
9. Branch auto-deletes after TTL (or explicitly on PR close)

### Idempotent DDL Requirement

All migrations must be idempotent (safe to re-run) since Lakebase has no merge capability:

```sql
-- GOOD: Idempotent
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS email VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_patients_email ON patients(email);

-- BAD: Non-idempotent (fails on re-run)
CREATE TABLE patients (...);
ALTER TABLE patients ADD COLUMN email VARCHAR(255);
```

### GitHub Actions Workflows (Complete YAML Provided)

**Create Branch on PR Open:**
- Trigger: `pull_request: [opened, reopened]`
- Steps: Install Databricks CLI -> Create branch with TTL -> Run Flyway migrations -> Run pytest integration tests

**Delete Branch on PR Close:**
- Trigger: `pull_request: [closed]`
- Steps: Delete branch (with `|| true` for idempotency)

---

## 19. CLI and SDK Reference

### Databricks CLI Commands

```bash
# Create branch
databricks postgres create-branch projects/PROJECT BRANCH_ID \
  --json '{"spec": {"source_branch": "projects/PROJECT/branches/BRANCH", "ttl": "604800s"}}'

# List branches
databricks postgres list-branches projects/PROJECT --output json

# Get branch details
databricks postgres get-branch projects/PROJECT/branches/BRANCH

# Reset branch from parent
databricks postgres reset-branch projects/PROJECT/branches/BRANCH

# Protect branch
databricks postgres update-branch projects/PROJECT/branches/BRANCH spec.is_protected \
  --json '{"spec": {"is_protected": true}}'

# Delete branch
databricks postgres delete-branch projects/PROJECT/branches/BRANCH
```

### Python SDK

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import Branch, BranchSpec, Duration

w = WorkspaceClient()

# Create branch with TTL
branch = w.postgres.create_branch(
    parent=f"projects/{project_name}",
    branch=Branch(spec=BranchSpec(
        source_branch=prod_branch_name,
        ttl=Duration(seconds=86400)
    )),
    branch_id="feature-branch"
).wait()

# Delete branch
w.postgres.delete_branch(
    name="projects/my-project/branches/feature-branch"
).wait()

# Reset branch
w.postgres.reset_branch(name="projects/my-project/branches/staging")
```

### Unity Catalog SQL

```sql
GRANT USE CATALOG ON CATALOG prod_finance TO finance_users;
GRANT USE SCHEMA ON SCHEMA prod_finance.gold TO finance_analysts;
GRANT SELECT ON SCHEMA prod_finance.gold TO finance_analysts;
```

---

## 20. Key Takeaways for Platform Implementation

1. **Naming is fundamental** -- The platform must enforce RFC 1123 for Lakebase branches and UC conventions for catalogs/schemas, with a translation layer between the two naming systems (underscore vs. hyphen, different prefix ordering).

2. **TTL is the primary branch lifecycle mechanism** -- Every non-protected branch must have an enforced TTL. The platform should provide sensible defaults and prevent infinite-lived ephemeral branches.

3. **No merge means idempotent-everything** -- The lack of merge capability is the single most impactful constraint. All migrations, DDL, and promotion workflows must be designed around replaying operations, not merging state.

4. **Branch limit of 10 drives automation** -- With only 10 unarchived branches per project, aggressive TTL enforcement and automated cleanup are non-negotiable.

5. **Multi-tenancy has two patterns** -- Project-level (full isolation, higher cost) and schema-level (RLS-based, lower cost). The platform should support both.

6. **CI/CD integration is custom work** -- Unlike Neon, Lakebase does not have native PR comment integration for schema diffs. This must be built as a custom GitHub Action.

7. **The "Git-like branching" messaging is contentious** -- The lack of merge capability is a known source of customer confusion. Platform documentation should be precise about what branching does and does not support.

8. **Governance spans two systems** -- UC groups provide the unified access control layer, but naming conventions differ between UC and Lakebase, requiring explicit mapping and validation.

9. **The UC namespace may evolve** -- Comment [a] indicates a proposed "folders" hierarchy could change the three-level namespace, suggesting the platform should be designed for extensibility.

10. **OLTP vs. OLAP naming diverges intentionally** -- Comment [b] confirms Postgres tables use entity names while analytics tables use dim/fact prefixes. The platform must handle both conventions correctly depending on context.
