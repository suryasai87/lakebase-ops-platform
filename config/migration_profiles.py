"""
Migration Profile dataclasses for the Aurora-to-Lakebase Assessment Accelerator.

Captures source database metadata, assessment results, and migration blueprints
for evaluating external PostgreSQL databases for migration to Lakebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SourceEngine(Enum):
    AURORA_POSTGRESQL = "aurora-postgresql"
    RDS_POSTGRESQL = "rds-postgresql"
    CLOUD_SQL_POSTGRESQL = "cloud-sql-postgresql"
    AZURE_POSTGRESQL = "azure-postgresql"
    SELF_MANAGED_POSTGRESQL = "self-managed-postgresql"
    AURORA_MYSQL = "aurora-mysql"


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
    workload: Optional[WorkloadProfile] = None
    assessment: Optional[AssessmentResult] = None
    blueprint: Optional[MigrationBlueprint] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
