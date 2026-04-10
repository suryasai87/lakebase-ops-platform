"""
AssessmentMixin — Migration Assessment

Provides tools for assessing external databases (PostgreSQL engines, DynamoDB,
and Azure Cosmos DB) for migration to Databricks Lakebase.
All source connections are read-only.

Contains:
- connect_and_discover: Connect to source DB and inventory schema/extensions/features
- profile_workload: Analyze query patterns, QPS, TPS, and connection usage
- compute_readiness_score: Score the database against Lakebase constraints
- generate_migration_blueprint: Produce a 4-phase migration plan
"""

from __future__ import annotations

import logging
import uuid

from config.migration_profiles import (
    ENGINE_KIND,
    DatabaseProfile,
    ExtensionInfo,
    FunctionInfo,
    MigrationProfile,
    SourceEngine,
    TableProfile,
    TriggerInfo,
    WorkloadProfile,
)
from sql import assessment_queries as aq
from utils.blueprint_generator import (
    generate_blueprint as _generate_blueprint,
)
from utils.blueprint_generator import (
    render_blueprint_markdown,
)
from utils.readiness_scorer import (
    EXTENSION_WORKAROUNDS,
    LAKEBASE_SUPPORTED_EXTENSIONS,
)
from utils.readiness_scorer import (
    compute_readiness_score as _compute_score,
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
            _mock_engines = {
                "aurora-postgresql": self._mock_discover,
                "rds-postgresql": self._mock_discover_rds,
                "cloud-sql-postgresql": self._mock_discover_cloud_sql,
                "azure-postgresql": self._mock_discover_azure,
                "self-managed-postgresql": self._mock_discover_self_managed,
                "alloydb-postgresql": self._mock_discover_alloydb,
                "supabase-postgresql": self._mock_discover_supabase,
                "dynamodb": self._mock_discover_dynamodb,
                "cosmosdb-nosql": self._mock_discover_cosmosdb,
            }
            discover_fn = _mock_engines.get(source_engine, self._mock_discover)
            db_profile = discover_fn(database or "app_production")
        else:
            if source_engine == "cosmosdb-nosql":
                db_profile = self._live_discover_cosmosdb(endpoint, database, source_user, source_password)
            else:
                db_profile = self._live_discover(endpoint, database, source_user, source_password)

        is_nosql = ENGINE_KIND.get(source_engine) == "nosql"
        engine = SourceEngine(source_engine)
        _mock_endpoints = {
            "aurora-postgresql": "mock-aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
            "rds-postgresql": "mock-rds.xxx.us-east-1.rds.amazonaws.com",
            "cloud-sql-postgresql": "mock-project:us-central1:mock-instance",
            "azure-postgresql": "mock-server.postgres.database.azure.com",
            "self-managed-postgresql": "pg-primary.internal.example.com",
            "alloydb-postgresql": "10.0.0.5",
            "supabase-postgresql": "db.abcdefghijkl.supabase.co",
            "dynamodb": "dynamodb.us-east-1.amazonaws.com",
            "cosmosdb-nosql": "myaccount.documents.azure.com",
        }
        profile = MigrationProfile(
            profile_id=profile_id,
            source_engine=engine,
            source_endpoint=endpoint or _mock_endpoints.get(source_engine, "mock-source.example.com"),
            source_version=db_profile.pg_version
            if not is_nosql
            else ("CosmosDB" if source_engine == "cosmosdb-nosql" else "DynamoDB"),
            source_region=region,
            databases=[db_profile],
        )

        if is_nosql and source_engine == "cosmosdb-nosql":
            summary = {
                "profile_id": profile_id,
                "source_engine": engine.value,
                "source_endpoint": profile.source_endpoint,
                "source_version": "CosmosDB",
                "database": db_profile.name,
                "size_gb": db_profile.size_gb,
                "table_count": db_profile.table_count,
                "cosmos_throughput_mode": db_profile.cosmos_throughput_mode or "provisioned",
                "cosmos_ru_per_sec": db_profile.cosmos_ru_per_sec or 0,
                "cosmos_consistency_level": db_profile.cosmos_consistency_level or "Session",
                "cosmos_change_feed_enabled": db_profile.cosmos_change_feed_enabled or False,
                "cosmos_multi_region_writes": db_profile.cosmos_multi_region_writes or False,
                "cosmos_regions": db_profile.cosmos_regions or [],
                "cosmos_partition_key_paths": db_profile.cosmos_partition_key_paths or [],
                "_profile": profile,
            }
        elif is_nosql:
            summary = {
                "profile_id": profile_id,
                "source_engine": engine.value,
                "source_endpoint": profile.source_endpoint,
                "source_version": "DynamoDB",
                "database": db_profile.name,
                "size_gb": db_profile.size_gb,
                "table_count": db_profile.table_count,
                "billing_mode": db_profile.billing_mode or "on-demand",
                "gsi_count": db_profile.gsi_count or 0,
                "lsi_count": db_profile.lsi_count or 0,
                "streams_enabled": db_profile.streams_enabled or False,
                "ttl_enabled": db_profile.ttl_enabled or False,
                "pitr_enabled": db_profile.pitr_enabled or False,
                "global_table_regions": db_profile.global_table_regions or [],
                "item_size_avg_bytes": db_profile.item_size_avg_bytes or 0,
                "_profile": profile,
            }
        else:
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

        if is_nosql and source_engine == "cosmosdb-nosql":
            logger.info(
                "Discovered %s: %.1f GB, %d containers, %d RU/s, consistency=%s",
                db_profile.name,
                db_profile.size_gb,
                db_profile.table_count,
                db_profile.cosmos_ru_per_sec or 0,
                db_profile.cosmos_consistency_level or "unknown",
            )
        elif is_nosql:
            logger.info(
                "Discovered %s: %.1f GB, %d tables, %d GSIs, billing=%s",
                db_profile.name,
                db_profile.size_gb,
                db_profile.table_count,
                db_profile.gsi_count or 0,
                db_profile.billing_mode or "unknown",
            )
        else:
            logger.info(
                "Discovered %s: %.1f GB, %d tables, %d extensions, %d functions",
                db_profile.name,
                db_profile.size_gb,
                db_profile.table_count,
                len(db_profile.extensions),
                len(db_profile.functions),
            )

        return summary

    def profile_workload(
        self,
        profile_data: dict | None = None,
        mock: bool = True,
        source_user: str = "",
        source_password: str = "",
    ) -> dict:
        """
        Profile workload patterns from pg_stat_statements and pg_stat_activity.
        """
        engine_str = ""
        if profile_data and "_profile" in profile_data:
            engine_str = profile_data["_profile"].source_engine.value

        if mock:
            if engine_str == "cosmosdb-nosql":
                workload = self._mock_workload_cosmosdb()
            elif ENGINE_KIND.get(engine_str) == "nosql":
                workload = self._mock_workload_dynamodb()
            else:
                workload = self._mock_workload()
        else:
            if engine_str == "cosmosdb-nosql":
                workload = self._live_workload_cosmosdb(profile_data)
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
            workload.avg_qps,
            workload.avg_tps,
            workload.connection_count_avg,
            workload.connection_count_peak,
        )

        return summary

    def assess_readiness(
        self,
        profile_data: dict | None = None,
        workload_data: dict | None = None,
    ) -> dict:
        """
        Compute a Lakebase readiness score for a profiled database.
        """
        profile: MigrationProfile | None = profile_data.get("_profile") if profile_data else None
        workload: WorkloadProfile | None = workload_data.get("_workload") if workload_data else None

        db_profile = profile.databases[0] if profile and profile.databases else self._mock_discover("app_production")

        source_engine = profile.source_engine.value if profile else ""
        assessment = _compute_score(db_profile, workload, source_engine)

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
            "dimensions": {d.dimension: {"score": d.score, "weight": d.weight} for d in assessment.dimension_scores},
            "blockers": [
                {
                    "severity": b.severity.value,
                    "category": b.category,
                    "description": b.description,
                    "workaround": b.workaround,
                }
                for b in assessment.blockers
            ],
            "warnings": list(assessment.warnings),
            "sizing_by_env": [
                {
                    "env": es.env,
                    "cu_min": es.cu_min,
                    "cu_max": es.cu_max,
                    "scale_to_zero": es.scale_to_zero,
                    "autoscaling": es.autoscaling,
                    "max_connections": es.max_connections,
                    "ram_gb": es.ram_gb,
                    "notes": es.notes,
                }
                for es in assessment.sizing_by_env
            ],
            "_assessment": assessment,
            "_profile": profile,
        }

        logger.info(
            "Readiness: %.1f/100 (%s) - %d blockers, %d warnings, est. %.0f days",
            assessment.overall_score,
            assessment.category.value,
            len(assessment.blockers),
            len(assessment.warnings),
            assessment.estimated_effort_days,
        )

        return summary

    def generate_migration_blueprint(
        self,
        profile_data: dict | None = None,
        assessment_data: dict | None = None,
        workload_data: dict | None = None,
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

        db_profile = profile.databases[0] if profile and profile.databases else self._mock_discover("app_production")

        engine_str = profile.source_engine.value if profile else "aurora-postgresql"

        if assessment is None:
            assessment = _compute_score(db_profile, workload, engine_str)

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
            source_engine=engine_str,
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
            "phases": [{"phase": p.phase_number, "name": p.name, "days": p.estimated_days} for p in blueprint.phases],
            "prerequisite_count": len(blueprint.prerequisites),
            "report_markdown": report,
            "_blueprint": blueprint,
        }

        logger.info(
            "Blueprint generated: %s strategy, %.0f days, %s risk",
            blueprint.strategy.value,
            blueprint.total_estimated_days,
            blueprint.risk_level,
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
            TriggerInfo(
                "public", "inventory", "trg_inventory_check", "INSERT OR UPDATE", "AFTER", "validate_inventory"
            ),
        ]

        total_size = sum(t.size_bytes for t in tables)

        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
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
                {
                    "query": "UPDATE inventory SET quantity = $1 WHERE product_id = $2",
                    "calls": 2_000_000,
                    "mean_ms": 4.1,
                },
                {"query": "SELECT * FROM user_events WHERE user_id = $1 AND ...", "calls": 3_000_000, "mean_ms": 12.5},
            ],
            hot_tables=["orders", "order_items", "sessions", "user_events"],
            connection_count_avg=120,
            connection_count_peak=350,
            workload_source="mock",
        )

    def _mock_discover_dynamodb(self, db_name: str) -> DatabaseProfile:
        """Mock DynamoDB profile - NoSQL key-value/document store."""
        tables = [
            TableProfile("default", "Users", 2_500_000, 1_200_000_000, 3, False, False, 0),
            TableProfile("default", "Orders", 15_000_000, 8_500_000_000, 5, False, False, 0),
            TableProfile("default", "OrderItems", 45_000_000, 12_000_000_000, 2, False, False, 0),
            TableProfile("default", "Products", 500_000, 250_000_000, 4, False, False, 0),
            TableProfile("default", "Inventory", 1_000_000, 400_000_000, 1, False, False, 0),
            TableProfile("default", "Sessions", 8_000_000, 3_200_000_000, 0, False, False, 0),
            TableProfile("default", "AuditLog", 50_000_000, 20_000_000_000, 1, False, False, 0),
            TableProfile("default", "UserEvents", 100_000_000, 45_000_000_000, 3, False, False, 0),
            TableProfile("default", "Notifications", 10_000_000, 3_000_000_000, 1, False, False, 0),
            TableProfile("default", "Config", 500, 50_000, 0, False, False, 0),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name or "dynamodb-account",
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=1,
            schemas=["default"],
            tables=tables,
            extensions=[],
            functions=[],
            triggers=[],
            sequence_count=0,
            materialized_view_count=0,
            custom_type_count=0,
            foreign_key_count=0,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="",
            billing_mode="on-demand",
            gsi_count=8,
            lsi_count=2,
            streams_enabled=True,
            ttl_enabled=True,
            pitr_enabled=True,
            global_table_regions=[],
            item_size_avg_bytes=4200,
            dynamo_table_details=[
                {
                    "name": "Users",
                    "key_schema": "PK (userId)",
                    "billing": "on-demand",
                    "gsi_count": 2,
                    "item_count": 2_500_000,
                },
                {
                    "name": "Orders",
                    "key_schema": "PK (orderId), SK (createdAt)",
                    "billing": "on-demand",
                    "gsi_count": 3,
                    "item_count": 15_000_000,
                },
                {
                    "name": "OrderItems",
                    "key_schema": "PK (orderId), SK (itemId)",
                    "billing": "on-demand",
                    "gsi_count": 1,
                    "item_count": 45_000_000,
                },
                {
                    "name": "Products",
                    "key_schema": "PK (productId)",
                    "billing": "provisioned",
                    "gsi_count": 2,
                    "item_count": 500_000,
                },
                {
                    "name": "Sessions",
                    "key_schema": "PK (sessionId)",
                    "billing": "on-demand",
                    "gsi_count": 0,
                    "item_count": 8_000_000,
                },
                {
                    "name": "UserEvents",
                    "key_schema": "PK (userId), SK (eventTimestamp)",
                    "billing": "on-demand",
                    "gsi_count": 0,
                    "item_count": 100_000_000,
                },
            ],
        )

    def _mock_workload_dynamodb(self) -> WorkloadProfile:
        """Mock DynamoDB workload - RCU/WCU mapped to QPS/TPS."""
        return WorkloadProfile(
            total_queries=800,
            total_calls=50_000_000,
            reads_pct=80.0,
            writes_pct=20.0,
            avg_qps=3_500,
            peak_qps=12_000,
            avg_tps=850,
            p99_latency_ms=8.0,
            top_queries=[
                {"query": "GetItem: Users (userId)", "calls": 20_000_000, "mean_ms": 3.0},
                {"query": "Query: Orders (userId, createdAt)", "calls": 10_000_000, "mean_ms": 5.0},
                {"query": "PutItem: UserEvents", "calls": 8_000_000, "mean_ms": 4.0},
                {"query": "Query: OrderItems (orderId)", "calls": 5_000_000, "mean_ms": 3.5},
                {"query": "Scan: Products (category GSI)", "calls": 2_000_000, "mean_ms": 15.0},
            ],
            hot_tables=["Users", "Orders", "UserEvents", "Sessions"],
            connection_count_avg=80,
            connection_count_peak=250,
            workload_source="mock",
        )

    def _mock_discover_cosmosdb(self, db_name: str) -> DatabaseProfile:
        """Mock Azure Cosmos DB (NoSQL API) profile - document store with partition keys."""
        tables = [
            TableProfile("default", "Users", 2_000_000, 1_000_000_000, 2, False, False, 0),
            TableProfile("default", "Orders", 12_000_000, 7_200_000_000, 3, False, False, 0),
            TableProfile("default", "OrderItems", 35_000_000, 10_500_000_000, 1, False, False, 0),
            TableProfile("default", "Products", 400_000, 200_000_000, 2, False, False, 0),
            TableProfile("default", "Sessions", 6_000_000, 2_400_000_000, 1, False, False, 0),
            TableProfile("default", "UserEvents", 80_000_000, 36_000_000_000, 2, False, False, 0),
            TableProfile("default", "Notifications", 8_000_000, 2_400_000_000, 1, False, False, 0),
            TableProfile("default", "Config", 1_000, 100_000, 0, False, False, 0),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name or "cosmosdb-account",
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=1,
            schemas=["default"],
            tables=tables,
            extensions=[],
            functions=[],
            triggers=[],
            sequence_count=0,
            materialized_view_count=0,
            custom_type_count=0,
            foreign_key_count=0,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="",
            cosmos_throughput_mode="provisioned",
            cosmos_ru_per_sec=4000,
            cosmos_partition_key_paths=[
                "/userId",
                "/orderId",
                "/orderId",
                "/productId",
                "/sessionId",
                "/userId",
                "/userId",
                "/configKey",
            ],
            cosmos_consistency_level="Session",
            cosmos_change_feed_enabled=False,
            cosmos_change_feed_mode="LatestVersion",
            cosmos_multi_region_writes=False,
            cosmos_regions=["eastus"],
            cosmos_container_details=[
                {
                    "name": "Users",
                    "partition_key": "/userId",
                    "ru_per_sec": 400,
                    "indexing_policy": "consistent",
                    "item_count": 2_000_000,
                },
                {
                    "name": "Orders",
                    "partition_key": "/orderId",
                    "ru_per_sec": 1000,
                    "indexing_policy": "consistent",
                    "item_count": 12_000_000,
                },
                {
                    "name": "OrderItems",
                    "partition_key": "/orderId",
                    "ru_per_sec": 800,
                    "indexing_policy": "consistent",
                    "item_count": 35_000_000,
                },
                {
                    "name": "Products",
                    "partition_key": "/productId",
                    "ru_per_sec": 400,
                    "indexing_policy": "consistent",
                    "item_count": 400_000,
                },
                {
                    "name": "Sessions",
                    "partition_key": "/sessionId",
                    "ru_per_sec": 400,
                    "indexing_policy": "lazy",
                    "item_count": 6_000_000,
                },
                {
                    "name": "UserEvents",
                    "partition_key": "/userId",
                    "ru_per_sec": 600,
                    "indexing_policy": "consistent",
                    "item_count": 80_000_000,
                },
                {
                    "name": "Notifications",
                    "partition_key": "/userId",
                    "ru_per_sec": 200,
                    "indexing_policy": "consistent",
                    "item_count": 8_000_000,
                },
                {
                    "name": "Config",
                    "partition_key": "/configKey",
                    "ru_per_sec": 200,
                    "indexing_policy": "none",
                    "item_count": 1_000,
                },
            ],
        )

    def _mock_workload_cosmosdb(self) -> WorkloadProfile:
        """Mock Cosmos DB workload - RU/s mapped to QPS/TPS."""
        return WorkloadProfile(
            total_queries=600,
            total_calls=40_000_000,
            reads_pct=75.0,
            writes_pct=25.0,
            avg_qps=2_800,
            peak_qps=9_000,
            avg_tps=700,
            p99_latency_ms=12.0,
            workload_source="mock",
            top_queries=[
                {"query": "ReadItem: Users (userId)", "calls": 15_000_000, "mean_ms": 3.0},
                {"query": "Query: Orders WHERE userId=@uid", "calls": 8_000_000, "mean_ms": 6.0},
                {"query": "CreateItem: UserEvents", "calls": 6_000_000, "mean_ms": 5.0},
                {"query": "Query: OrderItems WHERE orderId=@oid", "calls": 4_000_000, "mean_ms": 4.0},
                {"query": "Query: Products WHERE category=@cat (cross-partition)", "calls": 2_000_000, "mean_ms": 18.0},
            ],
            hot_tables=["Users", "Orders", "UserEvents", "Sessions"],
            connection_count_avg=60,
            connection_count_peak=200,
        )

    def _mock_discover_rds(self, db_name: str) -> DatabaseProfile:
        """Mock RDS PostgreSQL profile - smaller instance, pg_repack, no Aurora ML."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
            ExtensionInfo("aws_s3", "1.1", False, "Use Databricks SDK for S3 access"),
            ExtensionInfo("pg_repack", "1.5.0", False, "Use VACUUM FULL + REINDEX CONCURRENTLY"),
        ]
        tables = [
            TableProfile("public", "customers", 800_000, 400_000_000, 4, False, True, 12),
            TableProfile("public", "transactions", 5_000_000, 2_800_000_000, 6, True, True, 18),
            TableProfile("public", "accounts", 200_000, 100_000_000, 3, False, True, 10),
            TableProfile("public", "audit_trail", 12_000_000, 6_000_000_000, 1, False, False, 8),
            TableProfile("public", "config", 500, 50_000, 1, False, False, 6),
        ]
        functions = [
            FunctionInfo("public", "update_timestamp", "plpgsql", True, 6),
            FunctionInfo("public", "calculate_balance", "plpgsql", False, 30),
        ]
        triggers = [
            TriggerInfo(
                "public", "transactions", "trg_txn_timestamp", "INSERT OR UPDATE", "BEFORE", "update_timestamp"
            ),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=1,
            schemas=["public"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=5,
            materialized_view_count=1,
            custom_type_count=1,
            foreign_key_count=3,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="15.15",
        )

    def _mock_discover_cloud_sql(self, db_name: str) -> DatabaseProfile:
        """Mock Cloud SQL PostgreSQL profile - GCP extensions, no AWS deps."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("postgis", "3.4.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
            ExtensionInfo("google_ml_integration", "1.0", False, "Use Databricks Foundation Model API"),
            ExtensionInfo("pg_squeeze", "1.6", False, "Use VACUUM FULL + REINDEX CONCURRENTLY"),
        ]
        tables = [
            TableProfile("public", "users", 3_000_000, 1_500_000_000, 5, False, True, 14),
            TableProfile("public", "documents", 8_000_000, 4_500_000_000, 4, False, True, 20),
            TableProfile("public", "doc_embeddings", 8_000_000, 12_000_000_000, 2, False, True, 4),
            TableProfile("public", "search_log", 25_000_000, 8_000_000_000, 2, False, False, 10),
            TableProfile("public", "organizations", 50_000, 25_000_000, 3, False, True, 16),
            TableProfile("geo", "locations", 2_000_000, 800_000_000, 3, False, True, 8),
            TableProfile("geo", "boundaries", 100_000, 500_000_000, 1, False, False, 4),
        ]
        functions = [
            FunctionInfo("public", "update_search_index", "plpgsql", True, 12),
            FunctionInfo("public", "compute_similarity", "plpgsql", False, 35),
            FunctionInfo("public", "archive_search_logs", "plpgsql", False, 50),
            FunctionInfo("geo", "find_nearby", "sql", False, 10),
        ]
        triggers = [
            TriggerInfo(
                "public", "documents", "trg_doc_search_idx", "INSERT OR UPDATE", "AFTER", "update_search_index"
            ),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=2,
            schemas=["public", "geo"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=7,
            materialized_view_count=2,
            custom_type_count=1,
            foreign_key_count=5,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="16.4",
        )

    def _mock_discover_azure(self, db_name: str) -> DatabaseProfile:
        """Mock Azure Flexible Server profile - Azure extensions, Entra ID auth."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("citext", "1.6", True),
            ExtensionInfo("hstore", "1.8", True),
            ExtensionInfo("azure_storage", "1.5", False, "Replace with Databricks SDK for Azure Blob access"),
            ExtensionInfo("azure_ai", "1.0", False, "Replace with Databricks Foundation Model API"),
            ExtensionInfo("age", "1.5.0", False, "Not supported; use GraphFrames or Delta Lake for graph workloads"),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
        ]
        tables = [
            TableProfile("public", "patients", 1_500_000, 750_000_000, 6, False, True, 22),
            TableProfile("public", "records", 20_000_000, 10_000_000_000, 5, True, True, 30),
            TableProfile("public", "appointments", 8_000_000, 3_200_000_000, 4, True, True, 14),
            TableProfile("public", "providers", 50_000, 25_000_000, 3, False, True, 18),
            TableProfile("graph", "relationships", 5_000_000, 2_000_000_000, 2, False, True, 6),
            TableProfile("graph", "nodes", 2_000_000, 800_000_000, 3, False, False, 8),
        ]
        functions = [
            FunctionInfo("public", "validate_record", "plpgsql", True, 20),
            FunctionInfo("public", "generate_report", "plpgsql", False, 75),
            FunctionInfo("public", "schedule_appointment", "plpgsql", False, 40),
            FunctionInfo("graph", "traverse_path", "plpgsql", False, 60),
        ]
        triggers = [
            TriggerInfo("public", "records", "trg_record_validate", "INSERT OR UPDATE", "BEFORE", "validate_record"),
            TriggerInfo(
                "public", "appointments", "trg_appt_audit", "INSERT OR UPDATE OR DELETE", "AFTER", "validate_record"
            ),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=2,
            schemas=["public", "graph"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=8,
            materialized_view_count=4,
            custom_type_count=3,
            foreign_key_count=7,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="16.8",
        )

    def _mock_discover_self_managed(self, db_name: str) -> DatabaseProfile:
        """Mock self-managed PostgreSQL - complex setup with many unsupported extensions."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("postgis", "3.3.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("hstore", "1.8", True),
            ExtensionInfo(
                "timescaledb", "2.14.0", False, "Not available; use standard partitioning or Delta Lake for time-series"
            ),
            ExtensionInfo("citus", "12.1", False, "No distributed/sharded tables in Lakebase"),
            ExtensionInfo("pglogical", "2.4.4", False, "No logical replication in Lakebase; use Lakeflow Connect"),
            ExtensionInfo("pg_repack", "1.5.0", False, "Use VACUUM FULL + REINDEX CONCURRENTLY"),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
            ExtensionInfo("wal2json", "2.5", False, "No WAL-based CDC; use Lakeflow Connect"),
            ExtensionInfo("pgaudit", "16.0", False, "Use pg_stat_statements or Databricks audit logs"),
        ]
        tables = [
            TableProfile("public", "events", 500_000_000, 200_000_000_000, 4, True, True, 12),
            TableProfile("public", "metrics", 800_000_000, 320_000_000_000, 3, False, False, 8),
            TableProfile("public", "users", 5_000_000, 2_500_000_000, 6, False, True, 20),
            TableProfile("public", "sessions", 50_000_000, 20_000_000_000, 2, False, True, 10),
            TableProfile("public", "configs", 1_000, 100_000, 1, False, False, 15),
            TableProfile("ts", "raw_metrics", 1_000_000_000, 400_000_000_000, 2, False, False, 6),
            TableProfile("ts", "rollup_hourly", 100_000_000, 40_000_000_000, 1, False, False, 6),
            TableProfile("shard", "tenant_data", 200_000_000, 80_000_000_000, 4, False, True, 14),
        ]
        functions = [
            FunctionInfo("public", "update_modified", "plpgsql", True, 6),
            FunctionInfo("public", "partition_maintenance", "plpgsql", False, 120),
            FunctionInfo("public", "compute_aggregates", "plpgsql", False, 200),
            FunctionInfo("ts", "continuous_aggregate", "plpgsql", False, 150),
            FunctionInfo("ts", "retention_policy", "plpgsql", False, 80),
            FunctionInfo("shard", "route_query", "plpgsql", False, 90),
        ]
        triggers = [
            TriggerInfo("public", "events", "trg_events_modified", "INSERT", "AFTER", "update_modified"),
            TriggerInfo("public", "metrics", "trg_metrics_partition", "INSERT", "BEFORE", "partition_maintenance"),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=3,
            schemas=["public", "ts", "shard"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=15,
            materialized_view_count=6,
            custom_type_count=5,
            foreign_key_count=4,
            has_logical_replication=True,
            replication_slots=["pglogical_subscriber_1", "wal2json_cdc"],
            pg_version="14.10",
            event_trigger_count=2,
            large_object_count=15,
            partition_strategies=["range", "hash"],
        )

    def _mock_discover_alloydb(self, db_name: str) -> DatabaseProfile:
        """Mock AlloyDB for PostgreSQL profile - columnar engine, google_ml_integration."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("postgis", "3.4.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("google_ml_integration", "1.3", False, "Use Databricks Foundation Model API"),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
        ]
        tables = [
            TableProfile("public", "users", 4_000_000, 2_000_000_000, 5, False, True, 16),
            TableProfile("public", "transactions", 30_000_000, 16_000_000_000, 7, True, True, 20),
            TableProfile("public", "products", 800_000, 400_000_000, 5, False, True, 18),
            TableProfile("public", "recommendations", 10_000_000, 8_000_000_000, 3, False, True, 6),
            TableProfile("analytics", "events", 80_000_000, 35_000_000_000, 3, False, False, 12),
            TableProfile("analytics", "sessions", 20_000_000, 8_000_000_000, 2, False, True, 10),
            TableProfile("ml", "embeddings", 10_000_000, 30_000_000_000, 1, False, False, 3),
        ]
        functions = [
            FunctionInfo("public", "update_modified", "plpgsql", True, 8),
            FunctionInfo("public", "compute_recommendations", "plpgsql", False, 45),
            FunctionInfo("analytics", "aggregate_events", "plpgsql", False, 60),
            FunctionInfo("ml", "predict_churn", "sql", False, 15),
        ]
        triggers = [
            TriggerInfo("public", "transactions", "trg_txn_modified", "INSERT OR UPDATE", "BEFORE", "update_modified"),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=3,
            schemas=["public", "analytics", "ml"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=10,
            materialized_view_count=3,
            custom_type_count=1,
            foreign_key_count=6,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="15.7",
        )

    def _mock_discover_supabase(self, db_name: str) -> DatabaseProfile:
        """Mock Supabase PostgreSQL profile - auth/storage schemas, realtime, pg_graphql."""
        extensions = [
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
            ExtensionInfo("pg_trgm", "1.6", True),
            ExtensionInfo("pgcrypto", "1.3", True),
            ExtensionInfo("uuid-ossp", "1.1", True),
            ExtensionInfo("pg_graphql", "1.5.0", True),
            ExtensionInfo("pgjwt", "0.2.0", False, "Implement JWT validation in application layer"),
            ExtensionInfo("pg_cron", "1.6", False, "Replace with Databricks Jobs"),
            ExtensionInfo("pg_tle", "1.3.0", False, "Custom TLE extensions must be evaluated individually"),
        ]
        tables = [
            TableProfile("public", "profiles", 500_000, 250_000_000, 4, False, True, 12),
            TableProfile("public", "posts", 3_000_000, 1_500_000_000, 5, True, True, 16),
            TableProfile("public", "comments", 8_000_000, 3_200_000_000, 3, False, True, 10),
            TableProfile("public", "likes", 15_000_000, 4_500_000_000, 2, False, True, 4),
            TableProfile("public", "messages", 6_000_000, 2_400_000_000, 3, False, True, 8),
            TableProfile("public", "notifications", 10_000_000, 3_000_000_000, 2, False, True, 6),
        ]
        functions = [
            FunctionInfo("public", "handle_new_user", "plpgsql", True, 20),
            FunctionInfo("public", "update_post_count", "plpgsql", True, 10),
            FunctionInfo("public", "search_posts", "sql", False, 15),
        ]
        triggers = [
            TriggerInfo("public", "posts", "trg_post_count", "INSERT OR DELETE", "AFTER", "update_post_count"),
        ]
        total_size = sum(t.size_bytes for t in tables)
        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2),
            table_count=len(tables),
            schema_count=1,
            schemas=["public"],
            tables=tables,
            extensions=extensions,
            functions=functions,
            triggers=triggers,
            sequence_count=6,
            materialized_view_count=1,
            custom_type_count=0,
            foreign_key_count=5,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="15.6",
        )

    def _live_discover(self, endpoint: str, database: str, user: str = "", password: str = "") -> DatabaseProfile:
        """Connect to a live source database and discover its schema."""
        try:
            import psycopg
        except ImportError:
            logger.warning("psycopg not installed - returning mock data")
            return self._mock_discover(database)

        try:
            with (
                psycopg.connect(
                    host=endpoint,
                    port=5432,
                    dbname=database,
                    user=user,
                    password=password,
                    sslmode="require",
                    options="-c statement_timeout=30000",
                ) as conn,
                conn.cursor() as cur,
            ):
                cur.execute("SELECT version()")
                pg_version = (cur.fetchone()[0] or "").split()[1] if cur.rowcount else "unknown"

                cur.execute(aq.DISCOVER_TABLES)
                tables = [
                    TableProfile(
                        schema_name=r[0],
                        table_name=r[1],
                        row_count=int(r[3] or 0),
                        size_bytes=int(r[4] or 0),
                        index_count=int(r[6] or 0),
                        has_triggers=False,
                        has_foreign_keys=int(r[3] or 0) > 0,
                        column_count=int(r[7] or 0),
                    )
                    for r in cur.fetchall()
                ]

                cur.execute(aq.DISCOVER_EXTENSIONS)
                extensions = [
                    ExtensionInfo(
                        r[0], r[1], r[0] in LAKEBASE_SUPPORTED_EXTENSIONS, EXTENSION_WORKAROUNDS.get(r[0], "")
                    )
                    for r in cur.fetchall()
                ]

                cur.execute(aq.DISCOVER_FUNCTIONS)
                functions = [FunctionInfo(r[0], r[1], r[2], False, 0) for r in cur.fetchall()]

                cur.execute(aq.DISCOVER_TRIGGERS)
                triggers = [
                    TriggerInfo(
                        schema_name=r[0],
                        table_name=r[1],
                        trigger_name=r[2],
                        event="",
                        timing="",
                        function_name=r[3] if len(r) > 3 else "",
                    )
                    for r in cur.fetchall()
                ]

                cur.execute(aq.DISCOVER_SCHEMAS)
                schemas = [r[0] for r in cur.fetchall()]

                cur.execute(aq.DISCOVER_SEQUENCES)
                seq_count = len(cur.fetchall())

                cur.execute(aq.DISCOVER_MATERIALIZED_VIEWS)
                matview_count = len(cur.fetchall())

                cur.execute(aq.DISCOVER_CUSTOM_TYPES)
                custom_type_count = len(cur.fetchall())

                cur.execute(aq.DISCOVER_FOREIGN_KEYS)
                fk_count = len(cur.fetchall())

                total_size = sum(t.size_bytes for t in tables)

                return DatabaseProfile(
                    name=database,
                    size_bytes=total_size,
                    size_gb=round(total_size / (1024**3), 2),
                    table_count=len(tables),
                    schema_count=len(schemas),
                    schemas=schemas,
                    tables=tables,
                    extensions=extensions,
                    functions=functions,
                    triggers=triggers,
                    sequence_count=seq_count,
                    materialized_view_count=matview_count,
                    custom_type_count=custom_type_count,
                    foreign_key_count=fk_count,
                    has_logical_replication=False,
                    replication_slots=[],
                    pg_version=pg_version,
                )
        except Exception as e:
            logger.error(f"Live discover failed: {e}")
            return self._mock_discover(database)

    def _live_workload(self, profile_data: dict, user: str = "", password: str = "") -> WorkloadProfile:
        """Profile workload from a live source database."""
        try:
            import psycopg
        except ImportError:
            logger.warning("psycopg not installed - returning mock data")
            return self._mock_workload()

        profile = profile_data.get("_profile") if profile_data else None
        if not profile or not profile.databases:
            logger.warning("No profile data for live workload - returning mock data")
            return self._mock_workload()

        endpoint = profile.source_endpoint
        database = profile.databases[0].name

        try:
            with (
                psycopg.connect(
                    host=endpoint,
                    port=5432,
                    dbname=database,
                    user=user,
                    password=password,
                    sslmode="require",
                    options="-c statement_timeout=30000",
                ) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(aq.PROFILE_WORKLOAD)
                row = cur.fetchone()
                if not row:
                    return self._mock_workload()

                cur.execute(aq.PROFILE_TOP_QUERIES)
                top_queries = [{"query": r[0][:200], "calls": r[1], "mean_ms": float(r[2])} for r in cur.fetchall()]

                cur.execute(aq.PROFILE_HOT_TABLES)
                hot_tables = [r[0] for r in cur.fetchall()]

                cur.execute(aq.PROFILE_CONNECTIONS)
                conn_row = cur.fetchone()
                conn_avg = conn_row[0] if conn_row else 0
                conn_peak = conn_row[1] if conn_row else 0

                return WorkloadProfile(
                    total_queries=int(row[0] or 0),
                    total_calls=int(row[1] or 0),
                    reads_pct=float(row[2] or 50),
                    writes_pct=float(row[3] or 50),
                    avg_qps=float(row[4] or 0),
                    peak_qps=float(row[5] or 0),
                    avg_tps=float(row[6] or 0),
                    p99_latency_ms=float(row[7] or 0),
                    top_queries=top_queries,
                    hot_tables=hot_tables,
                    connection_count_avg=int(conn_avg),
                    connection_count_peak=int(conn_peak),
                )
        except Exception as e:
            logger.error(f"Live workload profiling failed: {e}")
            return self._mock_workload()

    def _live_discover_cosmosdb(
        self, endpoint: str, database: str, user: str = "", password: str = ""
    ) -> DatabaseProfile:
        """Connect to a live Cosmos DB account and discover its schema/configuration."""
        try:
            from agents.provisioning.cosmos_adapter import CosmosDiscoveryAdapter
        except ImportError:
            logger.warning("azure-cosmos not installed - returning CosmosDB mock data")
            return self._mock_discover_cosmosdb(database)

        try:
            adapter = CosmosDiscoveryAdapter(
                endpoint=endpoint,
                key=password,
                database_name=database,
            )
            return adapter.discover()
        except Exception as e:
            logger.error(f"Live CosmosDB discover failed: {e}")
            return self._mock_discover_cosmosdb(database)

    def _live_workload_cosmosdb(self, profile_data: dict) -> WorkloadProfile:
        """Build a heuristic workload profile from discovered CosmosDB container throughput data.

        Workload metrics are estimated from provisioned RU/s, not observed usage.
        The workload_source field is set to "heuristic" to surface this caveat.
        """
        profile = profile_data.get("_profile") if profile_data else None
        if not profile or not profile.databases:
            logger.warning("No profile data for CosmosDB workload - returning mock data")
            return self._mock_workload_cosmosdb()

        db = profile.databases[0]
        total_ru = db.cosmos_ru_per_sec or 0
        container_count = db.table_count or 1

        avg_qps = total_ru * 0.7
        avg_tps = total_ru * 0.3
        peak_qps = avg_qps * 3
        connection_avg = container_count * 8
        connection_peak = container_count * 25

        return WorkloadProfile(
            total_queries=int(avg_qps * 86400),
            total_calls=int((avg_qps + avg_tps) * 86400),
            reads_pct=70.0,
            writes_pct=30.0,
            avg_qps=round(avg_qps, 1),
            peak_qps=round(peak_qps, 1),
            avg_tps=round(avg_tps, 1),
            p99_latency_ms=10.0,
            top_queries=[],
            hot_tables=[],
            connection_count_avg=int(connection_avg),
            connection_count_peak=int(connection_peak),
            workload_source="heuristic",
        )
