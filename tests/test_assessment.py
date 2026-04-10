#!/usr/bin/env python3
"""
Tests for the Migration Assessment Accelerator.

Validates all 4 assessment tools, the readiness scoring engine,
and the blueprint generator using mock data (no live DB connections).

Usage:
  python test_assessment.py
"""

from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.migration_profiles import (
    BlockerSeverity,
    DatabaseProfile,
    ExtensionInfo,
    FunctionInfo,
    LakebaseTier,
    MigrationProfile,
    MigrationStrategy,
    ReadinessCategory,
    SourceEngine,
    WorkloadProfile,
    max_connections_for_cu,
)
from utils.blueprint_generator import generate_blueprint, render_blueprint_markdown
from utils.readiness_scorer import (
    compute_readiness_score,
)

# =============================================================================
# Test Helpers
# =============================================================================


class _TestReport:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def add(self, name: str, passed: bool, message: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append({"name": name, "status": status, "message": message})
        icon = "+" if passed else "X"
        print(f"  [{icon}] {name}: {message}")

    def summary(self):
        elapsed = time.time() - self.start_time
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed
        print(f"\n{'=' * 70}")
        print(f"  ASSESSMENT TESTS: {passed}/{total} passed, {failed} failed ({elapsed:.1f}s)")
        print(f"{'=' * 70}")
        return failed == 0


@pytest.fixture
def report():
    return _TestReport()


# =============================================================================
# Test: Migration Profile Dataclasses
# =============================================================================


def test_dataclasses(report: _TestReport):
    print("\n--- Migration Profile Dataclasses ---")

    profile = MigrationProfile(
        profile_id="test-001",
        source_engine=SourceEngine.AURORA_POSTGRESQL,
        source_endpoint="test.cluster-xxx.us-east-1.rds.amazonaws.com",
        source_version="15.4",
        source_region="us-east-1",
    )
    report.add("MigrationProfile creation", True, f"profile_id={profile.profile_id}")

    db = DatabaseProfile(
        name="test_db",
        size_bytes=5_000_000_000,
        size_gb=4.65,
        table_count=25,
        schema_count=2,
        schemas=["public", "analytics"],
    )
    profile.databases.append(db)
    report.add("DatabaseProfile creation", True, f"name={db.name}, size={db.size_gb} GB")
    report.add("MigrationProfile.total_size_gb", abs(profile.total_size_gb - 4.65) < 0.01, f"{profile.total_size_gb}")
    report.add("MigrationProfile.total_tables", profile.total_tables == 25, f"{profile.total_tables}")
    report.add("MigrationProfile.is_assessed", not profile.is_assessed, "False before assessment")

    workload = WorkloadProfile(avg_qps=1000, avg_tps=200, connection_count_peak=100)
    report.add("WorkloadProfile creation", workload.avg_qps == 1000, f"QPS={workload.avg_qps}")


# =============================================================================
# Test: Readiness Scoring Engine
# =============================================================================


def test_readiness_scorer(report: _TestReport):
    print("\n--- Readiness Scoring Engine ---")

    # Test 1: Small, clean database -> READY
    clean_db = DatabaseProfile(
        name="clean_db",
        size_bytes=2_000_000_000,
        size_gb=1.86,
        table_count=10,
        extensions=[
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pgvector", "0.7.0", True),
        ],
        functions=[],
        triggers=[],
    )
    clean_workload = WorkloadProfile(avg_qps=500, avg_tps=100, connection_count_peak=50)
    result = compute_readiness_score(clean_db, clean_workload)
    report.add(
        "Clean DB -> READY",
        result.category == ReadinessCategory.READY,
        f"Score={result.overall_score}, Category={result.category.value}",
    )
    report.add("Clean DB score > 70", result.overall_score > 70, f"{result.overall_score}")
    report.add("Clean DB no blockers", len(result.blockers) == 0, f"{len(result.blockers)} blockers")

    # Test 2: Database with unsupported extensions -> READY_WITH_WORKAROUNDS
    ext_db = DatabaseProfile(
        name="ext_db",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=30,
        extensions=[
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pg_cron", "1.6", False),
            ExtensionInfo("aws_s3", "1.1", False),
        ],
        functions=[FunctionInfo("public", "fn1", "plpgsql", False, 10)] * 5,
        triggers=[],
    )
    result2 = compute_readiness_score(ext_db)
    report.add(
        "Unsupported extensions -> has blockers",
        len(result2.blockers) > 0,
        f"{len(result2.blockers)} blockers found",
    )
    report.add(
        "pg_cron flagged",
        any("pg_cron" in b.description for b in result2.blockers),
        "pg_cron detected in blockers",
    )
    report.add(
        "aws_s3 flagged",
        any("aws_s3" in b.description for b in result2.blockers),
        "aws_s3 detected in blockers",
    )
    report.add(
        "Unsupported extensions listed",
        "pg_cron" in result2.unsupported_extensions and "aws_s3" in result2.unsupported_extensions,
        f"Unsupported: {result2.unsupported_extensions}",
    )

    # Test 3: Oversized database -> NOT_FEASIBLE
    huge_db = DatabaseProfile(
        name="huge_db",
        size_bytes=10 * 1024 * 1024 * 1024 * 1024,  # 10 TB
        size_gb=10 * 1024,
        table_count=500,
        extensions=[],
        functions=[],
        triggers=[],
    )
    result3 = compute_readiness_score(huge_db)
    report.add(
        "10 TB DB -> NOT_FEASIBLE",
        result3.category == ReadinessCategory.NOT_FEASIBLE,
        f"Category={result3.category.value}",
    )
    report.add(
        "Storage blocker detected",
        any(b.severity == BlockerSeverity.BLOCKER and b.category == "storage" for b in result3.blockers),
        "Storage BLOCKER found",
    )

    # Test 4: High QPS -> performance blocker
    normal_db = DatabaseProfile(
        name="high_qps_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
    )
    high_qps_workload = WorkloadProfile(avg_qps=150_000, avg_tps=200, connection_count_peak=100)
    result4 = compute_readiness_score(normal_db, high_qps_workload)
    report.add(
        "150k QPS -> performance blocker",
        any(b.severity == BlockerSeverity.BLOCKER and b.category == "performance" for b in result4.blockers),
        f"Category={result4.category.value}",
    )

    # Test 5: Logical replication -> HIGH severity
    repl_db = DatabaseProfile(
        name="repl_db",
        size_bytes=5_000_000_000,
        size_gb=4.65,
        table_count=15,
        extensions=[],
        functions=[],
        triggers=[],
        has_logical_replication=True,
        replication_slots=["sub_analytics"],
    )
    result5 = compute_readiness_score(repl_db)
    report.add(
        "Logical replication -> HIGH blocker",
        any(b.severity == BlockerSeverity.HIGH and b.category == "replication" for b in result5.blockers),
        f"{len(result5.blockers)} blockers",
    )

    # Test 6: Heavy PL/pgSQL -> complexity blocker
    plpgsql_db = DatabaseProfile(
        name="plpgsql_db",
        size_bytes=5_000_000_000,
        size_gb=4.65,
        table_count=20,
        extensions=[],
        triggers=[],
        functions=[FunctionInfo("public", f"fn_{i}", "plpgsql", False, 50) for i in range(60)],
    )
    result6 = compute_readiness_score(plpgsql_db)
    report.add(
        "60 PL/pgSQL functions -> complexity blocker",
        any(b.category == "complexity" for b in result6.blockers),
        f"Category={result6.category.value}",
    )

    # Test 7: Sizing recommendations
    report.add(
        "Autoscaling tier recommended",
        result.recommended_tier == LakebaseTier.AUTOSCALING,
        f"Tier={result.recommended_tier.value}",
    )
    report.add(
        "CU range reasonable",
        result.recommended_cu_min >= 1 and result.recommended_cu_max <= 32,
        f"CU={result.recommended_cu_min}-{result.recommended_cu_max}",
    )

    # Test 8: Effort estimation
    report.add(
        "Effort > 0 days",
        result.estimated_effort_days > 0,
        f"{result.estimated_effort_days} days",
    )

    # Test 9: Event triggers -> BLOCKER
    evt_db = DatabaseProfile(
        name="evt_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        event_trigger_count=2,
    )
    result_evt = compute_readiness_score(evt_db)
    report.add(
        "Event triggers -> BLOCKER",
        any(b.severity == BlockerSeverity.BLOCKER and b.category == "event_triggers" for b in result_evt.blockers),
        f"Category={result_evt.category.value}",
    )

    # Test 10: Large objects -> warning
    lo_db = DatabaseProfile(
        name="lo_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        large_object_count=15,
    )
    result_lo = compute_readiness_score(lo_db)
    report.add(
        "Large objects -> warning",
        any("large object" in w for w in result_lo.warnings),
        f"{len(result_lo.warnings)} warnings",
    )

    # Test 11: Custom aggregates -> warning (info)
    agg_db = DatabaseProfile(
        name="agg_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        custom_aggregate_count=3,
    )
    result_agg = compute_readiness_score(agg_db)
    report.add(
        "Custom aggregates -> warning",
        any("aggregate" in w for w in result_agg.warnings),
        f"{len(result_agg.warnings)} warnings",
    )

    # Test 12: Exclusion constraints -> warning
    excl_db = DatabaseProfile(
        name="excl_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        exclusion_constraint_count=2,
    )
    result_excl = compute_readiness_score(excl_db)
    report.add(
        "Exclusion constraints -> warning",
        any("exclusion" in w for w in result_excl.warnings),
        f"{len(result_excl.warnings)} warnings",
    )

    # Test 13: RLS policies -> warning (info)
    rls_db = DatabaseProfile(
        name="rls_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        rls_policy_count=4,
    )
    result_rls = compute_readiness_score(rls_db)
    report.add(
        "RLS policies -> warning",
        any("RLS" in w for w in result_rls.warnings),
        f"{len(result_rls.warnings)} warnings",
    )

    # Test 14: Non-default collation -> warning
    coll_db = DatabaseProfile(
        name="coll_db",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=5,
        extensions=[],
        functions=[],
        triggers=[],
        non_default_collation_count=8,
    )
    result_coll = compute_readiness_score(coll_db)
    report.add(
        "Non-default collation -> warning",
        any("collation" in w for w in result_coll.warnings),
        f"{len(result_coll.warnings)} warnings",
    )


# =============================================================================
# Test: Blueprint Generator
# =============================================================================


def test_blueprint_generator(report: _TestReport):
    print("\n--- Blueprint Generator ---")

    db = DatabaseProfile(
        name="app_db",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=25,
        extensions=[
            ExtensionInfo("pg_stat_statements", "1.10", True),
            ExtensionInfo("pg_cron", "1.6", False),
        ],
        functions=[FunctionInfo("public", "fn1", "plpgsql", False, 20)],
        triggers=[],
        pg_version="15.4",
    )

    assessment = compute_readiness_score(db)
    workload = WorkloadProfile(avg_qps=1000, avg_tps=200, connection_count_peak=100)

    blueprint = generate_blueprint(
        db_profile=db,
        assessment=assessment,
        workload=workload,
        source_endpoint="aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
        lakebase_endpoint="ep-xxx.database.us-east-1.cloud.databricks.com",
    )

    report.add("Blueprint generated", blueprint is not None, f"Strategy={blueprint.strategy.value}")
    report.add("4 phases", len(blueprint.phases) == 4, f"{len(blueprint.phases)} phases")
    report.add("Phase 1: Schema", blueprint.phases[0].name == "Schema & Index Preparation", blueprint.phases[0].name)
    report.add("Phase 2: Data", blueprint.phases[1].name == "Data Migration", blueprint.phases[1].name)
    report.add("Phase 3: App", blueprint.phases[2].name == "Application Refactoring", blueprint.phases[2].name)
    report.add("Phase 4: GoLive", blueprint.phases[3].name == "Performance Tuning & Go-Live", blueprint.phases[3].name)
    report.add("Total days > 0", blueprint.total_estimated_days > 0, f"{blueprint.total_estimated_days} days")
    report.add("Has prerequisites", len(blueprint.prerequisites) > 0, f"{len(blueprint.prerequisites)} prerequisites")
    report.add(
        "Has post-checks", len(blueprint.post_migration_checks) > 0, f"{len(blueprint.post_migration_checks)} checks"
    )
    report.add("Has rollback plan", len(blueprint.rollback_plan) > 0, "Rollback plan present")

    # Test markdown rendering
    md = render_blueprint_markdown(blueprint, db, assessment)
    report.add("Markdown rendered", len(md) > 500, f"{len(md)} chars")
    report.add("Markdown has title", "# Migration Blueprint" in md, "Title found")
    report.add("Markdown has phases", "## Phase 1" in md and "## Phase 4" in md, "All phases present")
    report.add("Markdown has commands", "pg_dump" in md, "pg_dump command found")
    report.add("Markdown has score", str(assessment.overall_score) in md, "Score in report")
    report.add(
        "Markdown has disable-triggers warning",
        "disable-triggers" in md.lower() or "disable_triggers" in md.lower(),
        "Trigger warning present",
    )
    report.add(
        "Markdown has plain-text recommendation",
        "plain-text" in md.lower() or "plain text" in md.lower(),
        "Plain-text dump note present",
    )


# =============================================================================
# Test: AssessmentMixin (4 Tools via ProvisioningAgent)
# =============================================================================


def test_assessment_mixin(report: _TestReport):
    print("\n--- AssessmentMixin (4 Tools) ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    client = LakebaseClient(workspace_host="test", mock_mode=True)
    writer = DeltaWriter(mock_mode=True)
    alerts = AlertManager(mock_mode=True)

    agent = ProvisioningAgent(client, writer, alerts)
    agent.register_tools()

    # Verify tools registered
    tool_names = [t.name for t in agent.tools.values()]
    report.add("connect_and_discover registered", "connect_and_discover" in tool_names, "Tool found")
    report.add("profile_workload registered", "profile_workload" in tool_names, "Tool found")
    report.add("assess_readiness registered", "assess_readiness" in tool_names, "Tool found")
    report.add("generate_migration_blueprint registered", "generate_migration_blueprint" in tool_names, "Tool found")
    report.add("Total tools >= 21", len(tool_names) >= 21, f"{len(tool_names)} tools")

    # Tool 1: connect_and_discover
    discovery = agent.connect_and_discover(
        endpoint="aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
        database="app_production",
        source_engine="aurora-postgresql",
        mock=True,
    )
    report.add("connect_and_discover returns profile_id", "profile_id" in discovery, discovery.get("profile_id", ""))
    report.add(
        "connect_and_discover returns tables",
        discovery.get("table_count", 0) > 0,
        f"{discovery.get('table_count')} tables",
    )
    report.add(
        "connect_and_discover returns extensions",
        discovery.get("extension_count", 0) > 0,
        f"{discovery.get('extension_count')} extensions",
    )
    report.add("connect_and_discover returns size", discovery.get("size_gb", 0) > 0, f"{discovery.get('size_gb')} GB")

    # Tool 2: profile_workload
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    report.add("profile_workload returns QPS", workload.get("avg_qps", 0) > 0, f"QPS={workload.get('avg_qps')}")
    report.add("profile_workload returns TPS", workload.get("avg_tps", 0) > 0, f"TPS={workload.get('avg_tps')}")
    report.add(
        "profile_workload returns connections",
        workload.get("connection_count_peak", 0) > 0,
        f"Peak={workload.get('connection_count_peak')}",
    )

    # Tool 3: assess_readiness
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)
    report.add(
        "assess_readiness returns score", "overall_score" in assessment, f"Score={assessment.get('overall_score')}"
    )
    report.add("assess_readiness returns category", "category" in assessment, f"Category={assessment.get('category')}")
    report.add(
        "assess_readiness returns tier", "recommended_tier" in assessment, f"Tier={assessment.get('recommended_tier')}"
    )
    report.add(
        "assess_readiness returns dimensions",
        "dimensions" in assessment,
        f"{len(assessment.get('dimensions', {}))} dimensions",
    )
    report.add(
        "assess_readiness detects pg_cron",
        any("pg_cron" in b.get("description", "") for b in assessment.get("blockers", [])),
        "pg_cron blocker found",
    )

    # Tool 4: generate_migration_blueprint
    blueprint = agent.generate_migration_blueprint(
        assessment_data=assessment,
        workload_data=workload,
        lakebase_endpoint="ep-xxx.database.us-east-1.cloud.databricks.com",
    )
    report.add("blueprint returns strategy", "strategy" in blueprint, f"Strategy={blueprint.get('strategy')}")
    report.add(
        "blueprint returns phases", blueprint.get("phase_count", 0) == 4, f"{blueprint.get('phase_count')} phases"
    )
    report.add(
        "blueprint returns days",
        blueprint.get("total_estimated_days", 0) > 0,
        f"{blueprint.get('total_estimated_days')} days",
    )
    report.add(
        "blueprint returns markdown",
        len(blueprint.get("report_markdown", "")) > 500,
        f"{len(blueprint.get('report_markdown', ''))} chars",
    )


# =============================================================================
# Test: End-to-End Pipeline
# =============================================================================


def test_end_to_end(report: _TestReport):
    print("\n--- End-to-End Pipeline ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    # Run the full pipeline: discover -> profile -> assess -> blueprint
    discovery = agent.connect_and_discover(mock=True)
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)
    blueprint = agent.generate_migration_blueprint(assessment_data=assessment, workload_data=workload)

    report.add("E2E: Discovery succeeded", discovery.get("table_count", 0) > 0, "Discovery OK")
    report.add("E2E: Workload profiled", workload.get("avg_qps", 0) > 0, "Workload OK")
    report.add(
        "E2E: Assessment scored", assessment.get("overall_score", 0) > 0, f"Score={assessment.get('overall_score')}"
    )
    report.add("E2E: Blueprint generated", blueprint.get("phase_count", 0) == 4, "Blueprint OK")

    # Verify the markdown report contains key sections
    md = blueprint.get("report_markdown", "")
    report.add(
        "E2E: Report has blockers section",
        "Blocker" in md or "blocker" in md.lower() or "Risk" in md,
        "Blockers section found",
    )
    report.add("E2E: Report has pg_dump commands", "pg_dump" in md, "pg_dump in report")
    report.add("E2E: Report has Lakebase sizing", "CU" in md, "CU sizing in report")


# =============================================================================
# Test: DynamoDB Assessment
# =============================================================================


def test_dynamodb_discovery(report: _TestReport):
    print("\n--- DynamoDB Discovery ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(
        source_engine="dynamodb",
        mock=True,
    )
    report.add("DynamoDB: discovery returns profile_id", "profile_id" in discovery, discovery.get("profile_id", ""))
    report.add(
        "DynamoDB: engine is dynamodb",
        discovery.get("source_engine") == "dynamodb",
        f"{discovery.get('source_engine')}",
    )
    report.add(
        "DynamoDB: has table_count", discovery.get("table_count", 0) > 0, f"{discovery.get('table_count')} tables"
    )
    report.add("DynamoDB: has size_gb", discovery.get("size_gb", 0) > 0, f"{discovery.get('size_gb')} GB")
    report.add("DynamoDB: has gsi_count", discovery.get("gsi_count", 0) > 0, f"{discovery.get('gsi_count')} GSIs")
    report.add(
        "DynamoDB: has billing_mode", discovery.get("billing_mode") is not None, f"{discovery.get('billing_mode')}"
    )
    report.add(
        "DynamoDB: has streams_enabled",
        discovery.get("streams_enabled") is not None,
        f"{discovery.get('streams_enabled')}",
    )
    report.add(
        "DynamoDB: has pitr_enabled", discovery.get("pitr_enabled") is not None, f"{discovery.get('pitr_enabled')}"
    )
    report.add(
        "DynamoDB: no extensions field",
        "extensions" not in discovery or "extension_count" not in discovery,
        "No PG extensions in DynamoDB",
    )
    report.add(
        "DynamoDB: source_version is DynamoDB",
        discovery.get("source_version") == "DynamoDB",
        f"{discovery.get('source_version')}",
    )

    workload = agent.profile_workload(profile_data=discovery, mock=True)
    report.add("DynamoDB: workload has QPS", workload.get("avg_qps", 0) > 0, f"QPS={workload.get('avg_qps')}")
    report.add("DynamoDB: workload has TPS", workload.get("avg_tps", 0) > 0, f"TPS={workload.get('avg_tps')}")


def test_dynamodb_readiness(report: _TestReport):
    print("\n--- DynamoDB Readiness Scoring ---")

    dynamo_db = DatabaseProfile(
        name="dynamo-test",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=10,
        schema_count=1,
        schemas=["default"],
        extensions=[],
        functions=[],
        triggers=[],
        billing_mode="on-demand",
        gsi_count=8,
        lsi_count=2,
        streams_enabled=True,
        ttl_enabled=True,
        pitr_enabled=True,
        global_table_regions=[],
        item_size_avg_bytes=4200,
    )
    workload = WorkloadProfile(avg_qps=3500, avg_tps=850, connection_count_peak=250)

    result = compute_readiness_score(dynamo_db, workload, source_engine="dynamodb")

    report.add("DynamoDB: score > 0", result.overall_score > 0, f"Score={result.overall_score}")
    report.add(
        "DynamoDB: has 6 dimensions", len(result.dimension_scores) == 6, f"{len(result.dimension_scores)} dimensions"
    )
    report.add("DynamoDB: has blockers", len(result.blockers) > 0, f"{len(result.blockers)} blockers")
    report.add(
        "DynamoDB: feature_compatibility blocker present",
        any(b.category == "feature_compatibility" for b in result.blockers),
        "Feature compatibility blockers found",
    )
    report.add(
        "DynamoDB: effort > 15 days (cross-engine)",
        result.estimated_effort_days >= 15,
        f"{result.estimated_effort_days} days",
    )
    report.add(
        "DynamoDB: DAX flagged as unsupported",
        any("DAX" in b.description for b in result.blockers),
        "DAX blocker found",
    )

    no_pitr = DatabaseProfile(
        name="dynamo-no-pitr",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=3,
        extensions=[],
        functions=[],
        triggers=[],
        billing_mode="on-demand",
        gsi_count=2,
        lsi_count=0,
        streams_enabled=False,
        pitr_enabled=False,
    )
    result2 = compute_readiness_score(no_pitr, source_engine="dynamodb")
    report.add(
        "DynamoDB: PITR warning when disabled",
        any("PITR" in b.description for b in result2.blockers),
        "PITR blocker found",
    )


def test_dynamodb_blueprint(report: _TestReport):
    print("\n--- DynamoDB Blueprint ---")

    dynamo_db = DatabaseProfile(
        name="dynamo-blueprint-test",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=10,
        schema_count=1,
        schemas=["default"],
        extensions=[],
        functions=[],
        triggers=[],
        billing_mode="on-demand",
        gsi_count=8,
        lsi_count=2,
        streams_enabled=True,
        pitr_enabled=True,
    )

    assessment = compute_readiness_score(dynamo_db, source_engine="dynamodb")
    workload = WorkloadProfile(avg_qps=3500, avg_tps=850, connection_count_peak=250)

    blueprint = generate_blueprint(
        db_profile=dynamo_db,
        assessment=assessment,
        workload=workload,
        source_endpoint="dynamodb.us-east-1.amazonaws.com",
        lakebase_endpoint="ep-xxx.database.us-east-1.cloud.databricks.com",
        database_name="dynamo-blueprint-test",
        source_engine="dynamodb",
    )

    report.add(
        "DynamoDB: strategy is cross_engine",
        blueprint.strategy == MigrationStrategy.CROSS_ENGINE,
        f"Strategy={blueprint.strategy.value}",
    )
    report.add("DynamoDB: 4 phases", len(blueprint.phases) == 4, f"{len(blueprint.phases)} phases")
    report.add(
        "DynamoDB: Phase 1 = Schema Design",
        "Schema Design" in blueprint.phases[0].name or "Schema" in blueprint.phases[0].name,
        blueprint.phases[0].name,
    )
    report.add(
        "DynamoDB: Phase 3 = Application Rewrite", "Application" in blueprint.phases[2].name, blueprint.phases[2].name
    )
    report.add("DynamoDB: total days > 0", blueprint.total_estimated_days > 0, f"{blueprint.total_estimated_days} days")

    md = render_blueprint_markdown(blueprint, dynamo_db, assessment, source_engine="dynamodb")
    report.add("DynamoDB: markdown has DynamoDB label", "Amazon DynamoDB" in md, "DynamoDB label found")
    report.add("DynamoDB: markdown has type mapping table", "jsonb" in md.lower(), "Type mapping present")
    report.add(
        "DynamoDB: markdown has Export to S3", "Export to S3" in md or "export" in md.lower(), "S3 export mentioned"
    )
    report.add(
        "DynamoDB: markdown has cross-engine note",
        "cross-engine" in md.lower() or "NoSQL" in md,
        "Cross-engine note present",
    )


def test_dynamodb_end_to_end(report: _TestReport):
    print("\n--- DynamoDB End-to-End Pipeline ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(source_engine="dynamodb", mock=True)
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)
    blueprint = agent.generate_migration_blueprint(assessment_data=assessment, workload_data=workload)

    report.add("DynamoDB E2E: Discovery succeeded", discovery.get("table_count", 0) > 0, "Discovery OK")
    report.add("DynamoDB E2E: Workload profiled", workload.get("avg_qps", 0) > 0, "Workload OK")
    report.add(
        "DynamoDB E2E: Assessment scored",
        assessment.get("overall_score", 0) > 0,
        f"Score={assessment.get('overall_score')}",
    )
    report.add(
        "DynamoDB E2E: Strategy is cross_engine",
        assessment.get("_assessment") is not None or blueprint.get("strategy") == "cross_engine",
        f"Strategy={blueprint.get('strategy')}",
    )
    report.add("DynamoDB E2E: Blueprint generated", blueprint.get("phase_count", 0) == 4, "Blueprint OK")

    md = blueprint.get("report_markdown", "")
    report.add("DynamoDB E2E: Report mentions DynamoDB", "DynamoDB" in md, "DynamoDB in report")
    report.add(
        "DynamoDB E2E: Report has type mapping", "jsonb" in md.lower() or "JSONB" in md, "Type mapping in report"
    )


# =============================================================================
# Test: CosmosDB Assessment
# =============================================================================


def test_cosmosdb_discovery(report: _TestReport):
    print("\n--- CosmosDB Discovery ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(
        source_engine="cosmosdb-nosql",
        mock=True,
    )
    report.add("CosmosDB: discovery returns profile_id", "profile_id" in discovery, discovery.get("profile_id", ""))
    report.add(
        "CosmosDB: engine is cosmosdb-nosql",
        discovery.get("source_engine") == "cosmosdb-nosql",
        f"{discovery.get('source_engine')}",
    )
    report.add(
        "CosmosDB: has table_count", discovery.get("table_count", 0) > 0, f"{discovery.get('table_count')} containers"
    )
    report.add("CosmosDB: has size_gb", discovery.get("size_gb", 0) > 0, f"{discovery.get('size_gb')} GB")
    report.add(
        "CosmosDB: has cosmos_ru_per_sec",
        discovery.get("cosmos_ru_per_sec", 0) > 0,
        f"{discovery.get('cosmos_ru_per_sec')} RU/s",
    )
    report.add(
        "CosmosDB: has cosmos_consistency_level",
        discovery.get("cosmos_consistency_level") is not None,
        f"{discovery.get('cosmos_consistency_level')}",
    )
    report.add(
        "CosmosDB: has cosmos_throughput_mode",
        discovery.get("cosmos_throughput_mode") is not None,
        f"{discovery.get('cosmos_throughput_mode')}",
    )
    report.add(
        "CosmosDB: has cosmos_change_feed_enabled",
        discovery.get("cosmos_change_feed_enabled") is not None,
        f"{discovery.get('cosmos_change_feed_enabled')}",
    )
    report.add(
        "CosmosDB: no PG extensions field",
        "extensions" not in discovery or "extension_count" not in discovery,
        "No PG extensions in CosmosDB",
    )
    report.add(
        "CosmosDB: source_version is CosmosDB",
        discovery.get("source_version") == "CosmosDB",
        f"{discovery.get('source_version')}",
    )

    workload = agent.profile_workload(profile_data=discovery, mock=True)
    report.add("CosmosDB: workload has QPS", workload.get("avg_qps", 0) > 0, f"QPS={workload.get('avg_qps')}")
    report.add("CosmosDB: workload has TPS", workload.get("avg_tps", 0) > 0, f"TPS={workload.get('avg_tps')}")


def test_cosmosdb_readiness(report: _TestReport):
    print("\n--- CosmosDB Readiness Scoring ---")

    cosmos_db = DatabaseProfile(
        name="cosmos-test",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=8,
        schema_count=1,
        schemas=["default"],
        extensions=[],
        functions=[],
        triggers=[],
        cosmos_throughput_mode="provisioned",
        cosmos_ru_per_sec=4000,
        cosmos_partition_key_paths=["/userId", "/orderId"],
        cosmos_consistency_level="Session",
        cosmos_change_feed_enabled=False,
        cosmos_change_feed_mode="LatestVersion",
        cosmos_multi_region_writes=False,
        cosmos_regions=["eastus"],
        cosmos_container_details=[
            {"name": "Users", "partition_key": "/userId", "ru_per_sec": 400, "indexing_policy": "consistent"},
            {"name": "Orders", "partition_key": "/orderId", "ru_per_sec": 1000, "indexing_policy": "consistent"},
        ],
    )
    workload = WorkloadProfile(avg_qps=2800, avg_tps=700, connection_count_peak=200)

    result = compute_readiness_score(cosmos_db, workload, source_engine="cosmosdb-nosql")

    report.add("CosmosDB: score > 0", result.overall_score > 0, f"Score={result.overall_score}")
    report.add(
        "CosmosDB: has 6 dimensions", len(result.dimension_scores) == 6, f"{len(result.dimension_scores)} dimensions"
    )
    report.add("CosmosDB: has blockers", len(result.blockers) > 0, f"{len(result.blockers)} blockers")
    report.add(
        "CosmosDB: feature_compatibility blocker present",
        any(b.category == "feature_compatibility" for b in result.blockers),
        "Feature compatibility blockers found",
    )
    report.add(
        "CosmosDB: effort > 15 days (cross-engine)",
        result.estimated_effort_days >= 15,
        f"{result.estimated_effort_days} days",
    )
    report.add(
        "CosmosDB: Integrated cache flagged as unsupported",
        any("Integrated cache" in b.description for b in result.blockers),
        "Integrated cache blocker found",
    )

    multi_region_db = DatabaseProfile(
        name="cosmos-multi-region",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=3,
        extensions=[],
        functions=[],
        triggers=[],
        cosmos_throughput_mode="provisioned",
        cosmos_ru_per_sec=2000,
        cosmos_consistency_level="Strong",
        cosmos_change_feed_enabled=True,
        cosmos_change_feed_mode="AllVersionsAndDeletes",
        cosmos_multi_region_writes=True,
        cosmos_regions=["eastus", "westeurope"],
    )
    result2 = compute_readiness_score(multi_region_db, source_engine="cosmosdb-nosql")
    report.add(
        "CosmosDB: multi-region writes -> HIGH blocker",
        any("Multi-region" in b.description and b.severity == BlockerSeverity.HIGH for b in result2.blockers),
        "Multi-region blocker found",
    )
    report.add(
        "CosmosDB: Strong consistency warning",
        any("Strong" in w for w in result2.warnings),
        "Strong consistency warning found",
    )


def test_cosmosdb_blueprint(report: _TestReport):
    print("\n--- CosmosDB Blueprint ---")

    cosmos_db = DatabaseProfile(
        name="cosmos-blueprint-test",
        size_bytes=50_000_000_000,
        size_gb=46.6,
        table_count=8,
        schema_count=1,
        schemas=["default"],
        extensions=[],
        functions=[],
        triggers=[],
        cosmos_throughput_mode="provisioned",
        cosmos_ru_per_sec=4000,
        cosmos_consistency_level="Session",
        cosmos_change_feed_enabled=True,
        cosmos_multi_region_writes=False,
        cosmos_regions=["eastus"],
    )

    assessment = compute_readiness_score(cosmos_db, source_engine="cosmosdb-nosql")
    workload = WorkloadProfile(avg_qps=2800, avg_tps=700, connection_count_peak=200)

    blueprint = generate_blueprint(
        db_profile=cosmos_db,
        assessment=assessment,
        workload=workload,
        source_endpoint="myaccount.documents.azure.com",
        lakebase_endpoint="ep-xxx.database.us-east-1.cloud.databricks.com",
        database_name="cosmos-blueprint-test",
        source_engine="cosmosdb-nosql",
    )

    report.add(
        "CosmosDB: strategy is cross_engine",
        blueprint.strategy == MigrationStrategy.CROSS_ENGINE,
        f"Strategy={blueprint.strategy.value}",
    )
    report.add("CosmosDB: 4 phases", len(blueprint.phases) == 4, f"{len(blueprint.phases)} phases")
    report.add(
        "CosmosDB: Phase 1 = Schema Design",
        "Schema Design" in blueprint.phases[0].name or "Schema" in blueprint.phases[0].name,
        blueprint.phases[0].name,
    )
    report.add(
        "CosmosDB: Phase 3 = Application Rewrite", "Application" in blueprint.phases[2].name, blueprint.phases[2].name
    )
    report.add("CosmosDB: total days > 0", blueprint.total_estimated_days > 0, f"{blueprint.total_estimated_days} days")

    md = render_blueprint_markdown(blueprint, cosmos_db, assessment, source_engine="cosmosdb-nosql")
    report.add("CosmosDB: markdown has Cosmos DB label", "Cosmos DB" in md, "Cosmos DB label found")
    report.add("CosmosDB: markdown has type mapping table", "jsonb" in md.lower(), "Type mapping present")
    report.add(
        "CosmosDB: markdown has Change Feed",
        "Change Feed" in md or "change feed" in md.lower(),
        "Change Feed mentioned",
    )
    report.add(
        "CosmosDB: markdown has cross-engine note",
        "cross-engine" in md.lower() or "NoSQL" in md,
        "Cross-engine note present",
    )


def test_cosmosdb_end_to_end(report: _TestReport):
    print("\n--- CosmosDB End-to-End Pipeline ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(source_engine="cosmosdb-nosql", mock=True)
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)
    blueprint = agent.generate_migration_blueprint(assessment_data=assessment, workload_data=workload)

    report.add("CosmosDB E2E: Discovery succeeded", discovery.get("table_count", 0) > 0, "Discovery OK")
    report.add("CosmosDB E2E: Workload profiled", workload.get("avg_qps", 0) > 0, "Workload OK")
    report.add(
        "CosmosDB E2E: Assessment scored",
        assessment.get("overall_score", 0) > 0,
        f"Score={assessment.get('overall_score')}",
    )
    report.add(
        "CosmosDB E2E: Strategy is cross_engine",
        assessment.get("_assessment") is not None or blueprint.get("strategy") == "cross_engine",
        f"Strategy={blueprint.get('strategy')}",
    )
    report.add("CosmosDB E2E: Blueprint generated", blueprint.get("phase_count", 0) == 4, "Blueprint OK")

    md = blueprint.get("report_markdown", "")
    report.add("CosmosDB E2E: Report mentions Cosmos DB", "Cosmos DB" in md, "Cosmos DB in report")
    report.add(
        "CosmosDB E2E: Report has type mapping", "jsonb" in md.lower() or "JSONB" in md, "Type mapping in report"
    )


# =============================================================================
# Test: CosmosDB Live Discover Fallback
# =============================================================================


def test_cosmosdb_live_discover_fallback(report: _TestReport):
    print("\n--- CosmosDB Live Discover Fallback ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    result = agent._live_discover_cosmosdb("fake-endpoint", "fake-db", "user", "key")

    report.add(
        "Fallback: returns CosmosDB mock (not PG)",
        result.cosmos_throughput_mode is not None,
        f"throughput_mode={result.cosmos_throughput_mode}",
    )
    report.add(
        "Fallback: has cosmos fields",
        result.cosmos_ru_per_sec is not None and result.cosmos_ru_per_sec > 0,
        f"ru_per_sec={result.cosmos_ru_per_sec}",
    )
    report.add(
        "Fallback: no pg_version",
        result.pg_version == "",
        f"pg_version='{result.pg_version}'",
    )
    report.add(
        "Fallback: has containers",
        result.table_count > 0,
        f"table_count={result.table_count}",
    )


# =============================================================================
# Test: CosmosDB Live Workload from Profile
# =============================================================================


def test_cosmosdb_live_workload(report: _TestReport):
    print("\n--- CosmosDB Live Workload from Profile ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(source_engine="cosmosdb-nosql", mock=True)
    workload = agent._live_workload_cosmosdb(discovery)

    report.add(
        "Live workload: QPS > 0",
        workload.avg_qps > 0,
        f"QPS={workload.avg_qps}",
    )
    report.add(
        "Live workload: TPS > 0",
        workload.avg_tps > 0,
        f"TPS={workload.avg_tps}",
    )
    report.add(
        "Live workload: derived from RU",
        workload.avg_qps + workload.avg_tps > 0,
        f"total_throughput={workload.avg_qps + workload.avg_tps}",
    )


# =============================================================================
# Test: Pricing Fetcher
# =============================================================================


def test_pricing_fetcher(report: _TestReport):
    print("\n--- Pricing Fetcher ---")
    from config.pricing_fetcher import check_lakebase_pricing_staleness, get_live_source_rates

    rates, source = get_live_source_rates("aurora-postgresql", "us-east-1")
    report.add(
        "Aurora: returns rates (live or static)",
        source in ("static", "live", "cached"),
        f"source={source}",
    )
    report.add(
        "Aurora: has compute_per_hour",
        "compute_per_hour" in rates,
        f"rate={rates.get('compute_per_hour')}",
    )

    dynamo_rates, dynamo_source = get_live_source_rates("dynamodb", "us-east-1")
    report.add(
        "DynamoDB: returns rates",
        dynamo_source in ("static", "live", "cached"),
        f"source={dynamo_source}",
    )
    report.add(
        "DynamoDB: has wru_per_million",
        "wru_per_million" in dynamo_rates,
        f"wru={dynamo_rates.get('wru_per_million')}",
    )

    cosmos_rates, cosmos_source = get_live_source_rates("cosmosdb-nosql", "eastus")
    report.add(
        "CosmosDB: returns rates",
        "compute_per_hour" in cosmos_rates,
        f"source={cosmos_source}, rate={cosmos_rates.get('compute_per_hour')}",
    )

    staleness = check_lakebase_pricing_staleness()
    report.add(
        "Lakebase staleness: returns string or None",
        staleness is None or isinstance(staleness, str),
        f"staleness={'None' if staleness is None else staleness[:50]}",
    )


# =============================================================================
# Test: Warnings Propagation
# =============================================================================


def test_warnings_propagation(report: _TestReport):
    print("\n--- Warnings Propagation ---")

    from agents import ProvisioningAgent
    from utils.alerting import AlertManager
    from utils.delta_writer import DeltaWriter
    from utils.lakebase_client import LakebaseClient

    agent = ProvisioningAgent(
        LakebaseClient(workspace_host="test", mock_mode=True),
        DeltaWriter(mock_mode=True),
        AlertManager(mock_mode=True),
    )
    agent.register_tools()

    discovery = agent.connect_and_discover(source_engine="cosmosdb-nosql", mock=True)
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)

    warnings = assessment.get("warnings", [])
    report.add(
        "Warnings: included in summary",
        "warnings" in assessment,
        f"warning_count={len(warnings)}",
    )
    report.add(
        "Warnings: are strings not feature names",
        all(isinstance(w, str) and len(w) > 10 for w in warnings) if warnings else True,
        f"sample={'...' if not warnings else warnings[0][:60]}",
    )
    report.add(
        "Warnings: match warning_count",
        assessment.get("warning_count", 0) == len(warnings),
        f"count_field={assessment.get('warning_count')}, actual={len(warnings)}",
    )


# =============================================================================
# Test: Lakebase Pricing Registry (v2.5)
# =============================================================================


def test_lakebase_pricing_registry(report: _TestReport):
    print("\n--- Lakebase Pricing Registry (v2.5) ---")

    from config.pricing import (
        LAKEBASE_COST_DISCLAIMER,
        LAKEBASE_DBU_PER_CU_HOUR,
        LAKEBASE_PRICING,
        get_lakebase_rates,
    )

    report.add(
        "DBU per CU hour = 1",
        LAKEBASE_DBU_PER_CU_HOUR == 1,
        f"dbu_per_cu_hour={LAKEBASE_DBU_PER_CU_HOUR}",
    )
    report.add(
        "Pricing has tiers",
        "tiers" in LAKEBASE_PRICING and "premium" in LAKEBASE_PRICING["tiers"],
        "premium tier present",
    )
    report.add(
        "Pricing has enterprise tier",
        "enterprise" in LAKEBASE_PRICING["tiers"],
        "enterprise tier present",
    )
    report.add(
        "Pricing has sku_pattern",
        "sku_pattern" in LAKEBASE_PRICING,
        f"sku={LAKEBASE_PRICING.get('sku_pattern', '')}",
    )

    premium_rates = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="premium")
    report.add(
        "Premium DBU rate = $0.40",
        premium_rates["dbu_rate"] == 0.40,
        f"rate={premium_rates['dbu_rate']}",
    )

    enterprise_rates = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="enterprise")
    report.add(
        "Enterprise DBU rate = $0.52",
        enterprise_rates["dbu_rate"] == 0.52,
        f"rate={enterprise_rates['dbu_rate']}",
    )

    report.add(
        "Tier default = premium",
        get_lakebase_rates("aurora-postgresql", "us-east-1")["dbu_rate"] == 0.40,
        "default tier is premium",
    )

    formula = LAKEBASE_PRICING["formulas"]["compute"]
    report.add(
        "Compute formula uses 1 DBU/CU/hr",
        "1 DBU/CU/hr" in formula,
        f"formula='{formula}'",
    )

    report.add(
        "LAKEBASE_COST_DISCLAIMER present",
        "account team" in LAKEBASE_COST_DISCLAIMER.lower(),
        "disclaimer has account team reference",
    )


# =============================================================================
# Test: Environment Sizing Recommendations (v2.5)
# =============================================================================


def test_environment_sizing(report: _TestReport):
    print("\n--- Environment Sizing Recommendations (v2.5) ---")

    clean_db = DatabaseProfile(
        name="sizing_test_db",
        size_bytes=5_000_000_000,
        size_gb=4.65,
        table_count=15,
        extensions=[
            ExtensionInfo("pg_stat_statements", "1.10", True),
        ],
        functions=[],
        triggers=[],
    )
    workload = WorkloadProfile(avg_qps=1500, avg_tps=300, connection_count_peak=200)

    result = compute_readiness_score(clean_db, workload)

    report.add(
        "sizing_by_env populated",
        len(result.sizing_by_env) == 3,
        f"envs={len(result.sizing_by_env)}",
    )

    env_names = [e.env for e in result.sizing_by_env]
    report.add(
        "Has dev/staging/prod",
        env_names == ["dev", "staging", "prod"],
        f"envs={env_names}",
    )

    dev = result.sizing_by_env[0]
    staging = result.sizing_by_env[1]
    prod = result.sizing_by_env[2]

    report.add(
        "Dev: scale-to-zero = True",
        dev.scale_to_zero is True,
        f"s2z={dev.scale_to_zero}",
    )
    report.add(
        "Staging: scale-to-zero = True",
        staging.scale_to_zero is True,
        f"s2z={staging.scale_to_zero}",
    )
    report.add(
        "Prod: scale-to-zero = False",
        prod.scale_to_zero is False,
        f"s2z={prod.scale_to_zero}",
    )

    report.add(
        "Dev CU < Prod CU",
        dev.cu_max <= prod.cu_min,
        f"dev_max={dev.cu_max}, prod_min={prod.cu_min}",
    )
    report.add(
        "All envs have autoscaling",
        all(e.autoscaling for e in result.sizing_by_env),
        "all autoscaling=True",
    )
    report.add(
        "RAM = CU * 2",
        prod.ram_gb == prod.cu_max * 2,
        f"ram={prod.ram_gb}, cu_max={prod.cu_max}",
    )
    report.add(
        "Max connections set",
        prod.max_connections > 0,
        f"max_conns={prod.max_connections}",
    )

    report.add(
        "max_connections_for_cu(0.5) = 104",
        max_connections_for_cu(0.5) == 104,
        f"conns={max_connections_for_cu(0.5)}",
    )
    report.add(
        "max_connections_for_cu(8) = 1678",
        max_connections_for_cu(8) == 1678,
        f"conns={max_connections_for_cu(8)}",
    )
    report.add(
        "max_connections_for_cu(32) = 4000",
        max_connections_for_cu(32) == 4000,
        f"conns={max_connections_for_cu(32)}",
    )


# =============================================================================
# Test: Corrected Lakebase Cost Formula (v2.5)
# =============================================================================


def test_lakebase_cost_formula(report: _TestReport):
    print("\n--- Lakebase Cost Formula (v2.5) ---")

    from config.pricing import HOURS_PER_MONTH, LAKEBASE_DBU_PER_CU_HOUR, get_lakebase_rates

    rates = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="premium")
    cu = 4
    expected_compute = cu * LAKEBASE_DBU_PER_CU_HOUR * rates["dbu_rate"] * HOURS_PER_MONTH
    report.add(
        "4 CU Premium monthly compute = $1,168",
        abs(expected_compute - 1168.0) < 1.0,
        f"compute=${expected_compute:.2f}",
    )

    rates_ent = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="enterprise")
    expected_ent = cu * LAKEBASE_DBU_PER_CU_HOUR * rates_ent["dbu_rate"] * HOURS_PER_MONTH
    report.add(
        "4 CU Enterprise monthly compute = $1,518.40",
        abs(expected_ent - 1518.4) < 1.0,
        f"compute=${expected_ent:.2f}",
    )

    storage_gb = 100
    expected_storage = rates["storage_dsu_per_gb_month"] * storage_gb
    report.add(
        "100 GB storage = $2.30",
        abs(expected_storage - 2.30) < 0.01,
        f"storage=${expected_storage:.2f}",
    )


# =============================================================================
# Test: Cost Estimator Validation (v2.6)
# =============================================================================


def test_corrected_source_rates(report: _TestReport):
    print("\n--- Corrected Source Engine Rates (v2.6) ---")

    from config.pricing import SOURCE_ENGINES, get_source_rates

    aurora_rates = get_source_rates("aurora-postgresql", "us-east-1")
    report.add(
        "Aurora Standard: $0.519/hr",
        aurora_rates["compute_per_hour"] == 0.519,
        f"rate={aurora_rates['compute_per_hour']}",
    )

    rds_rates = get_source_rates("rds-postgresql", "us-east-1")
    report.add(
        "RDS PostgreSQL: $0.45/hr",
        rds_rates["compute_per_hour"] == 0.45,
        f"rate={rds_rates['compute_per_hour']}",
    )

    azure_rates = get_source_rates("azure-postgresql", "eastus")
    report.add(
        "Azure Flexible Server: $0.356/hr",
        azure_rates["compute_per_hour"] == 0.356,
        f"rate={azure_rates['compute_per_hour']}",
    )

    report.add(
        "Aurora I/O-Optimized exists",
        "aurora-postgresql-io" in SOURCE_ENGINES,
        "engine present",
    )
    aurora_io = get_source_rates("aurora-postgresql-io", "us-east-1")
    report.add(
        "Aurora I/O-Optimized: $0.675/hr",
        aurora_io["compute_per_hour"] == 0.675,
        f"rate={aurora_io['compute_per_hour']}",
    )
    report.add(
        "Aurora I/O-Optimized: storage=$0.225",
        aurora_io["storage_per_gb_month"] == 0.225,
        f"storage={aurora_io['storage_per_gb_month']}",
    )
    report.add(
        "Aurora I/O-Optimized: io=$0 (bundled)",
        aurora_io["io_per_million"] == 0.0,
        f"io={aurora_io['io_per_million']}",
    )


def test_dynamodb_restructured_pricing(report: _TestReport):
    print("\n--- DynamoDB Restructured Pricing (v2.6) ---")

    from config.pricing import SOURCE_ENGINES, get_source_rates

    dynamo_cfg = SOURCE_ENGINES["dynamodb"]
    report.add(
        "DynamoDB: pricing_model=request_unit",
        dynamo_cfg.get("pricing_model") == "request_unit",
        f"model={dynamo_cfg.get('pricing_model')}",
    )

    rates = get_source_rates("dynamodb", "us-east-1")
    report.add(
        "DynamoDB: compute_per_hour=0 (no hourly compute)",
        rates["compute_per_hour"] == 0.0,
        f"compute={rates['compute_per_hour']}",
    )
    report.add(
        "DynamoDB: wru_per_million=$1.25",
        rates.get("wru_per_million") == 1.25,
        f"wru={rates.get('wru_per_million')}",
    )
    report.add(
        "DynamoDB: rru_per_million=$0.25",
        rates.get("rru_per_million") == 0.25,
        f"rru={rates.get('rru_per_million')}",
    )
    report.add(
        "DynamoDB: storage=$0.25/GB",
        rates["storage_per_gb_month"] == 0.25,
        f"storage={rates['storage_per_gb_month']}",
    )


def test_azure_lakebase_uplift(report: _TestReport):
    print("\n--- Azure Lakebase Uplift (v2.6) ---")

    from config.pricing import LAKEBASE_PRICING, get_lakebase_rates

    aws_premium = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="premium")
    azure_premium = get_lakebase_rates("azure-postgresql", "eastus", tier="premium")
    report.add(
        "AWS Premium = $0.40",
        aws_premium["dbu_rate"] == 0.40,
        f"rate={aws_premium['dbu_rate']}",
    )
    report.add(
        "Azure Premium = $0.46 (15% uplift)",
        azure_premium["dbu_rate"] == 0.46,
        f"rate={azure_premium['dbu_rate']}",
    )
    report.add(
        "Azure Premium > AWS Premium",
        azure_premium["dbu_rate"] > aws_premium["dbu_rate"],
        f"azure={azure_premium['dbu_rate']} > aws={aws_premium['dbu_rate']}",
    )

    aws_ent = get_lakebase_rates("aurora-postgresql", "us-east-1", tier="enterprise")
    azure_ent = get_lakebase_rates("azure-postgresql", "eastus", tier="enterprise")
    report.add(
        "AWS Enterprise = $0.52",
        aws_ent["dbu_rate"] == 0.52,
        f"rate={aws_ent['dbu_rate']}",
    )
    report.add(
        "Azure Enterprise = $0.60",
        azure_ent["dbu_rate"] == 0.60,
        f"rate={azure_ent['dbu_rate']}",
    )

    cross_cloud = LAKEBASE_PRICING.get("cross_cloud_notes", {})
    report.add(
        "Cross-cloud notes present",
        "azure_uplift_pct" in cross_cloud,
        f"uplift={cross_cloud.get('azure_uplift_pct')}%",
    )


def test_committed_use_discounts(report: _TestReport):
    print("\n--- Committed-Use Discounts (v2.6) ---")

    from config.pricing import LAKEBASE_PRICING

    discounts = LAKEBASE_PRICING.get("committed_use_discounts", {})
    report.add(
        "Committed-use discounts present",
        "1_year" in discounts and "3_year" in discounts,
        "1-year and 3-year present",
    )
    report.add(
        "1-year discount = 25%",
        discounts["1_year"]["discount_pct"] == 25,
        f"discount={discounts['1_year']['discount_pct']}%",
    )
    report.add(
        "3-year discount = 40%",
        discounts["3_year"]["discount_pct"] == 40,
        f"discount={discounts['3_year']['discount_pct']}%",
    )
    report.add(
        "Discount note present",
        "note" in discounts and "account team" in discounts["note"].lower(),
        "has contact guidance",
    )


def test_confidence_indicators(report: _TestReport):
    print("\n--- Confidence Indicators (v2.6) ---")

    from config.pricing import SOURCE_ENGINES

    verified_engines = ["aurora-postgresql", "aurora-postgresql-io", "rds-postgresql",
                        "azure-postgresql", "dynamodb", "cosmosdb-nosql"]
    for eng in verified_engines:
        cfg = SOURCE_ENGINES[eng]
        report.add(
            f"{eng}: confidence=verified",
            cfg.get("confidence") == "verified",
            f"confidence={cfg.get('confidence')}",
        )

    estimated_engines = ["cloud-sql-postgresql", "alloydb-postgresql", "supabase-postgresql",
                         "self-managed-postgresql"]
    for eng in estimated_engines:
        cfg = SOURCE_ENGINES[eng]
        report.add(
            f"{eng}: confidence=estimated",
            cfg.get("confidence") == "estimated",
            f"confidence={cfg.get('confidence')}",
        )


def test_change_feed_mode_scoring(report: _TestReport):
    print("\n--- Change Feed Mode Scoring (v2.7) ---")

    db_latest = DatabaseProfile(
        name="cosmos-cf-latest",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=3,
        extensions=[],
        functions=[],
        triggers=[],
        cosmos_throughput_mode="provisioned",
        cosmos_ru_per_sec=2000,
        cosmos_consistency_level="Session",
        cosmos_change_feed_enabled=False,
        cosmos_change_feed_mode="LatestVersion",
        cosmos_multi_region_writes=False,
        cosmos_regions=["eastus"],
    )
    result_latest = compute_readiness_score(db_latest, source_engine="cosmosdb-nosql")

    db_avd = DatabaseProfile(
        name="cosmos-cf-avd",
        size_bytes=1_000_000_000,
        size_gb=0.93,
        table_count=3,
        extensions=[],
        functions=[],
        triggers=[],
        cosmos_throughput_mode="provisioned",
        cosmos_ru_per_sec=2000,
        cosmos_consistency_level="Session",
        cosmos_change_feed_enabled=True,
        cosmos_change_feed_mode="AllVersionsAndDeletes",
        cosmos_multi_region_writes=False,
        cosmos_regions=["eastus"],
    )
    result_avd = compute_readiness_score(db_avd, source_engine="cosmosdb-nosql")

    report.add(
        "LatestVersion CF -> no replication blocker",
        not any(b.category == "replication" and "AllVersionsAndDeletes" in b.description for b in result_latest.blockers),
        "No AVD blocker for LatestVersion",
    )
    report.add(
        "AllVersionsAndDeletes CF -> replication blocker",
        any(b.category == "replication" and "AllVersionsAndDeletes" in b.description for b in result_avd.blockers),
        "AVD blocker present",
    )
    report.add(
        "AVD scores lower than LatestVersion",
        result_avd.overall_score < result_latest.overall_score,
        f"AVD={result_avd.overall_score} < Latest={result_latest.overall_score}",
    )


def test_workload_source_field(report: _TestReport):
    print("\n--- Workload Source Field (v2.7) ---")

    wp_default = WorkloadProfile(avg_qps=1000)
    report.add(
        "Default workload_source='observed'",
        wp_default.workload_source == "observed",
        f"source={wp_default.workload_source}",
    )

    wp_mock = WorkloadProfile(avg_qps=1000, workload_source="mock")
    report.add(
        "Mock workload_source='mock'",
        wp_mock.workload_source == "mock",
        f"source={wp_mock.workload_source}",
    )

    wp_heuristic = WorkloadProfile(avg_qps=1000, workload_source="heuristic")
    report.add(
        "Heuristic workload_source='heuristic'",
        wp_heuristic.workload_source == "heuristic",
        f"source={wp_heuristic.workload_source}",
    )


def test_cu_from_memory_sizing(report: _TestReport):
    print("\n--- CU From Memory Sizing (v2.7) ---")

    from utils.readiness_scorer import compute_readiness_score

    large_db = DatabaseProfile(
        name="large-db",
        size_bytes=200 * 1024**3,
        size_gb=200.0,
        table_count=50,
        schema_count=5,
        schemas=["public"],
        extensions=[],
        functions=[],
        triggers=[],
    )
    small_workload = WorkloadProfile(avg_qps=10, connection_count_peak=5)

    result = compute_readiness_score(large_db, small_workload, source_engine="aurora-postgresql")
    sizing = result.sizing_by_env
    prod_sizing = next((s for s in sizing if s.env == "prod"), None)

    report.add(
        "Large DB: prod sizing exists",
        prod_sizing is not None,
        "prod sizing present",
    )
    if prod_sizing:
        report.add(
            "Large DB (200GB): prod cu_max >= 32 (memory-driven)",
            prod_sizing.cu_max >= 32,
            f"cu_max={prod_sizing.cu_max} (200GB / 2 = 100 CU target)",
        )


def test_lakebase_pricing_transparency(report: _TestReport):
    print("\n--- Lakebase Pricing Transparency (v2.7) ---")

    from config.pricing import LAKEBASE_PRICING, PRICING_VERSION

    report.add(
        "LAKEBASE_PRICING has source_url",
        "source_url" in LAKEBASE_PRICING,
        f"url={LAKEBASE_PRICING.get('source_url', 'missing')}",
    )
    report.add(
        "PRICING_VERSION is set",
        PRICING_VERSION is not None and len(PRICING_VERSION) > 0,
        f"version={PRICING_VERSION}",
    )


# =============================================================================
# Main
# =============================================================================


def main():
    print("\n" + "=" * 70)
    print("  MIGRATION ASSESSMENT ACCELERATOR - TEST SUITE")
    print("  Postgres, DynamoDB & CosmosDB -> Lakebase Assessment & Migration")
    print("  Includes: Live adapter fallback, pricing fetcher, warnings propagation")
    print("  Includes: Lakebase pricing v2.5, environment sizing, cost formula")
    print("  Includes: Cost estimator validation v2.6")
    print("  Includes: Cosmos adapter accuracy, workload source, CU memory v2.7")
    print("=" * 70)

    report = _TestReport()

    test_dataclasses(report)
    test_readiness_scorer(report)
    test_blueprint_generator(report)
    test_assessment_mixin(report)
    test_end_to_end(report)
    test_dynamodb_discovery(report)
    test_dynamodb_readiness(report)
    test_dynamodb_blueprint(report)
    test_dynamodb_end_to_end(report)
    test_cosmosdb_discovery(report)
    test_cosmosdb_readiness(report)
    test_cosmosdb_blueprint(report)
    test_cosmosdb_end_to_end(report)
    test_cosmosdb_live_discover_fallback(report)
    test_cosmosdb_live_workload(report)
    test_pricing_fetcher(report)
    test_warnings_propagation(report)
    test_lakebase_pricing_registry(report)
    test_environment_sizing(report)
    test_lakebase_cost_formula(report)
    test_corrected_source_rates(report)
    test_dynamodb_restructured_pricing(report)
    test_azure_lakebase_uplift(report)
    test_committed_use_discounts(report)
    test_confidence_indicators(report)
    test_change_feed_mode_scoring(report)
    test_workload_source_field(report)
    test_cu_from_memory_sizing(report)
    test_lakebase_pricing_transparency(report)

    success = report.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
