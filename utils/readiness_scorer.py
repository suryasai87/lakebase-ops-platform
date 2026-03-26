"""
Lakebase Readiness Scoring Engine

Pure logic module (no DB connections) that evaluates a profiled source database
against Lakebase constraints and produces a readiness score.

Scoring dimensions (weighted):
  - Storage compatibility (20%)
  - Extension compatibility (20%)
  - Performance fit (15%)
  - Schema complexity (15%)
  - Replication & HA (15%)
  - Operational readiness (15%)

"""

from __future__ import annotations

from config.migration_profiles import (
    ENGINE_KIND,
    AssessmentResult,
    Blocker,
    BlockerSeverity,
    DatabaseProfile,
    DimensionScore,
    LakebaseTier,
    ReadinessCategory,
    WorkloadProfile,
)

# Lakebase constraints
LAKEBASE_MAX_STORAGE_AUTOSCALING_GB = 8 * 1024  # 8 TB
LAKEBASE_MAX_STORAGE_PROVISIONED_GB = 2 * 1024   # 2 TB
LAKEBASE_MAX_CONNECTIONS = 4000
LAKEBASE_MAX_QPS = 100_000
LAKEBASE_MAX_SUSTAINED_TPS = 5000
LAKEBASE_MAX_CU_AUTOSCALING = 32
LAKEBASE_MAX_CU_PROVISIONED = 112

LAKEBASE_SUPPORTED_EXTENSIONS = {
    "pg_stat_statements", "pgvector", "postgis", "pg_trgm", "pgcrypto",
    "pg_hint_plan", "pg_prewarm", "uuid-ossp", "hstore", "citext", "ltree",
    "intarray", "tablefunc", "earthdistance", "cube", "fuzzystrmatch",
    "unaccent", "btree_gin", "btree_gist", "pg_graphql", "pg_jsonschema",
    "databricks_auth", "vector", "postgis_topology", "postgis_raster",
    "address_standardizer", "pg_visibility", "pgrowlocks", "pg_buffercache",
    "sslinfo", "xml2", "dict_int", "dict_xsyn", "pg_surgery", "bool_plperl",
    "jsonb_plperl", "hstore_plperl", "seg", "isn", "lo", "tcn",
    "tsm_system_rows", "tsm_system_time", "bloom",
}

EXTENSION_WORKAROUNDS = {
    # AWS-specific
    "aws_s3": "Use Databricks SDK or Unity Catalog for S3 access",
    "aws_lambda": "Use Databricks serverless compute or external API calls",
    # GCP-specific
    "google_ml_integration": "Not available; use Databricks Foundation Model API for ML inference",
    "pg_squeeze": "Use VACUUM FULL + REINDEX CONCURRENTLY (requires brief lock)",
    # Azure-specific
    "azure_storage": "Replace with Databricks SDK or Unity Catalog for Azure Blob access",
    "azure_ai": "Replace with Databricks Foundation Model API for AI services",
    "age": "Not supported; use GraphFrames or Delta Lake for graph workloads",
    # Scheduling / maintenance
    "pg_cron": "Replace with Databricks Jobs for scheduled tasks",
    "pg_partman": "Manage partitions manually or via Databricks Jobs notebooks",
    "pg_repack": "Use VACUUM FULL + REINDEX CONCURRENTLY (requires brief lock)",
    # Replication / CDC
    "pglogical": "No logical replication in Lakebase; use Lakeflow Connect or application-level sync",
    "wal2json": "No WAL-based CDC; use Lakeflow Connect for change capture",
    "decoderbufs": "No WAL-based CDC; use Lakeflow Connect",
    # Auditing / monitoring
    "pgaudit": "Use PostgreSQL system views (pg_stat_activity, pg_stat_statements) or Databricks audit logs",
    "pg_stat_kcache": "Not available; use pg_stat_statements for query-level metrics",
    "pg_wait_sampling": "Not available; use pg_stat_activity wait events",
    "pg_qualstats": "Not available; use EXPLAIN ANALYZE for query plan analysis",
    # Distributed / scale-out
    "citus": "No distributed/sharded tables in Lakebase",
    "timescaledb": "Not available; use standard partitioning or Delta Lake for time-series",
    # Connection pooling
    "pgbouncer": "No built-in connection pooling; use application-side pooling",
    # Trusted Language Extensions
    "pg_tle": "Custom Trusted Language Extensions must be evaluated individually",
    # Supabase-specific
    "pgjwt": "Implement JWT validation in application layer or use Databricks OAuth",
    "supautils": "Supabase utility functions not available; replicate needed logic in application code",
}

DYNAMODB_FEATURE_SUPPORT: dict[str, str] = {
    "Transactions (TransactWriteItems)": "supported",
    "Conditional writes": "supported",
    "Batch operations (BatchWriteItem)": "supported",
    "TTL (time-to-live)": "supported",
    "Encryption at rest": "supported",
    "DynamoDB Streams": "workaround",
    "Global Tables (multi-region)": "workaround",
    "DAX (DynamoDB Accelerator)": "unsupported",
    "PartiQL over DynamoDB": "workaround",
    "On-demand capacity scaling": "workaround",
    "Single-table design patterns": "workaround",
}

DYNAMODB_FEATURE_WORKAROUNDS: dict[str, str] = {
    "DynamoDB Streams": "Use Lakeflow Connect CDC, application-level triggers, or pg_notify for change capture",
    "Global Tables (multi-region)": "Use single-region Lakebase primary with read replicas or DR failover",
    "DAX (DynamoDB Accelerator)": "Not available as managed service; use application-level caching (Redis, Memcached) or materialized views",
    "PartiQL over DynamoDB": "Rewrite PartiQL queries to standard PostgreSQL SQL",
    "On-demand capacity scaling": "Lakebase uses CU-based autoscaling (0.5-32 CU); capacity planning required",
    "Single-table design patterns": "Decompose into normalized relational tables; use JSONB for flexible attributes",
}


def compute_readiness_score(
    db_profile: DatabaseProfile,
    workload: WorkloadProfile | None = None,
    source_engine: str = "",
) -> AssessmentResult:
    """
    Compute a Lakebase readiness score for a profiled database.
    Returns an AssessmentResult with overall score, category, and blockers.
    """
    is_nosql = ENGINE_KIND.get(source_engine) == "nosql"
    dimensions = []
    all_blockers = []
    all_warnings = []
    unsupported_exts = []
    supported_exts = []

    # ── Dimension 1: Storage (weight 0.20) ──────────────────────────────

    storage_score, storage_blockers, storage_details = _score_storage(db_profile)
    dimensions.append(DimensionScore(
        dimension="storage",
        score=storage_score,
        max_score=100,
        weight=0.20,
        details=storage_details,
        blockers=storage_blockers,
    ))
    all_blockers.extend(storage_blockers)

    # ── Dimension 2: Extensions (weight 0.20) ───────────────────────────

    if is_nosql:
        ext_score, ext_blockers, ext_warnings, sup, unsup = _score_dynamodb_features(db_profile)
    else:
        ext_score, ext_blockers, ext_warnings, sup, unsup = _score_extensions(db_profile)
    dimensions.append(DimensionScore(
        dimension="extensions",
        score=ext_score,
        max_score=100,
        weight=0.20,
        details=f"{len(sup)} supported, {len(unsup)} unsupported",
        blockers=ext_blockers,
    ))
    all_blockers.extend(ext_blockers)
    all_warnings.extend(ext_warnings)
    supported_exts = sup
    unsupported_exts = unsup

    # ── Dimension 3: Performance Fit (weight 0.15) ──────────────────────

    perf_score, perf_blockers, perf_details = _score_performance(workload)
    dimensions.append(DimensionScore(
        dimension="performance",
        score=perf_score,
        max_score=100,
        weight=0.15,
        details=perf_details,
        blockers=perf_blockers,
    ))
    all_blockers.extend(perf_blockers)

    # ── Dimension 4: Schema Complexity (weight 0.15) ────────────────────

    if is_nosql:
        complexity_score, complexity_blockers, complexity_warnings, complexity_details = _score_nosql_complexity(db_profile)
    else:
        complexity_score, complexity_blockers, complexity_warnings, complexity_details = _score_complexity(db_profile)
    dimensions.append(DimensionScore(
        dimension="schema_complexity",
        score=complexity_score,
        max_score=100,
        weight=0.15,
        details=complexity_details,
        blockers=complexity_blockers,
    ))
    all_blockers.extend(complexity_blockers)
    all_warnings.extend(complexity_warnings)

    # ── Dimension 5: Replication & HA (weight 0.15) ─────────────────────

    if is_nosql:
        repl_score, repl_blockers, repl_details = _score_nosql_replication(db_profile)
    else:
        repl_score, repl_blockers, repl_details = _score_replication(db_profile)
    dimensions.append(DimensionScore(
        dimension="replication_ha",
        score=repl_score,
        max_score=100,
        weight=0.15,
        details=repl_details,
        blockers=repl_blockers,
    ))
    all_blockers.extend(repl_blockers)

    # ── Dimension 6: Operational Readiness (weight 0.15) ────────────────

    if is_nosql:
        ops_score, ops_warnings, ops_details = _score_nosql_operational(db_profile, workload)
    else:
        ops_score, ops_warnings, ops_details = _score_operational(db_profile, workload)
    dimensions.append(DimensionScore(
        dimension="operational",
        score=ops_score,
        max_score=100,
        weight=0.15,
        details=ops_details,
    ))
    all_warnings.extend(ops_warnings)

    # ── Aggregate ───────────────────────────────────────────────────────

    overall = sum(d.score * d.weight for d in dimensions)
    has_blockers = any(b.severity == BlockerSeverity.BLOCKER for b in all_blockers)
    has_high = any(b.severity == BlockerSeverity.HIGH for b in all_blockers)

    if has_blockers:
        category = ReadinessCategory.NOT_FEASIBLE
    elif has_high or overall < 40:
        category = ReadinessCategory.NEEDS_REARCHITECTURE
    elif overall < 70:
        category = ReadinessCategory.READY_WITH_WORKAROUNDS
    else:
        category = ReadinessCategory.READY

    if is_nosql:
        effort = _estimate_effort_nosql(db_profile, all_blockers)
    else:
        effort = _estimate_effort(db_profile, all_blockers, unsupported_exts)
    tier, cu_min, cu_max = _recommend_sizing(db_profile, workload)

    return AssessmentResult(
        overall_score=round(overall, 1),
        category=category,
        dimension_scores=dimensions,
        blockers=all_blockers,
        warnings=all_warnings,
        unsupported_extensions=unsupported_exts,
        supported_extensions=supported_exts,
        estimated_effort_days=effort,
        recommended_tier=tier,
        recommended_cu_min=cu_min,
        recommended_cu_max=cu_max,
    )


# ── Dimension Scorers ──────────────────────────────────────────────────────


def _score_storage(db: DatabaseProfile) -> tuple[float, list[Blocker], str]:
    blockers = []
    size_gb = db.size_gb

    if size_gb > LAKEBASE_MAX_STORAGE_AUTOSCALING_GB:
        blockers.append(Blocker(
            category="storage",
            severity=BlockerSeverity.BLOCKER,
            description=f"Database size ({size_gb:.1f} GB) exceeds Lakebase max (8 TB)",
        ))
        return 0, blockers, f"{size_gb:.1f} GB exceeds 8 TB limit"

    if size_gb > LAKEBASE_MAX_STORAGE_PROVISIONED_GB:
        ratio = size_gb / LAKEBASE_MAX_STORAGE_AUTOSCALING_GB
        score = max(0, 100 * (1 - ratio))
        return score, blockers, f"{size_gb:.1f} GB - requires Autoscaling tier"

    ratio = size_gb / LAKEBASE_MAX_STORAGE_PROVISIONED_GB
    score = max(0, 100 * (1 - ratio * 0.5))
    return round(score, 1), blockers, f"{size_gb:.1f} GB - fits both tiers"


def _score_dynamodb_features(db: DatabaseProfile) -> tuple[float, list[Blocker], list[str], list[str], list[str]]:
    """Score DynamoDB feature compatibility with Lakebase."""
    blockers = []
    warnings = []
    supported = []
    unsupported = []
    score = 100

    for feature, status in DYNAMODB_FEATURE_SUPPORT.items():
        if status == "supported":
            supported.append(feature)
        elif status == "workaround":
            wk = DYNAMODB_FEATURE_WORKAROUNDS.get(feature, "Evaluate manually")
            warnings.append(f"'{feature}' requires workaround: {wk}")
            unsupported.append(feature)
            blockers.append(Blocker(
                category="feature_compatibility",
                severity=BlockerSeverity.MEDIUM,
                description=f"DynamoDB feature '{feature}' not natively available in Lakebase",
                workaround=wk,
                effort_days=2,
            ))
            score -= 8
        else:
            unsupported.append(feature)
            blockers.append(Blocker(
                category="feature_compatibility",
                severity=BlockerSeverity.HIGH,
                description=f"DynamoDB feature '{feature}' not supported in Lakebase",
                workaround=DYNAMODB_FEATURE_WORKAROUNDS.get(feature, "Evaluate manually"),
                effort_days=3,
            ))
            score -= 15

    if db.streams_enabled:
        score -= 5
    if db.global_table_regions and len(db.global_table_regions) > 1:
        score -= 15
        blockers.append(Blocker(
            category="feature_compatibility",
            severity=BlockerSeverity.HIGH,
            description=f"Global Tables active in {len(db.global_table_regions)} regions - multi-region not supported in Lakebase",
            workaround="Consolidate to single-region Lakebase with DR strategy",
            effort_days=5,
        ))

    return max(0, round(score, 1)), blockers, warnings, supported, unsupported


def _score_nosql_complexity(db: DatabaseProfile) -> tuple[float, list[Blocker], list[str], str]:
    """Score DynamoDB schema complexity for relational conversion."""
    blockers = []
    warnings = []
    score = 100

    gsi_count = db.gsi_count or 0
    lsi_count = db.lsi_count or 0

    if gsi_count > 10:
        score -= 15
        warnings.append(f"{gsi_count} GSIs require careful index design in PostgreSQL")
    elif gsi_count > 5:
        score -= 5

    if lsi_count > 3:
        score -= 5

    if db.item_size_avg_bytes and db.item_size_avg_bytes > 100_000:
        score -= 10
        warnings.append(f"Average item size {db.item_size_avg_bytes:,} bytes - large items may need JSONB + TOAST tuning")

    # Penalty for NoSQL-to-relational schema redesign overhead (always applies for cross-engine migration)
    score -= 15

    details_parts = []
    if gsi_count:
        details_parts.append(f"{gsi_count} GSIs")
    if lsi_count:
        details_parts.append(f"{lsi_count} LSIs")
    if db.billing_mode:
        details_parts.append(f"billing: {db.billing_mode}")
    if db.item_size_avg_bytes:
        details_parts.append(f"avg item: {db.item_size_avg_bytes:,} bytes")

    details = ", ".join(details_parts) if details_parts else "Standard NoSQL schema"
    return max(0, round(score, 1)), blockers, warnings, details


def _score_nosql_replication(db: DatabaseProfile) -> tuple[float, list[Blocker], str]:
    """Score DynamoDB Streams and Global Tables for migration impact."""
    blockers = []
    score = 100

    if db.streams_enabled:
        blockers.append(Blocker(
            category="replication",
            severity=BlockerSeverity.MEDIUM,
            description="DynamoDB Streams enabled - downstream consumers need migration to Lakebase CDC or application triggers",
            workaround="Use Lakeflow Connect or application-level event publishing",
            effort_days=3,
        ))
        score -= 15

    if not db.pitr_enabled:
        blockers.append(Blocker(
            category="replication",
            severity=BlockerSeverity.MEDIUM,
            description="PITR not enabled - required for zero-impact DynamoDB Export to S3",
            workaround="Enable PITR before starting migration; required for Export to S3",
            effort_days=0.5,
        ))
        score -= 10

    regions = db.global_table_regions or []
    if len(regions) > 1:
        score -= 20

    details = f"Streams: {db.streams_enabled}, PITR: {db.pitr_enabled}, Global regions: {len(regions)}"
    return max(0, round(score, 1)), blockers, details


def _score_nosql_operational(db: DatabaseProfile, workload: WorkloadProfile | None) -> tuple[float, list[str], str]:
    """Score DynamoDB operational dependencies for migration."""
    warnings = []
    score = 100

    if db.billing_mode == "provisioned":
        warnings.append("Provisioned capacity mode requires capacity planning for Lakebase CU sizing")
        score -= 5

    if db.ttl_enabled:
        warnings.append("DynamoDB TTL must be replaced with scheduled DELETE jobs or partition drops on Lakebase")
        score -= 5

    # Baseline penalty for SDK-to-SQL rewrite and operational tooling changes
    score -= 10

    if workload and workload.avg_tps > LAKEBASE_MAX_SUSTAINED_TPS:
        warnings.append(f"Write throughput ({workload.avg_tps:,.0f} TPS) may exceed Lakebase sustained capacity")
        score -= 15

    details = f"{len(warnings)} operational considerations" if warnings else "No operational concerns"
    return max(0, round(score, 1)), warnings, details


def _estimate_effort_nosql(db: DatabaseProfile, blockers: list[Blocker]) -> float:
    """Estimate migration effort for NoSQL-to-relational migration."""
    base_days = 15.0
    base_days += sum(b.effort_days for b in blockers)
    if db.table_count > 20:
        base_days += 5
    if db.size_gb > 500:
        base_days += 10
    gsi_count = db.gsi_count or 0
    if gsi_count > 5:
        base_days += gsi_count * 0.5
    return round(base_days, 1)


def _score_extensions(db: DatabaseProfile) -> tuple[float, list[Blocker], list[str], list[str], list[str]]:
    blockers = []
    warnings = []
    supported = []
    unsupported = []

    if not db.extensions:
        return 100, blockers, warnings, supported, unsupported

    for ext in db.extensions:
        ext_name = ext.name.lower()
        if ext_name in LAKEBASE_SUPPORTED_EXTENSIONS:
            supported.append(ext_name)
        else:
            unsupported.append(ext_name)
            workaround = EXTENSION_WORKAROUNDS.get(ext_name, "Evaluate manually")
            severity = BlockerSeverity.HIGH if ext_name in ("pglogical", "citus", "timescaledb") else BlockerSeverity.MEDIUM
            blockers.append(Blocker(
                category="extension",
                severity=severity,
                description=f"Extension '{ext_name}' not supported in Lakebase",
                workaround=workaround,
                effort_days=2 if severity == BlockerSeverity.HIGH else 1,
            ))
            warnings.append(f"Extension '{ext_name}' requires workaround: {workaround}")

    total = len(supported) + len(unsupported)
    score = (len(supported) / total) * 100 if total > 0 else 100
    return round(score, 1), blockers, warnings, supported, unsupported


def _score_performance(workload: WorkloadProfile | None) -> tuple[float, list[Blocker], str]:
    if workload is None:
        return 75, [], "No workload data available - defaulting to 75"

    blockers = []
    score = 100

    if workload.avg_qps > LAKEBASE_MAX_QPS:
        blockers.append(Blocker(
            category="performance",
            severity=BlockerSeverity.BLOCKER,
            description=f"QPS ({workload.avg_qps:,.0f}) exceeds Lakebase max ({LAKEBASE_MAX_QPS:,})",
        ))
        score = 0
    elif workload.avg_qps > LAKEBASE_MAX_QPS * 0.7:
        score -= 30

    if workload.avg_tps > LAKEBASE_MAX_SUSTAINED_TPS:
        blockers.append(Blocker(
            category="performance",
            severity=BlockerSeverity.HIGH,
            description=f"Sustained TPS ({workload.avg_tps:,.0f}) exceeds recommended max ({LAKEBASE_MAX_SUSTAINED_TPS:,})",
            workaround="Consider partitioning workload or keeping high-TPS tables on Aurora",
        ))
        score -= 40

    if workload.connection_count_peak > LAKEBASE_MAX_CONNECTIONS:
        blockers.append(Blocker(
            category="performance",
            severity=BlockerSeverity.HIGH,
            description=f"Peak connections ({workload.connection_count_peak}) exceed Lakebase max ({LAKEBASE_MAX_CONNECTIONS})",
            workaround="Use application-side connection pooling (PgBouncer, HikariCP)",
            effort_days=2,
        ))
        score -= 20

    details = f"QPS: {workload.avg_qps:,.0f}, TPS: {workload.avg_tps:,.0f}, Connections: {workload.connection_count_peak}"
    return max(0, round(score, 1)), blockers, details


def _score_complexity(db: DatabaseProfile) -> tuple[float, list[Blocker], list[str], str]:
    blockers = []
    warnings = []
    score = 100

    plpgsql_functions = [f for f in db.functions if f.language == "plpgsql"]
    heavy_plpgsql = len(plpgsql_functions) > 50 or any(f.line_count > 200 for f in plpgsql_functions)

    if heavy_plpgsql:
        blockers.append(Blocker(
            category="complexity",
            severity=BlockerSeverity.HIGH,
            description=f"Heavy PL/pgSQL usage ({len(plpgsql_functions)} functions) - may require significant refactoring",
            workaround="Evaluate which functions are critical; consider moving logic to application layer",
            effort_days=10,
        ))
        score -= 40

    if len(db.triggers) > 20:
        score -= 15
    elif len(db.triggers) > 5:
        score -= 5

    if db.materialized_view_count > 10:
        score -= 10

    if db.custom_type_count > 20:
        score -= 10

    if db.event_trigger_count > 0:
        blockers.append(Blocker(
            category="event_triggers",
            severity=BlockerSeverity.BLOCKER,
            description=f"{db.event_trigger_count} event trigger(s) detected - not supported on Lakebase",
            workaround="Remove event triggers; replicate DDL-audit logic via application-layer hooks or Databricks audit logs",
            effort_days=3,
        ))
        score -= 30

    if db.large_object_count > 0:
        warnings.append(
            f"{db.large_object_count} large object(s) detected - verify migration with pg_dump; "
            "Lakebase supports lo extension but large objects may not restore cleanly"
        )
        score -= 5

    if db.custom_aggregate_count > 0:
        warnings.append(
            f"{db.custom_aggregate_count} custom aggregate(s) detected - "
            "should migrate via pg_dump but verify execution on Lakebase"
        )

    if db.exclusion_constraint_count > 0:
        warnings.append(
            f"{db.exclusion_constraint_count} exclusion constraint(s) detected - "
            "requires btree_gist extension (supported on Lakebase)"
        )

    if db.rls_policy_count > 0:
        warnings.append(
            f"{db.rls_policy_count} RLS policy/policies detected - "
            "supported on Lakebase; verify enforcement after migration"
        )

    if db.non_default_collation_count > 0:
        warnings.append(
            f"{db.non_default_collation_count} column(s) with non-default collation - "
            "verify ICU collation support on Lakebase"
        )
        score -= 5

    parts = []
    if plpgsql_functions:
        parts.append(f"{len(plpgsql_functions)} PL/pgSQL functions")
    if db.triggers:
        parts.append(f"{len(db.triggers)} triggers")
    if db.materialized_view_count:
        parts.append(f"{db.materialized_view_count} materialized views")
    if db.event_trigger_count:
        parts.append(f"{db.event_trigger_count} event triggers")
    if db.large_object_count:
        parts.append(f"{db.large_object_count} large objects")

    details = ", ".join(parts) if parts else "Low complexity"
    return max(0, round(score, 1)), blockers, warnings, details


def _score_replication(db: DatabaseProfile) -> tuple[float, list[Blocker], str]:
    blockers = []
    score = 100

    if db.has_logical_replication:
        blockers.append(Blocker(
            category="replication",
            severity=BlockerSeverity.HIGH,
            description="Source uses logical replication - Lakebase does not support logical replication as publisher",
            workaround="Redesign data distribution using Lakeflow Connect, Delta Lake sync, or application-level routing",
            effort_days=5,
        ))
        score -= 40

    if db.replication_slots:
        score -= 10
        for slot in db.replication_slots:
            blockers.append(Blocker(
                category="replication",
                severity=BlockerSeverity.MEDIUM,
                description=f"Replication slot '{slot}' - downstream consumers need alternative data source",
                workaround="Route consumers to Delta Lake via Synced Tables or Lakeflow Connect",
                effort_days=2,
            ))

    details = "No replication dependencies" if score == 100 else f"Logical replication: {db.has_logical_replication}, Slots: {len(db.replication_slots)}"
    return max(0, round(score, 1)), blockers, details


def _score_operational(db: DatabaseProfile, workload: WorkloadProfile | None) -> tuple[float, list[str], str]:
    warnings = []
    score = 100

    ext_names = {e.name.lower() for e in db.extensions}

    if "pg_cron" in ext_names:
        warnings.append("pg_cron jobs must be migrated to Databricks Jobs")
        score -= 10

    aws_extensions = [n for n in ext_names if n.startswith("aws_")]
    if aws_extensions:
        warnings.append(f"AWS-specific extensions ({', '.join(sorted(aws_extensions))}) need replacement")
        score -= 5 * len(aws_extensions)

    gcp_extensions = [n for n in ext_names if n.startswith("google_")]
    if gcp_extensions:
        warnings.append(f"GCP-specific extensions ({', '.join(sorted(gcp_extensions))}) need replacement with Databricks equivalents")
        score -= 5 * len(gcp_extensions)

    azure_extensions = [n for n in ext_names if n.startswith("azure_")]
    if azure_extensions:
        warnings.append(f"Azure-specific extensions ({', '.join(sorted(azure_extensions))}) need replacement with Databricks equivalents")
        score -= 5 * len(azure_extensions)

    if "age" in ext_names:
        warnings.append("Apache AGE graph extension not supported - evaluate GraphFrames or Delta Lake for graph workloads")
        score -= 5

    if "timescaledb" in ext_names:
        warnings.append("TimescaleDB hypertables must be converted to standard partitioned tables or Delta Lake time-series")
        score -= 10

    if "citus" in ext_names:
        warnings.append("Citus distributed tables must be consolidated - Lakebase does not support sharding")
        score -= 10

    if "pglogical" in ext_names:
        warnings.append("pglogical replication must be replaced with Lakeflow Connect or application-level sync")
        score -= 5

    if workload and workload.connection_count_avg > 500:
        warnings.append("High average connection count - consider connection pooling strategy")
        score -= 5

    details = f"{len(warnings)} operational considerations" if warnings else "No operational concerns"
    return max(0, round(score, 1)), warnings, details


# ── Helpers ────────────────────────────────────────────────────────────────


def _estimate_effort(db: DatabaseProfile, blockers: list[Blocker], unsupported_exts: list[str]) -> float:
    base_days = 5.0  # Minimum for any migration

    base_days += sum(b.effort_days for b in blockers)
    base_days += len(unsupported_exts) * 0.5

    if db.table_count > 100:
        base_days += 3
    if db.size_gb > 500:
        base_days += 5
    if len(db.functions) > 20:
        base_days += 5

    return round(base_days, 1)


def _recommend_sizing(
    db: DatabaseProfile,
    workload: WorkloadProfile | None,
) -> tuple[LakebaseTier, int, int]:
    size_gb = db.size_gb

    if size_gb > LAKEBASE_MAX_STORAGE_PROVISIONED_GB:
        tier = LakebaseTier.AUTOSCALING
    else:
        tier = LakebaseTier.AUTOSCALING  # Default recommendation

    if workload and workload.connection_count_peak > 0:
        if workload.connection_count_peak <= 200:
            cu_min, cu_max = 1, 4
        elif workload.connection_count_peak <= 800:
            cu_min, cu_max = 2, 8
        elif workload.connection_count_peak <= 1600:
            cu_min, cu_max = 4, 16
        else:
            cu_min, cu_max = 8, 32
    else:
        if size_gb < 10:
            cu_min, cu_max = 1, 4
        elif size_gb < 100:
            cu_min, cu_max = 2, 8
        elif size_gb < 500:
            cu_min, cu_max = 4, 16
        else:
            cu_min, cu_max = 8, 32

    if tier == LakebaseTier.PROVISIONED:
        cu_min = max(cu_min, 1)
        cu_max = min(cu_max, 8)

    return tier, cu_min, cu_max
