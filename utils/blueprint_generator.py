"""
Migration Blueprint Generator

Generates a structured 4-phase migration plan:
  Phase 1: Schema & Index Preparation
  Phase 2: Data Migration (Bulk or CDC)
  Phase 3: Application Refactoring
  Phase 4: Performance Tuning & Go-Live

Engine-aware: produces engine-specific commands, auth notes,
and decommission steps for Aurora, RDS, Cloud SQL, Azure, and self-managed PG.
"""

from __future__ import annotations

from datetime import UTC, datetime

from config.migration_profiles import (
    ENGINE_KIND,
    AssessmentResult,
    DatabaseProfile,
    MigrationBlueprint,
    MigrationPhase,
    MigrationStrategy,
    WorkloadProfile,
)

_ENGINE_LABELS = {
    "aurora-postgresql": "Aurora PostgreSQL",
    "rds-postgresql": "RDS PostgreSQL",
    "cloud-sql-postgresql": "Cloud SQL for PostgreSQL",
    "azure-postgresql": "Azure Database for PostgreSQL Flexible Server",
    "self-managed-postgresql": "Self-Managed PostgreSQL",
    "alloydb-postgresql": "Google AlloyDB for PostgreSQL",
    "supabase-postgresql": "Supabase PostgreSQL",
    "dynamodb": "Amazon DynamoDB",
}

_AUTH_MIGRATION_NOTES = {
    "aurora-postgresql": "Switch authentication from IAM/password to Databricks OAuth tokens",
    "rds-postgresql": "Switch authentication from IAM/password to Databricks OAuth tokens",
    "cloud-sql-postgresql": "Switch authentication from GCP IAM DB auth to Databricks OAuth tokens",
    "azure-postgresql": "Switch authentication from Entra ID (Azure AD) to Databricks OAuth tokens",
    "self-managed-postgresql": "Switch authentication from password/certificate to Databricks OAuth tokens",
    "alloydb-postgresql": "Switch authentication from GCP IAM DB auth to Databricks OAuth tokens",
    "supabase-postgresql": "Switch authentication from Supabase JWT/API keys to Databricks OAuth tokens",
    "dynamodb": "Switch authentication from AWS IAM roles/access keys to Databricks OAuth tokens",
}

_POOLING_NOTES = {
    "aurora-postgresql": "Update connection pooling configuration (replace RDS Proxy with app-side pooling if needed)",
    "rds-postgresql": "Update connection pooling configuration (replace RDS Proxy with app-side pooling if needed)",
    "cloud-sql-postgresql": "Update connection pooling (replace Cloud SQL Auth Proxy with direct app-side pooling)",
    "azure-postgresql": "Update connection pooling (replace built-in PgBouncer on port 6432 with app-side pooling)",
    "self-managed-postgresql": "Update connection pooling (replace PgBouncer/pgpool-II with app-side pooling)",
    "alloydb-postgresql": "Update connection pooling (replace AlloyDB Auth Proxy with direct app-side pooling)",
    "supabase-postgresql": "Update connection pooling (replace Supavisor pooler with app-side pooling)",
    "dynamodb": "N/A for DynamoDB (HTTP API, no persistent connections); configure app-side connection pooling for Lakebase",
}

_DECOMMISSION_STEPS = {
    "aurora-postgresql": "Decommission Aurora cluster after validation period (recommended: 2 weeks)",
    "rds-postgresql": "Decommission RDS instance after validation period (recommended: 2 weeks)",
    "cloud-sql-postgresql": "Delete Cloud SQL instance after validation period (recommended: 2 weeks); revoke IAM DB auth bindings",
    "azure-postgresql": "Delete Azure Flexible Server after validation period (recommended: 2 weeks); revoke Entra ID assignments",
    "self-managed-postgresql": "Decommission self-managed PostgreSQL servers after validation period; archive WAL backups",
    "alloydb-postgresql": "Delete AlloyDB cluster after validation period (recommended: 2 weeks); revoke IAM bindings",
    "supabase-postgresql": "Pause or delete Supabase project after validation period (recommended: 2 weeks); revoke API keys",
    "dynamodb": "Disable DynamoDB Streams consumers, scale down provisioned capacity to minimum, delete tables after validation period (recommended: 2 weeks)",
}

_NETWORK_PREREQS = {
    "aurora-postgresql": "Network connectivity between Aurora VPC and Lakebase endpoint (Private Link or public)",
    "rds-postgresql": "Network connectivity between RDS VPC and Lakebase endpoint (Private Link or public)",
    "cloud-sql-postgresql": "Network connectivity between GCP VPC and Lakebase endpoint (Private Service Connect or public)",
    "azure-postgresql": "Network connectivity between Azure VNet and Lakebase endpoint (Private Link or public)",
    "self-managed-postgresql": "Network connectivity between source host and Lakebase endpoint (VPN, Direct Connect, or public)",
    "alloydb-postgresql": "Network connectivity between AlloyDB VPC and Lakebase endpoint (Private Service Connect or public)",
    "supabase-postgresql": "Network connectivity between Supabase project and Lakebase endpoint (public; use connection string from Supabase dashboard)",
    "dynamodb": "VPC endpoint for DynamoDB and S3 gateway endpoint for Export to S3; network connectivity to Lakebase endpoint",
}


def generate_blueprint(
    db_profile: DatabaseProfile,
    assessment: AssessmentResult,
    workload: WorkloadProfile | None = None,
    source_endpoint: str = "<source-endpoint>",
    lakebase_endpoint: str = "<lakebase-endpoint>",
    database_name: str = "",
    source_engine: str = "aurora-postgresql",
) -> MigrationBlueprint:
    """Generate a migration blueprint based on assessment results."""
    db_name = database_name or db_profile.name
    strategy = _select_strategy(db_profile, assessment, workload, source_engine)
    engine_label = _ENGINE_LABELS.get(source_engine, source_engine)

    phases = [
        _phase_1_schema(db_profile, assessment, source_endpoint, lakebase_endpoint, db_name, source_engine),
        _phase_2_data(db_profile, strategy, source_endpoint, lakebase_endpoint, db_name, source_engine),
        _phase_3_application(assessment, lakebase_endpoint, db_name, source_engine),
        _phase_4_golive(assessment, source_engine),
    ]

    total_days = sum(p.estimated_days for p in phases)
    risk = _assess_risk(assessment)

    network_prereq = _NETWORK_PREREQS.get(source_engine, _NETWORK_PREREQS["aurora-postgresql"])
    prerequisites = [
        "Lakebase project created with appropriate branching pattern",
        network_prereq,
        "Databricks workspace with Unity Catalog configured",
        f"Lakebase Autoscaling instance sized at {assessment.recommended_cu_min}-{assessment.recommended_cu_max} CU",
        "Application team briefed on connection string and auth changes",
    ]

    post_checks = [
        f"Verify row counts match between {engine_label} and Lakebase for all tables",
        "Run EXPLAIN ANALYZE on top 10 queries and compare execution plans",
        "Validate application connectivity with OAuth tokens",
        "Confirm Synced Tables are populating Delta Lake correctly",
        "Run load test at expected peak traffic levels",
        "Verify PITR backup is configured and tested",
    ]

    rollback = (
        f"If issues are found post-cutover:\n"
        f"1. Revert application connection strings to {engine_label} endpoint\n"
        f"2. Verify {engine_label} is still receiving writes (if CDC was used, it remains in sync)\n"
        f"3. Investigate and resolve Lakebase issues\n"
        f"4. Re-attempt cutover after fixes"
    )

    return MigrationBlueprint(
        strategy=strategy,
        phases=phases,
        total_estimated_days=round(total_days, 1),
        risk_level=risk,
        prerequisites=prerequisites,
        post_migration_checks=post_checks,
        rollback_plan=rollback,
    )


def render_blueprint_markdown(
    blueprint: MigrationBlueprint,
    db_profile: DatabaseProfile,
    assessment: AssessmentResult,
    source_engine: str = "Aurora PostgreSQL",
) -> str:
    """Render a migration blueprint as a markdown report."""
    engine_label = _ENGINE_LABELS.get(source_engine, source_engine)
    lines = []
    now = datetime.now(UTC).strftime("%Y-%m-%d")

    lines.append(f"# Migration Blueprint: {engine_label} to Lakebase")
    lines.append(f"\n**Generated:** {now}")
    lines.append(f"**Source Engine:** {engine_label}")
    lines.append(f"**Database:** {db_profile.name}")
    lines.append(f"**Size:** {db_profile.size_gb:.1f} GB ({db_profile.table_count} tables)")
    lines.append(f"**Strategy:** {blueprint.strategy.value}")
    lines.append(f"**Estimated Duration:** {blueprint.total_estimated_days} days")
    lines.append(f"**Risk Level:** {blueprint.risk_level}")
    lines.append(f"**Readiness Score:** {assessment.overall_score}/100 ({assessment.category.value})")

    lines.append("\n**Recommended Lakebase Sizing:**")
    lines.append(f"- Tier: {assessment.recommended_tier.value}")
    lines.append(f"- Compute: {assessment.recommended_cu_min}-{assessment.recommended_cu_max} CU")

    if assessment.blockers:
        lines.append("\n---\n## Blockers & Risks\n")
        for b in assessment.blockers:
            lines.append(f"- **[{b.severity.value.upper()}]** {b.description}")
            if b.workaround:
                lines.append(f"  - Workaround: {b.workaround}")

    if assessment.warnings:
        lines.append("\n## Warnings\n")
        for w in assessment.warnings:
            lines.append(f"- {w}")

    lines.append("\n## Lakebase Migration Notes\n")
    lines.append(
        "- **pg_restore --disable-triggers**: Does NOT work on Lakebase. "
        "Lakebase prevents disabling system-level foreign key triggers "
        "(RI_ConstraintTrigger). Manually disable user-defined triggers before "
        "data load and re-enable after."
    )
    lines.append(
        "- **Recommended dump format**: Use plain-text pg_dump (`pg_dump > data.sql`) "
        "and load with `psql -f data.sql`. This gives full control over load order "
        "and avoids pg_restore trigger issues."
    )
    lines.append(
        "- **--no-owner --no-privileges**: Always use these flags. Lakebase uses "
        "Databricks identity management; source roles will not exist on the target."
    )

    if source_engine == "cloud-sql-postgresql":
        lines.append(
            "- **Cloud SQL note**: The `cloudsqlsuperuser` role does not exist on Lakebase. "
            "Extension creation and admin tasks use the Lakebase admin role instead."
        )
    elif source_engine == "azure-postgresql":
        lines.append(
            "- **Azure note**: The `azure_pg_admin` role does not exist on Lakebase. "
            "PgBouncer built-in pooling (port 6432) is not available; use application-side pooling."
        )
    elif source_engine == "self-managed-postgresql":
        lines.append(
            "- **Self-managed note**: Custom-compiled extensions must be verified against "
            "Lakebase's supported extension list. OS-level dependencies are not transferable."
        )
    elif source_engine == "alloydb-postgresql":
        lines.append(
            "- **AlloyDB note**: The `alloydbsuperuser` role does not exist on Lakebase. "
            "AlloyDB AI/ML integration (`google_ml_integration`) must be replaced with "
            "Databricks Foundation Model API. Columnar engine acceleration is not available."
        )
    elif source_engine == "supabase-postgresql":
        lines.append(
            "- **Supabase note**: Supabase-specific schemas (`auth`, `storage`, `realtime`) "
            "are platform-managed and do not migrate. Replace Supabase Auth with Databricks "
            "identity management. Replace Supabase Realtime with application-level WebSockets."
        )
    elif source_engine == "dynamodb":
        lines.append(
            "- **DynamoDB note**: This is a cross-engine NoSQL-to-relational migration. "
            "Schema must be redesigned from access patterns, not ported directly. "
            "Use DynamoDB Export to S3 (requires PITR) for zero-impact data extraction."
        )
        lines.append("\n**DynamoDB Type Mapping:**\n")
        lines.append("| DynamoDB | PostgreSQL | Notes |")
        lines.append("|----------|-----------|-------|")
        lines.append("| S (String) | `text` | |")
        lines.append("| N (Number) | `numeric` | Preserves arbitrary precision |")
        lines.append("| B (Binary) | `bytea` | |")
        lines.append("| BOOL | `boolean` | |")
        lines.append("| NULL | SQL `NULL` | |")
        lines.append("| SS (String Set) | `text[]` | Unique, unordered |")
        lines.append("| NS (Number Set) | `numeric[]` | Unique, unordered |")
        lines.append("| L (List) | `jsonb` | Ordered, mixed types |")
        lines.append("| M (Map) | `jsonb` or flattened columns | Nested maps stay as JSONB |")

    is_nosql = ENGINE_KIND.get(source_engine) == "nosql"

    if not is_nosql and (assessment.supported_extensions or assessment.unsupported_extensions):
        lines.append("\n---\n## Extension Compatibility\n")
        if assessment.supported_extensions:
            lines.append(
                f"**Supported ({len(assessment.supported_extensions)}):** {', '.join(sorted(assessment.supported_extensions))}"
            )
        if assessment.unsupported_extensions:
            lines.append(
                f"\n**Unsupported ({len(assessment.unsupported_extensions)}):** {', '.join(sorted(assessment.unsupported_extensions))}"
            )

    lines.append("\n---\n## Prerequisites\n")
    for p in blueprint.prerequisites:
        lines.append(f"- {p}")

    for phase in blueprint.phases:
        lines.append(f"\n---\n## Phase {phase.phase_number}: {phase.name}")
        lines.append(f"\n**Estimated:** {phase.estimated_days} days")
        lines.append(f"\n{phase.description}\n")

        if phase.steps:
            lines.append("### Steps\n")
            for i, step in enumerate(phase.steps, 1):
                lines.append(f"{i}. {step}")

        if phase.commands:
            lines.append("\n### Commands\n")
            for cmd in phase.commands:
                lines.append(f"```bash\n{cmd}\n```")

    lines.append("\n---\n## Post-Migration Validation\n")
    for check in blueprint.post_migration_checks:
        lines.append(f"- [ ] {check}")

    lines.append(f"\n---\n## Rollback Plan\n\n{blueprint.rollback_plan}")

    return "\n".join(lines)


# ── Internal Helpers ───────────────────────────────────────────────────────


def _select_strategy(
    db: DatabaseProfile,
    assessment: AssessmentResult,
    workload: WorkloadProfile | None,
    source_engine: str = "aurora-postgresql",
) -> MigrationStrategy:
    if source_engine == "dynamodb":
        return MigrationStrategy.CROSS_ENGINE

    if db.pg_version and not db.pg_version.startswith(("14", "15", "16", "17")):
        return MigrationStrategy.CROSS_ENGINE

    if workload and workload.avg_tps > 100:
        return MigrationStrategy.HYBRID

    if db.size_gb > 500:
        return MigrationStrategy.HYBRID

    if source_engine == "cloud-sql-postgresql" and workload and workload.avg_tps > 50:
        return MigrationStrategy.BULK_DUMP_RESTORE

    return MigrationStrategy.BULK_DUMP_RESTORE


def _phase_1_schema(
    db: DatabaseProfile,
    assessment: AssessmentResult,
    source_ep: str,
    lakebase_ep: str,
    db_name: str,
    source_engine: str = "aurora-postgresql",
) -> MigrationPhase:
    if source_engine == "dynamodb":
        steps = [
            "Analyze DynamoDB access patterns (GetItem, Query, Scan, BatchWrite) to design relational schema",
            "Map partition keys and sort keys to PostgreSQL composite primary keys",
            "Convert GSIs to PostgreSQL secondary indexes (B-tree, GIN for JSONB)",
            "Design JSONB columns for nested Map/List attributes; add generated columns for hot query paths",
            "Normalize single-table design patterns into separate relational tables with foreign keys",
            "Create schema in Lakebase target branch and validate with sample data",
        ]
        commands = [
            "# DynamoDB type mapping: S->text, N->numeric, B->bytea, M->jsonb, L->jsonb, SS->text[], BOOL->boolean",
            "# Design SQL schema based on access patterns, not DynamoDB table structure",
        ]
        return MigrationPhase(
            phase_number=1,
            name="Schema Design & Relational Modeling",
            description="Design a relational schema from DynamoDB access patterns. Map key schemas to primary keys, GSIs to indexes, and nested documents to JSONB columns.",
            steps=steps,
            estimated_days=max(5, (db.gsi_count or 0) * 0.5 + 5),
            commands=commands,
        )

    engine_label = _ENGINE_LABELS.get(source_engine, source_engine)

    steps = [
        f"Extract schema from {engine_label} using pg_dump --schema-only",
        "Review extracted DDL for incompatibilities (unsupported extensions, custom types)",
        f"Remove or replace {engine_label}-specific extension references",
        "Optimize indexing strategy (B-tree for OLTP, pgvector for AI use cases)",
        "Create schema in Lakebase target branch",
        "Validate schema creation with \\dt and \\d+ checks",
    ]

    if source_engine == "self-managed-postgresql":
        steps.insert(2, "Verify custom-compiled extensions are available on Lakebase or identify workarounds")

    if assessment.unsupported_extensions:
        steps.insert(
            2,
            f"Address {len(assessment.unsupported_extensions)} unsupported extensions: {', '.join(assessment.unsupported_extensions)}",
        )

    if source_engine == "cloud-sql-postgresql":
        commands = [
            "# Option 1: pg_dump via Cloud SQL Auth Proxy",
            f"pg_dump --schema-only -h 127.0.0.1 -p 5432 -U <user> -d {db_name} > schema.sql",
            "# Option 2: gcloud sql export",
            f"gcloud sql export sql {source_ep} gs://<bucket>/schema.sql --database={db_name} --offload",
            f"psql -h {lakebase_ep} -d {db_name} -U <user> -f schema.sql",
        ]
    elif source_engine == "azure-postgresql":
        commands = [
            "# pg_dump via Azure Private Link or public endpoint",
            f"pg_dump --schema-only -h {source_ep} -U <user> -d {db_name} > schema.sql",
            f"psql -h {lakebase_ep} -d {db_name} -U <user> -f schema.sql",
        ]
    else:
        commands = [
            f"pg_dump --schema-only -h {source_ep} -U <user> -d {db_name} > schema.sql",
            f"psql -h {lakebase_ep} -d {db_name} -U <user> -f schema.sql",
        ]

    return MigrationPhase(
        phase_number=1,
        name="Schema & Index Preparation",
        description=f"Extract, clean, and apply schema from {engine_label} to Lakebase. Address extension incompatibilities and optimize indexing.",
        steps=steps,
        estimated_days=max(2, len(assessment.unsupported_extensions) * 0.5 + 2),
        commands=commands,
    )


def _phase_2_data(
    db: DatabaseProfile,
    strategy: MigrationStrategy,
    source_ep: str,
    lakebase_ep: str,
    db_name: str,
    source_engine: str = "aurora-postgresql",
) -> MigrationPhase:
    engine_label = _ENGINE_LABELS.get(source_engine, source_engine)

    if strategy == MigrationStrategy.BULK_DUMP_RESTORE:
        steps = [
            "Schedule a maintenance window for the bulk migration",
            f"Export data from {engine_label} using pg_dump (plain-text format recommended)",
            "Disable user-defined triggers on target tables before data load",
            "Import data into Lakebase using psql (plain-text) or pg_restore (custom format with --no-owner --no-privileges)",
            "Re-enable user-defined triggers after data load",
            "Verify row counts match for all tables",
            "Rebuild indexes and run ANALYZE",
        ]

        if source_engine == "cloud-sql-postgresql":
            commands = [
                "# Plain-text dump via Cloud SQL Auth Proxy (recommended for Lakebase)",
                f"pg_dump -h 127.0.0.1 -p 5432 -U <user> -d {db_name} --no-owner --no-privileges > data.sql",
                f"psql -h {lakebase_ep} -U <user> -d {db_name} -f data.sql",
            ]
        elif source_engine == "self-managed-postgresql":
            steps.insert(1, "Verify pg_dump client version matches source PostgreSQL major version")
            commands = [
                "# Plain-text dump (recommended for Lakebase)",
                f"pg_dump -h {source_ep} -U <user> -d {db_name} --no-owner --no-privileges > data.sql",
                f"psql -h {lakebase_ep} -U <user> -d {db_name} -f data.sql",
            ]
        else:
            commands = [
                "# Plain-text dump (recommended for Lakebase)",
                f"pg_dump -h {source_ep} -U <user> -d {db_name} --no-owner --no-privileges > data.sql",
                f"psql -h {lakebase_ep} -U <user> -d {db_name} -f data.sql",
                "",
                "# Alternative: custom format (note --disable-triggers limitation)",
                f"pg_dump -h {source_ep} -U <user> -d {db_name} -F c -f data.dump",
                f"pg_restore -h {lakebase_ep} -U <user> -d {db_name} -F c --no-owner --no-privileges data.dump",
            ]
        est_days = max(1, db.size_gb / 100)

    elif strategy in (MigrationStrategy.CDC_LOGICAL_REPLICATION, MigrationStrategy.HYBRID):
        steps = [
            "Perform initial bulk load using pg_dump/pg_restore",
            f"Enable logical replication on {engine_label} (wal_level = logical)",
            f"Create publication on {engine_label} for all tables",
            "Create subscription on Lakebase pointing to source",
            "Monitor replication lag until near-zero",
            "Cut over application traffic to Lakebase",
            "Drop subscription after successful cutover",
        ]

        if source_engine == "cloud-sql-postgresql":
            steps[1] = "Enable logical replication on Cloud SQL (set cloudsql.logical_decoding = on)"
            steps.insert(
                1,
                "Note: Cloud SQL does not support being a logical replication publisher natively; consider pg_dump + Datastream for CDC",
            )

        commands = [
            f"pg_dump -h {source_ep} -U <user> -d {db_name} -F c -f data.dump",
            f"pg_restore -h {lakebase_ep} -U <user> -d {db_name} -F c data.dump",
            f"-- On {engine_label}:",
            "ALTER SYSTEM SET wal_level = logical;",
            "CREATE PUBLICATION datasync FOR ALL TABLES;",
            "-- On Lakebase:",
            f"CREATE SUBSCRIPTION datasync_sub CONNECTION 'host={source_ep} dbname={db_name}' PUBLICATION datasync;",
        ]
        est_days = max(3, db.size_gb / 100 + 2)
    else:
        if source_engine == "dynamodb":
            steps = [
                "Enable PITR on all DynamoDB tables (required for Export to S3)",
                "Export DynamoDB tables to S3 using ExportTableToPointInTime (zero impact on table performance)",
                "Parse DynamoDB JSON export files and transform to relational format",
                "Bulk load transformed data into Lakebase using COPY or batch INSERT",
                "Verify record counts match (DynamoDB ItemCount vs PostgreSQL row count)",
                "Set up incremental sync via DynamoDB Streams + Lambda if cutover window is needed",
            ]
            commands = [
                "# Export via AWS CLI (requires PITR enabled)",
                "aws dynamodb export-table-to-point-in-time --table-arn <arn> --s3-bucket <bucket> --export-format DYNAMODB_JSON",
                "# Parse and transform DynamoDB JSON to SQL INSERT statements or CSV for COPY",
            ]
        else:
            steps = [
                "Evaluate cross-engine migration tooling (AWS DMS, AWS SCT, pgloader)",
                "Convert schema using Schema Conversion Tool",
                "Migrate data using DMS full load + CDC or pgloader",
                "Validate data integrity post-migration",
            ]
            commands = []
        est_days = max(10, db.size_gb / 50 + 5)

    return MigrationPhase(
        phase_number=2,
        name="Data Migration",
        description=f"Strategy: {strategy.value}. Migrate data from {engine_label} to Lakebase with {'minimal' if strategy != MigrationStrategy.BULK_DUMP_RESTORE else 'scheduled'} downtime.",
        steps=steps,
        estimated_days=round(est_days, 1),
        commands=commands,
    )


def _phase_3_application(
    assessment: AssessmentResult,
    lakebase_ep: str,
    db_name: str,
    source_engine: str = "aurora-postgresql",
) -> MigrationPhase:
    auth_note = _AUTH_MIGRATION_NOTES.get(source_engine, _AUTH_MIGRATION_NOTES["aurora-postgresql"])
    pool_note = _POOLING_NOTES.get(source_engine, _POOLING_NOTES["aurora-postgresql"])

    if source_engine == "dynamodb":
        steps = [
            "Rewrite DynamoDB SDK calls (GetItem, PutItem, Query, Scan) to SQL queries via psycopg",
            auth_note,
            "Replace DynamoDB Streams + Lambda consumers with application-level triggers or Lakeflow Connect",
            "Replace DAX caching layer with application-side caching (Redis) or PostgreSQL materialized views",
            "Update IAM-based access to Databricks OAuth token authentication",
            "Configure Synced Tables for Delta Lake integration (OLTP-to-OLAP sync)",
        ]
        return MigrationPhase(
            phase_number=3,
            name="Application Rewrite",
            description="Rewrite DynamoDB API calls to SQL, replace Streams consumers, and update authentication to Databricks OAuth.",
            steps=steps,
            estimated_days=10,
            commands=[
                f'DATABASE_URL = "postgresql://<user>:<oauth_token>@{lakebase_ep}:5432/{db_name}?sslmode=require"',
                "# Replace: dynamodb.get_item(TableName='Users', Key={'userId': {'S': '123'}})",
                "# With:    cur.execute('SELECT * FROM users WHERE user_id = %s', ('123',))",
            ],
        )

    steps = [
        f"Update application connection string to Lakebase endpoint ({lakebase_ep})",
        auth_note,
        pool_note,
        "Run EXPLAIN ANALYZE on top queries to verify execution plans",
        "Configure Synced Tables for Delta Lake integration (OLTP-to-OLAP sync)",
        "Set up pgvector indexes if AI/ML use cases are planned",
    ]

    if assessment.unsupported_extensions:
        steps.insert(2, "Deploy workarounds for unsupported extensions (Databricks Jobs for pg_cron, etc.)")

    return MigrationPhase(
        phase_number=3,
        name="Application Refactoring",
        description="Update application connections, authentication, and integrate with the Databricks Lakehouse ecosystem.",
        steps=steps,
        estimated_days=5,
        commands=[
            f'DATABASE_URL = "postgresql://<user>:<oauth_token>@{lakebase_ep}:5432/{db_name}?sslmode=require"',
        ],
    )


def _phase_4_golive(
    assessment: AssessmentResult,
    source_engine: str = "aurora-postgresql",
) -> MigrationPhase:
    decommission = _DECOMMISSION_STEPS.get(source_engine, _DECOMMISSION_STEPS["aurora-postgresql"])

    steps = [
        "Enable High Availability (HA) with standby replicas",
        "Configure PITR backup with appropriate retention window",
        "Run load test at expected peak traffic",
        "Set up monitoring dashboards (Databricks AI/BI or LakebaseOps platform)",
        "Configure alerting thresholds for connections, cache hit ratio, deadlocks",
        "Schedule cutover during low-traffic window",
        "Execute cutover and monitor for 24-48 hours",
        decommission,
    ]

    return MigrationPhase(
        phase_number=4,
        name="Performance Tuning & Go-Live",
        description="Optimize performance, enable HA/DR, and execute production cutover.",
        steps=steps,
        estimated_days=5,
        commands=[],
    )


def _assess_risk(assessment: AssessmentResult) -> str:
    blocker_count = len(assessment.blockers)
    if blocker_count == 0:
        return "low"
    elif blocker_count <= 3:
        return "medium"
    else:
        return "high"
