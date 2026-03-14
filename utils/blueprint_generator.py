"""
Migration Blueprint Generator

Generates a structured 4-phase migration plan:
  Phase 1: Schema & Index Preparation
  Phase 2: Data Migration (Bulk or CDC)
  Phase 3: Application Refactoring
  Phase 4: Performance Tuning & Go-Live
"""

from __future__ import annotations

from datetime import datetime, timezone

from config.migration_profiles import (
    AssessmentResult,
    DatabaseProfile,
    MigrationBlueprint,
    MigrationPhase,
    MigrationStrategy,
    WorkloadProfile,
)


def generate_blueprint(
    db_profile: DatabaseProfile,
    assessment: AssessmentResult,
    workload: WorkloadProfile | None = None,
    source_endpoint: str = "<aurora-endpoint>",
    lakebase_endpoint: str = "<lakebase-endpoint>",
    database_name: str = "",
) -> MigrationBlueprint:
    """Generate a migration blueprint based on assessment results."""
    db_name = database_name or db_profile.name
    strategy = _select_strategy(db_profile, assessment, workload)

    phases = [
        _phase_1_schema(db_profile, assessment, source_endpoint, lakebase_endpoint, db_name),
        _phase_2_data(db_profile, strategy, source_endpoint, lakebase_endpoint, db_name),
        _phase_3_application(assessment, lakebase_endpoint, db_name),
        _phase_4_golive(assessment),
    ]

    total_days = sum(p.estimated_days for p in phases)
    risk = _assess_risk(assessment)

    prerequisites = [
        "Lakebase project created with appropriate branching pattern",
        "Network connectivity between Aurora VPC and Lakebase endpoint (Private Link or public)",
        "Databricks workspace with Unity Catalog configured",
        f"Lakebase Autoscaling instance sized at {assessment.recommended_cu_min}-{assessment.recommended_cu_max} CU",
        "Application team briefed on connection string and auth changes",
    ]

    post_checks = [
        "Verify row counts match between Aurora and Lakebase for all tables",
        "Run EXPLAIN ANALYZE on top 10 queries and compare execution plans",
        "Validate application connectivity with OAuth tokens",
        "Confirm Synced Tables are populating Delta Lake correctly",
        "Run load test at expected peak traffic levels",
        "Verify PITR backup is configured and tested",
    ]

    rollback = (
        "If issues are found post-cutover:\n"
        "1. Revert application connection strings to Aurora endpoint\n"
        "2. Verify Aurora is still receiving writes (if CDC was used, it remains in sync)\n"
        "3. Investigate and resolve Lakebase issues\n"
        "4. Re-attempt cutover after fixes"
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
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines.append(f"# Migration Blueprint: {source_engine} to Lakebase")
    lines.append(f"\n**Generated:** {now}")
    lines.append(f"**Database:** {db_profile.name}")
    lines.append(f"**Size:** {db_profile.size_gb:.1f} GB ({db_profile.table_count} tables)")
    lines.append(f"**Strategy:** {blueprint.strategy.value}")
    lines.append(f"**Estimated Duration:** {blueprint.total_estimated_days} days")
    lines.append(f"**Risk Level:** {blueprint.risk_level}")
    lines.append(f"**Readiness Score:** {assessment.overall_score}/100 ({assessment.category.value})")

    lines.append(f"\n**Recommended Lakebase Sizing:**")
    lines.append(f"- Tier: {assessment.recommended_tier.value}")
    lines.append(f"- Compute: {assessment.recommended_cu_min}-{assessment.recommended_cu_max} CU")

    # Blockers
    if assessment.blockers:
        lines.append("\n---\n## Blockers & Risks\n")
        for b in assessment.blockers:
            lines.append(f"- **[{b.severity.value.upper()}]** {b.description}")
            if b.workaround:
                lines.append(f"  - Workaround: {b.workaround}")

    # Warnings
    if assessment.warnings:
        lines.append("\n## Warnings\n")
        for w in assessment.warnings:
            lines.append(f"- {w}")

    lines.append("\n## Lakebase Migration Notes\n")
    lines.append("- **pg_restore --disable-triggers**: Does NOT work on Lakebase. "
                 "Lakebase prevents disabling system-level foreign key triggers "
                 "(RI_ConstraintTrigger). Manually disable user-defined triggers before "
                 "data load and re-enable after.")
    lines.append("- **Recommended dump format**: Use plain-text pg_dump (`pg_dump > data.sql`) "
                 "and load with `psql -f data.sql`. This gives full control over load order "
                 "and avoids pg_restore trigger issues.")
    lines.append("- **--no-owner --no-privileges**: Always use these flags. Lakebase uses "
                 "Databricks identity management; Aurora roles will not exist on the target.")

    # Extension compatibility
    if assessment.supported_extensions or assessment.unsupported_extensions:
        lines.append("\n---\n## Extension Compatibility\n")
        if assessment.supported_extensions:
            lines.append(f"**Supported ({len(assessment.supported_extensions)}):** {', '.join(sorted(assessment.supported_extensions))}")
        if assessment.unsupported_extensions:
            lines.append(f"\n**Unsupported ({len(assessment.unsupported_extensions)}):** {', '.join(sorted(assessment.unsupported_extensions))}")

    # Prerequisites
    lines.append("\n---\n## Prerequisites\n")
    for p in blueprint.prerequisites:
        lines.append(f"- {p}")

    # Phases
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

    # Post-migration
    lines.append("\n---\n## Post-Migration Validation\n")
    for check in blueprint.post_migration_checks:
        lines.append(f"- [ ] {check}")

    # Rollback
    lines.append(f"\n---\n## Rollback Plan\n\n{blueprint.rollback_plan}")

    return "\n".join(lines)


# ── Internal Helpers ───────────────────────────────────────────────────────


def _select_strategy(
    db: DatabaseProfile,
    assessment: AssessmentResult,
    workload: WorkloadProfile | None,
) -> MigrationStrategy:
    if db.pg_version and not db.pg_version.startswith(("14", "15", "16", "17")):
        return MigrationStrategy.CROSS_ENGINE

    if workload and workload.avg_tps > 100:
        return MigrationStrategy.HYBRID

    if db.size_gb > 500:
        return MigrationStrategy.HYBRID

    return MigrationStrategy.BULK_DUMP_RESTORE


def _phase_1_schema(
    db: DatabaseProfile,
    assessment: AssessmentResult,
    source_ep: str,
    lakebase_ep: str,
    db_name: str,
) -> MigrationPhase:
    steps = [
        "Extract schema from Aurora using pg_dump --schema-only",
        "Review extracted DDL for incompatibilities (unsupported extensions, custom types)",
        "Remove or replace Aurora-specific extension references",
        "Optimize indexing strategy (B-tree for OLTP, pgvector for AI use cases)",
        "Create schema in Lakebase target branch",
        "Validate schema creation with \\dt and \\d+ checks",
    ]

    if assessment.unsupported_extensions:
        steps.insert(2, f"Address {len(assessment.unsupported_extensions)} unsupported extensions: {', '.join(assessment.unsupported_extensions)}")

    commands = [
        f"pg_dump --schema-only -h {source_ep} -U <user> -d {db_name} > schema.sql",
        f"psql -h {lakebase_ep} -d {db_name} -U <user> -f schema.sql",
    ]

    return MigrationPhase(
        phase_number=1,
        name="Schema & Index Preparation",
        description="Extract, clean, and apply schema from Aurora to Lakebase. Address extension incompatibilities and optimize indexing.",
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
) -> MigrationPhase:
    if strategy == MigrationStrategy.BULK_DUMP_RESTORE:
        steps = [
            "Schedule a maintenance window for the bulk migration",
            "Export data from Aurora using pg_dump (plain-text format recommended)",
            "Disable user-defined triggers on target tables before data load",
            "Import data into Lakebase using psql (plain-text) or pg_restore (custom format with --no-owner --no-privileges)",
            "Re-enable user-defined triggers after data load",
            "Verify row counts match for all tables",
            "Rebuild indexes and run ANALYZE",
        ]
        commands = [
            f"# Plain-text dump (recommended for Lakebase)",
            f"pg_dump -h {source_ep} -U <user> -d {db_name} --no-owner --no-privileges > data.sql",
            f"psql -h {lakebase_ep} -U <user> -d {db_name} -f data.sql",
            f"",
            f"# Alternative: custom format (note --disable-triggers limitation below)",
            f"pg_dump -h {source_ep} -U <user> -d {db_name} -F c -f data.dump",
            f"pg_restore -h {lakebase_ep} -U <user> -d {db_name} -F c --no-owner --no-privileges data.dump",
        ]
        est_days = max(1, db.size_gb / 100)  # ~100 GB/day throughput estimate

    elif strategy in (MigrationStrategy.CDC_LOGICAL_REPLICATION, MigrationStrategy.HYBRID):
        steps = [
            "Perform initial bulk load using pg_dump/pg_restore",
            "Enable logical replication on Aurora (wal_level = logical)",
            "Create publication on Aurora for all tables",
            "Create subscription on Lakebase pointing to Aurora",
            "Monitor replication lag until near-zero",
            "Cut over application traffic to Lakebase",
            "Drop subscription after successful cutover",
        ]
        commands = [
            f"pg_dump -h {source_ep} -U <user> -d {db_name} -F c -f data.dump",
            f"pg_restore -h {lakebase_ep} -U <user> -d {db_name} -F c data.dump",
            "-- On Aurora:",
            "ALTER SYSTEM SET wal_level = logical;",
            f"CREATE PUBLICATION datasync FOR ALL TABLES;",
            "-- On Lakebase:",
            f"CREATE SUBSCRIPTION datasync_sub CONNECTION 'host={source_ep} dbname={db_name}' PUBLICATION datasync;",
        ]
        est_days = max(3, db.size_gb / 100 + 2)
    else:
        steps = [
            "Evaluate cross-engine migration tooling (AWS DMS, AWS SCT)",
            "Convert schema using Schema Conversion Tool",
            "Migrate data using DMS full load + CDC",
            "Validate data integrity post-migration",
        ]
        commands = []
        est_days = max(10, db.size_gb / 50 + 5)

    return MigrationPhase(
        phase_number=2,
        name="Data Migration",
        description=f"Strategy: {strategy.value}. Migrate data from Aurora to Lakebase with {'minimal' if strategy != MigrationStrategy.BULK_DUMP_RESTORE else 'scheduled'} downtime.",
        steps=steps,
        estimated_days=round(est_days, 1),
        commands=commands,
    )


def _phase_3_application(
    assessment: AssessmentResult,
    lakebase_ep: str,
    db_name: str,
) -> MigrationPhase:
    steps = [
        f"Update application connection string to Lakebase endpoint ({lakebase_ep})",
        "Switch authentication from IAM/password to Databricks OAuth tokens",
        "Update connection pooling configuration (replace RDS Proxy with app-side pooling if needed)",
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


def _phase_4_golive(assessment: AssessmentResult) -> MigrationPhase:
    steps = [
        "Enable High Availability (HA) with standby replicas",
        "Configure PITR backup with appropriate retention window",
        "Run load test at expected peak traffic",
        "Set up monitoring dashboards (Databricks AI/BI or LakebaseOps platform)",
        "Configure alerting thresholds for connections, cache hit ratio, deadlocks",
        "Schedule cutover during low-traffic window",
        "Execute cutover and monitor for 24-48 hours",
        "Decommission Aurora instance after validation period (recommended: 2 weeks)",
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
