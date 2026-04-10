"""
Migration Profile dataclasses for the Aurora-to-Lakebase Assessment Accelerator.

Captures source database metadata, assessment results, and migration blueprints
for evaluating external PostgreSQL databases for migration to Lakebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SourceEngine(Enum):
    AURORA_POSTGRESQL = "aurora-postgresql"
    AURORA_POSTGRESQL_IO = "aurora-postgresql-io"
    RDS_POSTGRESQL = "rds-postgresql"
    CLOUD_SQL_POSTGRESQL = "cloud-sql-postgresql"
    AZURE_POSTGRESQL = "azure-postgresql"
    SELF_MANAGED_POSTGRESQL = "self-managed-postgresql"
    ALLOYDB_POSTGRESQL = "alloydb-postgresql"
    SUPABASE_POSTGRESQL = "supabase-postgresql"
    AURORA_MYSQL = "aurora-mysql"
    DYNAMODB = "dynamodb"
    COSMOSDB_NOSQL = "cosmosdb-nosql"


ENGINE_KIND: dict[str, str] = {
    "dynamodb": "nosql",
    "cosmosdb-nosql": "nosql",
    "aurora-postgresql": "pg",
    "aurora-postgresql-io": "pg",
    "rds-postgresql": "pg",
    "cloud-sql-postgresql": "pg",
    "azure-postgresql": "pg",
    "self-managed-postgresql": "pg",
    "alloydb-postgresql": "pg",
    "supabase-postgresql": "pg",
    "aurora-mysql": "pg",
}


class ReadinessCategory(Enum):
    READY = "ready"
    READY_WITH_WORKAROUNDS = "ready_with_workarounds"
    NEEDS_REARCHITECTURE = "needs_rearchitecture"
    NOT_FEASIBLE = "not_feasible"


class BlockerSeverity(Enum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MigrationStrategy(Enum):
    BULK_DUMP_RESTORE = "bulk_dump_restore"
    CDC_LOGICAL_REPLICATION = "cdc_logical_replication"
    HYBRID = "hybrid"
    CROSS_ENGINE = "cross_engine"


class LakebaseTier(Enum):
    AUTOSCALING = "autoscaling"
    PROVISIONED = "provisioned"


# ── Source Database Profiling ──────────────────────────────────────────────


@dataclass
class ExtensionInfo:
    name: str
    version: str
    lakebase_supported: bool = False
    workaround: str = ""


@dataclass
class FunctionInfo:
    schema_name: str
    function_name: str
    language: str
    is_trigger_function: bool = False
    line_count: int = 0


@dataclass
class TriggerInfo:
    schema_name: str
    table_name: str
    trigger_name: str
    event: str
    timing: str
    function_name: str


@dataclass
class TableProfile:
    schema_name: str
    table_name: str
    row_count: int = 0
    size_bytes: int = 0
    index_count: int = 0
    has_triggers: bool = False
    has_foreign_keys: bool = False
    column_count: int = 0


@dataclass
class WorkloadProfile:
    total_queries: int = 0
    total_calls: int = 0
    reads_pct: float = 0.0
    writes_pct: float = 0.0
    avg_qps: float = 0.0
    peak_qps: float = 0.0
    avg_tps: float = 0.0
    p99_latency_ms: float = 0.0
    top_queries: list = field(default_factory=list)
    hot_tables: list = field(default_factory=list)
    connection_count_avg: int = 0
    connection_count_peak: int = 0
    workload_source: str = "observed"  # "observed" | "heuristic" | "mock"


@dataclass
class DatabaseProfile:
    name: str
    size_bytes: int = 0
    size_gb: float = 0.0
    table_count: int = 0
    schema_count: int = 0
    schemas: list[str] = field(default_factory=list)
    tables: list[TableProfile] = field(default_factory=list)
    extensions: list[ExtensionInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    triggers: list[TriggerInfo] = field(default_factory=list)
    sequence_count: int = 0
    materialized_view_count: int = 0
    custom_type_count: int = 0
    foreign_key_count: int = 0
    has_logical_replication: bool = False
    replication_slots: list[str] = field(default_factory=list)
    pg_version: str = ""
    rls_policy_count: int = 0
    partition_strategies: list[str] = field(default_factory=list)
    event_trigger_count: int = 0
    large_object_count: int = 0
    exclusion_constraint_count: int = 0
    custom_aggregate_count: int = 0
    non_default_collation_count: int = 0
    # DynamoDB-specific (None for PostgreSQL engines)
    billing_mode: str | None = None
    gsi_count: int | None = None
    lsi_count: int | None = None
    streams_enabled: bool | None = None
    ttl_enabled: bool | None = None
    pitr_enabled: bool | None = None
    global_table_regions: list[str] | None = None
    item_size_avg_bytes: int | None = None
    dynamo_table_details: list[dict] | None = None
    # CosmosDB-specific (None for non-CosmosDB engines)
    cosmos_throughput_mode: str | None = None
    cosmos_ru_per_sec: int | None = None
    cosmos_partition_key_paths: list[str] | None = None
    cosmos_consistency_level: str | None = None
    cosmos_change_feed_enabled: bool | None = None
    cosmos_change_feed_mode: str | None = None  # "LatestVersion" | "AllVersionsAndDeletes"
    cosmos_multi_region_writes: bool | None = None
    cosmos_regions: list[str] | None = None
    cosmos_container_details: list[dict] | None = None
    cosmos_autoscale_max_ru: int | None = None
    cosmos_backup_policy: str | None = None


# ── Assessment Results ─────────────────────────────────────────────────────


@dataclass
class Blocker:
    category: str
    severity: BlockerSeverity
    description: str
    workaround: str = ""
    effort_days: float = 0.0


@dataclass
class DimensionScore:
    dimension: str
    score: float
    max_score: float
    weight: float
    details: str = ""
    blockers: list[Blocker] = field(default_factory=list)


CU_TO_MAX_CONNECTIONS: dict[float, int] = {
    0.5: 104, 1: 209, 2: 419, 3: 629, 4: 839, 5: 1049,
    6: 1258, 7: 1468, 8: 1678, 9: 1888, 10: 2098, 12: 2517,
    14: 2937, 16: 3357, 24: 4000, 28: 4000, 32: 4000,
}


def max_connections_for_cu(cu: float) -> int:
    """Return the max_connections for a given CU size based on official specs."""
    if cu in CU_TO_MAX_CONNECTIONS:
        return CU_TO_MAX_CONNECTIONS[cu]
    best = 104
    for cu_val, conns in sorted(CU_TO_MAX_CONNECTIONS.items()):
        if cu_val <= cu:
            best = conns
    return best


@dataclass
class EnvironmentSizing:
    """Sizing recommendation for a specific environment (dev/staging/prod)."""
    env: str
    cu_min: float
    cu_max: float
    scale_to_zero: bool
    autoscaling: bool
    max_connections: int
    ram_gb: float = 0.0
    estimated_monthly_cost_usd: float | None = None
    notes: str = ""


@dataclass
class AssessmentResult:
    overall_score: float = 0.0
    category: ReadinessCategory = ReadinessCategory.NOT_FEASIBLE
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported_extensions: list[str] = field(default_factory=list)
    supported_extensions: list[str] = field(default_factory=list)
    estimated_effort_days: float = 0.0
    recommended_tier: LakebaseTier = LakebaseTier.AUTOSCALING
    recommended_cu_min: int = 1
    recommended_cu_max: int = 8
    sizing_by_env: list[EnvironmentSizing] = field(default_factory=list)


# ── Migration Blueprint ────────────────────────────────────────────────────


@dataclass
class MigrationPhase:
    phase_number: int
    name: str
    description: str
    steps: list[str] = field(default_factory=list)
    estimated_days: float = 0.0
    commands: list[str] = field(default_factory=list)


@dataclass
class MigrationBlueprint:
    strategy: MigrationStrategy = MigrationStrategy.BULK_DUMP_RESTORE
    phases: list[MigrationPhase] = field(default_factory=list)
    total_estimated_days: float = 0.0
    risk_level: str = "medium"
    prerequisites: list[str] = field(default_factory=list)
    post_migration_checks: list[str] = field(default_factory=list)
    rollback_plan: str = ""


# ── Top-Level Migration Profile ────────────────────────────────────────────


@dataclass
class MigrationProfile:
    """
    Top-level profile capturing everything about a migration assessment.
    Created by connect_and_discover, enriched by profile_workload,
    scored by compute_readiness_score, and planned by generate_migration_blueprint.
    """

    profile_id: str = ""
    source_engine: SourceEngine = SourceEngine.AURORA_POSTGRESQL
    source_endpoint: str = ""
    source_version: str = ""
    source_region: str = ""
    databases: list[DatabaseProfile] = field(default_factory=list)
    workload: WorkloadProfile | None = None
    assessment: AssessmentResult | None = None
    blueprint: MigrationBlueprint | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_size_gb(self) -> float:
        return sum(db.size_gb for db in self.databases)

    @property
    def total_tables(self) -> int:
        return sum(db.table_count for db in self.databases)

    @property
    def is_assessed(self) -> bool:
        return self.assessment is not None

    @property
    def is_planned(self) -> bool:
        return self.blueprint is not None
