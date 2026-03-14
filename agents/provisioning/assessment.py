"""
AssessmentMixin — Migration Assessment

Provides tools for assessing external PostgreSQL databases (Aurora, RDS, Cloud SQL)
for migration to Databricks Lakebase. All source connections are read-only.

Contains:
- connect_and_discover: Connect to source DB and inventory schema/extensions/functions
- profile_workload: Analyze query patterns, QPS, TPS, and connection usage
- compute_readiness_score: Score the database against Lakebase constraints
- generate_migration_blueprint: Produce a 4-phase migration plan
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sql import assessment_queries as aq
from config.migration_profiles import (
    DatabaseProfile,
    ExtensionInfo,
    FunctionInfo,
    LakebaseTier,
    MigrationProfile,
    MigrationStrategy,
    SourceEngine,
    TableProfile,
    TriggerInfo,
    WorkloadProfile,
)
from utils.readiness_scorer import (
    LAKEBASE_SUPPORTED_EXTENSIONS,
    EXTENSION_WORKAROUNDS,
    compute_readiness_score as _compute_score,
)
from utils.blueprint_generator import (
    generate_blueprint as _generate_blueprint,
    render_blueprint_markdown,
)

logger = logging.getLogger("lakebase_ops.provisioning")


class AssessmentMixin:
    """Mixin providing migration assessment tools for the ProvisioningAgent."""

    def connect_and_discover(
        self,
        endpoint: str = "",
        database: str = "",
        source_engine: str = "aurora-postgresql",
        region: str = "us-east-1",
        mock: bool = True,
        source_user: str = "",
        source_password: str = "",
    ) -> dict:
        """
        Connect read-only to a source PostgreSQL instance and discover its schema,
        data volumes, workload patterns, and advanced features.
        """
        profile_id = str(uuid.uuid4())[:8]

        if mock:
            db_profile = self._mock_discover(database or "app_production")
        else:
            db_profile = self._live_discover(endpoint, database, source_user, source_password)

        engine = SourceEngine(source_engine)
        profile = MigrationProfile(
            profile_id=profile_id,
            source_engine=engine,
            source_endpoint=endpoint or "mock-aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
            source_version=db_profile.pg_version,
            source_region=region,
            databases=[db_profile],
        )

        summary = {
            "profile_id": profile_id,
            "source_engine": engine.value,
            "source_endpoint": profile.source_endpoint,
            "source_version": db_profile.pg_version,
            "database": db_profile.name,
            "size_gb": db_profile.size_gb,
            "table_count": db_profile.table_count,
            "schema_count": db_profile.schema_count,
            "extension_count": len(db_profile.extensions),
            "function_count": len(db_profile.functions),
            "trigger_count": len(db_profile.triggers),
            "sequence_count": db_profile.sequence_count,
            "materialized_view_count": db_profile.materialized_view_count,
            "custom_type_count": db_profile.custom_type_count,
            "foreign_key_count": db_profile.foreign_key_count,
            "has_logical_replication": db_profile.has_logical_replication,
            "extensions": [e.name for e in db_profile.extensions],
            "_profile": profile,
        }

        logger.info(
            "Discovered %s: %.1f GB, %d tables, %d extensions, %d functions",
            db_profile.name, db_profile.size_gb, db_profile.table_count,
            len(db_profile.extensions), len(db_profile.functions),
        )

        return summary

    def profile_workload(
        self,
        profile_data: dict = None,
        mock: bool = True,
        source_user: str = "",
        source_password: str = "",
    ) -> dict:
        """
        Profile workload patterns from pg_stat_statements and pg_stat_activity.
        """
        if mock:
            workload = self._mock_workload()
        else:
            workload = self._live_workload(profile_data, source_user, source_password)

        if profile_data and "_profile" in profile_data:
            profile_data["_profile"].workload = workload

        summary = {
            "total_queries": workload.total_queries,
            "total_calls": workload.total_calls,
            "reads_pct": workload.reads_pct,
            "writes_pct": workload.writes_pct,
            "avg_qps": workload.avg_qps,
            "peak_qps": workload.peak_qps,
            "avg_tps": workload.avg_tps,
            "p99_latency_ms": workload.p99_latency_ms,
            "connection_count_avg": workload.connection_count_avg,
            "connection_count_peak": workload.connection_count_peak,
            "top_queries_count": len(workload.top_queries),
            "hot_tables_count": len(workload.hot_tables),
            "_workload": workload,
        }

        logger.info(
            "Workload profiled: QPS=%.0f, TPS=%.0f, Connections=%d/%d (avg/peak)",
            workload.avg_qps, workload.avg_tps,
            workload.connection_count_avg, workload.connection_count_peak,
        )

        return summary

    def assess_readiness(
        self,
        profile_data: dict = None,
        workload_data: dict = None,
    ) -> dict:
        """
        Compute a Lakebase readiness score for a profiled database.
        """
        profile: MigrationProfile | None = profile_data.get("_profile") if profile_data else None
        workload: WorkloadProfile | None = workload_data.get("_workload") if workload_data else None

        if profile and profile.databases:
            db_profile = profile.databases[0]
        else:
            db_profile = self._mock_discover("app_production")

        assessment = _compute_score(db_profile, workload)

        if profile:
            profile.assessment = assessment

        summary = {
            "overall_score": assessment.overall_score,
            "category": assessment.category.value,
            "recommended_tier": assessment.recommended_tier.value,
            "recommended_cu_range": f"{assessment.recommended_cu_min}-{assessment.recommended_cu_max} CU",
            "estimated_effort_days": assessment.estimated_effort_days,
            "blocker_count": len(assessment.blockers),
            "warning_count": len(assessment.warnings),
            "supported_extensions": assessment.supported_extensions,
            "unsupported_extensions": assessment.unsupported_extensions,
            "dimensions": {
                d.dimension: {"score": d.score, "weight": d.weight}
                for d in assessment.dimension_scores
            },
            "blockers": [
                {"severity": b.severity.value, "category": b.category, "description": b.description, "workaround": b.workaround}
                for b in assessment.blockers
            ],
            "_assessment": assessment,
            "_profile": profile,
        }

        logger.info(
            "Readiness: %.1f/100 (%s) - %d blockers, %d warnings, est. %.0f days",
            assessment.overall_score, assessment.category.value,
            len(assessment.blockers), len(assessment.warnings),
            assessment.estimated_effort_days,
        )

        return summary

    def generate_migration_blueprint(
        self,
        profile_data: dict = None,
        assessment_data: dict = None,
        workload_data: dict = None,
        source_endpoint: str = "<aurora-endpoint>",
        lakebase_endpoint: str = "<lakebase-endpoint>",
    ) -> dict:
        """
        Generate a 4-phase migration blueprint with target schema,
        data-movement strategy, and execution steps.
        """
        profile = (assessment_data or {}).get("_profile") or (profile_data or {}).get("_profile")
        assessment = (assessment_data or {}).get("_assessment")
        workload = (workload_data or {}).get("_workload")

        if profile and profile.databases:
            db_profile = profile.databases[0]
        else:
            db_profile = self._mock_discover("app_production")

        if assessment is None:
            assessment = _compute_score(db_profile, workload)

        src_ep = source_endpoint
        if profile and profile.source_endpoint:
            src_ep = profile.source_endpoint

        blueprint = _generate_blueprint(
            db_profile=db_profile,
            assessment=assessment,
            workload=workload,
            source_endpoint=src_ep,
            lakebase_endpoint=lakebase_endpoint,
            database_name=db_profile.name,
        )

        if profile:
            profile.blueprint = blueprint

        report = render_blueprint_markdown(
            blueprint=blueprint,
            db_profile=db_profile,
            assessment=assessment,
            source_engine=profile.source_engine.value if profile else "Aurora PostgreSQL",
        )

        summary = {
            "strategy": blueprint.strategy.value,
            "total_estimated_days": blueprint.total_estimated_days,
            "risk_level": blueprint.risk_level,
            "phase_count": len(blueprint.phases),
            "phases": [
                {"phase": p.phase_number, "name": p.name, "days": p.estimated_days}
                for p in blueprint.phases
            ],
            "prerequisite_count": len(blueprint.prerequisites),
            "report_markdown": report,
            "_blueprint": blueprint,
        }

        logger.info(
            "Blueprint generated: %s strategy, %.0f days, %s risk",
            blueprint.strategy.value, blueprint.total_estimated_days, blueprint.risk_level,
        )

        return summary

    # ── Mock Data (for testing without live connections) ────────────────

    def _mock_discover(self, db_name: str) -> DatabaseProfile:
        """Generate a realistic mock Aurora PostgreSQL database profile."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("postgis", "3.4.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
            ExtensionInfo("aws_s3", "1.1", False, "Use Databricks SDK for S3 access"),
        ]

        tables = [
            TableProfile("public", "users", 2_500_000, 1_200_000_000, 5, False, True, 15),
            TableProfile("public", "orders", 15_000_000, 8_500_000_000, 8, True, True, 22),
            TableProfile("public", "order_items", 45_000_000, 12_000_000_000, 4, False, True, 10),
            TableProfile("public", "products", 500_000, 250_000_000, 6, False, True, 18),
            TableProfile("public", "inventory", 1_000_000, 400_000_000, 3, True, True, 12),
            TableProfile("public", "sessions", 8_000_000, 3_200_000_000, 2, False, False, 8),
            TableProfile("public", "audit_log", 50_000_000, 20_000_000_000, 1, False, False, 6),
            TableProfile("analytics", "user_events", 100_000_000, 45_000_000_000, 3, False, True, 14),
            TableProfile("analytics", "page_views", 200_000_000, 60_000_000_000, 2, False, False, 8),
            TableProfile("ml", "embeddings", 5_000_000, 15_000_000_000, 1, False, False, 3),
        ]

        functions = [
            FunctionInfo("public", "update_modified_column", "plpgsql", True, 8),
            FunctionInfo("public", "calculate_order_total", "plpgsql", False, 25),
            FunctionInfo("public", "validate_inventory", "plpgsql", True, 15),
            FunctionInfo("public", "archive_old_sessions", "plpgsql", False, 40),
            FunctionInfo("public", "generate_report_data", "plpgsql", False, 60),
            FunctionInfo("analytics", "aggregate_daily_stats", "plpgsql", False, 80),
        ]

        triggers = [
            TriggerInfo("public", "orders", "trg_orders_modified", "UPDATE", "BEFORE", "update_modified_column"),
            TriggerInfo("public", "inventory", "trg_inventory_check", "INSERT OR UPDATE", "AFTER", "validate_inventory"),
        ]

        total_size = sum(t.size_bytes for t in tables)

        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024 ** 3), 2),
            table_count=len(tables),
            schema_count=3,
            schemas=["public", "analytics", "ml"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=12,
            materialized_view_count=3,
            custom_type_count=2,
            foreign_key_count=8,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="15.4",
        )

    def _mock_workload(self) -> WorkloadProfile:
        """Generate a realistic mock workload profile."""
        return WorkloadProfile(
            total_queries=1_250,
            total_calls=85_000_000,
            reads_pct=72.0,
            writes_pct=28.0,
            avg_qps=2_800,
            peak_qps=8_500,
            avg_tps=780,
            p99_latency_ms=45.0,
            top_queries=[
                {"query": "SELECT * FROM orders WHERE customer_id = $1", "calls": 15_000_000, "mean_ms": 2.1},
                {"query": "INSERT INTO order_items ...", "calls": 8_000_000, "mean_ms": 3.5},
                {"query": "SELECT * FROM products WHERE category = $1", "calls": 5_000_000, "mean_ms": 8.2},
                {"query": "UPDATE inventory SET quantity = $1 WHERE product_id = $2", "calls": 2_000_000, "mean_ms": 4.1},
                {"query": "SELECT * FROM user_events WHERE user_id = $1 AND ...", "calls": 3_000_000, "mean_ms": 12.5},
            ],
            hot_tables=["orders", "order_items", "sessions", "user_events"],
            connection_count_avg=120,
            connection_count_peak=350,
        )

    def _live_discover(self, endpoint: str, database: str, user: str = "", password: str = "") -> DatabaseProfile:
        """Connect to a live source database and discover its schema."""
        try:
            from e2e_test.live_connector import live_discover
            return live_discover(endpoint, 5432, database, user, password)
        except ImportError:
            logger.warning("e2e_test.live_connector not available - returning mock data")
            return self._mock_discover(database)

    def _live_workload(self, profile_data: dict, user: str = "", password: str = "") -> WorkloadProfile:
        """Profile workload from a live source database."""
        try:
            from e2e_test.live_connector import live_workload
            profile = profile_data.get("_profile") if profile_data else None
            if profile:
                return live_workload(profile.source_endpoint, 5432, profile.databases[0].name, user, password)
            logger.warning("No profile data for live workload - returning mock data")
            return self._mock_workload()
        except ImportError:
            logger.warning("e2e_test.live_connector not available - returning mock data")
            return self._mock_workload()
