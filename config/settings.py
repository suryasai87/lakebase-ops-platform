"""
LakebaseOps Platform Configuration
Centralized settings for all agents, jobs, and utilities.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Environment(Enum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class BranchType(Enum):
    DEFAULT = "default"
    PROTECTED = "protected"
    EPHEMERAL = "ephemeral"
    POINT_IN_TIME = "point_in_time"


class BranchingPattern(Enum):
    SIMPLE_DEV_PROD = "simple_dev_prod"
    MULTI_ENV_PIPELINE = "multi_env_pipeline"
    PER_DEVELOPER = "per_developer"
    CICD_EPHEMERAL = "cicd_ephemeral"
    MULTI_TENANT_PROJECT = "multi_tenant_project"
    MULTI_TENANT_SCHEMA = "multi_tenant_schema"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RemediationRisk(Enum):
    LOW = "low"      # Auto-execute: vacuum, idle connection kill
    MEDIUM = "medium" # Requires approval: index drop, parameter change
    HIGH = "high"     # Human only: VACUUM FULL, schema migration to prod


@dataclass
class LakebaseProjectConfig:
    """Configuration for a Lakebase project."""
    project_name: str
    domain: str
    environment: Environment
    branching_pattern: BranchingPattern
    catalog: str = "ops_catalog"
    schema: str = "lakebase_ops"
    max_branches: int = 10
    oauth_token_ttl_seconds: int = 3600
    token_refresh_at_seconds: int = 3000  # Refresh at 50 min (before 1h expiry)


@dataclass
class BranchConfig:
    """Configuration for a Lakebase branch."""
    name: str
    branch_type: BranchType
    source_branch: str = "production"
    ttl_seconds: Optional[int] = None
    is_protected: bool = False
    auto_archive_idle_hours: Optional[int] = None


# Default TTL policies (from Enterprise Design Guide)
TTL_POLICIES = {
    "ci": 14400,          # 4 hours
    "hotfix": 86400,      # 24 hours
    "perf": 172800,       # 48 hours
    "feat": 604800,       # 7 days
    "dev": 604800,        # 7 days
    "demo": 1209600,      # 14 days
    "qa": 1209600,        # 14 days
    "audit": 2592000,     # 30 days
    "ai-agent": 3600,     # 1 hour
    "production": None,   # No TTL (protected)
    "staging": None,      # No TTL (protected)
}

# Branch naming conventions (RFC 1123 compliant)
BRANCH_NAMING = {
    "ci": "ci-pr-{number}",
    "hotfix": "hotfix-{ticket_id}",
    "perf": "perf-{test_name}",
    "feat": "feat-{description}",
    "dev": "dev-{firstname}",
    "demo": "demo-{customer}",
    "qa": "qa-release-{version}",
    "audit": "audit-{date}",
    "ai-agent": "ai-agent-test",
}


@dataclass
class AlertThresholds:
    """Performance alerting thresholds from PRD FR-04."""
    # Buffer cache hit ratio
    cache_hit_warning: float = 0.99
    cache_hit_critical: float = 0.95
    # Connection utilization (fraction of max)
    conn_util_warning: float = 0.70
    conn_util_critical: float = 0.85
    # Dead tuple ratio
    dead_tuple_warning: float = 0.10
    dead_tuple_critical: float = 0.25
    # Lock wait time (seconds)
    lock_wait_warning: int = 30
    lock_wait_critical: int = 120
    # Deadlocks per hour
    deadlock_warning: int = 2
    deadlock_critical: int = 5
    # Slow query mean exec time (seconds)
    slow_query_warning: float = 5.0
    slow_query_critical: float = 30.0
    # Transaction ID age
    txid_age_warning: int = 500_000_000
    txid_age_critical: int = 1_000_000_000
    # Replication lag (seconds)
    repl_lag_warning: int = 10
    repl_lag_critical: int = 60


@dataclass
class SyncValidationConfig:
    """Configuration for OLTP-to-OLAP sync validation."""
    source_table: str
    target_delta_table: str
    timestamp_column: str = "updated_at"
    key_columns: list = field(default_factory=list)
    freshness_threshold_continuous_hours: float = 1.0
    freshness_threshold_batch_hours: float = 24.0
    sync_type: str = "batch"  # "continuous" or "batch"


@dataclass
class ColdDataPolicy:
    """Policy for cold data archival (FR-07)."""
    table_name: str
    schema_name: str = "public"
    cold_threshold_days: int = 90
    archive_delta_table: str = ""
    delete_after_archive: bool = True
    create_unified_view: bool = True
    min_rows_for_archival: int = 100_000


@dataclass
class IndexRecommendation:
    """Structure for index recommendations (FR-02)."""
    table_name: str
    schema_name: str
    recommendation_type: str  # "drop_unused", "reindex_bloated", "create_missing", "drop_duplicate"
    index_name: Optional[str] = None
    suggested_columns: Optional[list] = None
    confidence: str = "medium"  # "high", "medium", "low"
    estimated_impact: str = ""
    ddl_statement: str = ""
    requires_approval: bool = True


# Delta table destinations for operational data
DELTA_TABLES = {
    "pg_stat_history": "ops_catalog.lakebase_ops.pg_stat_history",
    "index_recommendations": "ops_catalog.lakebase_ops.index_recommendations",
    "vacuum_history": "ops_catalog.lakebase_ops.vacuum_history",
    "lakebase_metrics": "ops_catalog.lakebase_ops.lakebase_metrics",
    "sync_validation": "ops_catalog.lakebase_ops.sync_validation_history",
    "branch_lifecycle": "ops_catalog.lakebase_ops.branch_lifecycle",
    "data_archival": "ops_catalog.lakebase_ops.data_archival_history",
}

# Job schedules
JOB_SCHEDULES = {
    "metric_collector": "*/5 * * * *",     # Every 5 minutes
    "index_analyzer": "0 * * * *",          # Every hour
    "vacuum_scheduler": "0 2 * * *",        # Daily at 2 AM
    "sync_validator": "*/15 * * * *",       # Every 15 minutes
    "branch_manager": "0 */6 * * *",        # Every 6 hours
    "cold_archiver": "0 3 * * 0",           # Weekly Sunday 3 AM
    "connection_monitor": "* * * * *",       # Every minute
    "cost_tracker": "0 6 * * *",            # Daily 6 AM
}

# Workspace defaults
WORKSPACE_HOST = "fe-vm-hls-amer.cloud.databricks.com"
DEFAULT_CATALOG = "hls_amer_catalog"
OPS_CATALOG = "ops_catalog"
OPS_SCHEMA = "lakebase_ops"
ARCHIVE_SCHEMA = "lakebase_archive"
