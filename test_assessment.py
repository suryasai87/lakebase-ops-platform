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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.migration_profiles import (
    AssessmentResult,
    BlockerSeverity,
    DatabaseProfile,
    ExtensionInfo,
    FunctionInfo,
    LakebaseTier,
    MigrationBlueprint,
    MigrationProfile,
    ReadinessCategory,
    SourceEngine,
    TableProfile,
    TriggerInfo,
    WorkloadProfile,
)
from utils.readiness_scorer import compute_readiness_score, LAKEBASE_SUPPORTED_EXTENSIONS
from utils.blueprint_generator import generate_blueprint, render_blueprint_markdown


# =============================================================================
# Test Helpers
# =============================================================================

class TestReport:
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


# =============================================================================
# Test: Migration Profile Dataclasses
# =============================================================================

def test_dataclasses(report: TestReport):
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

def test_readiness_scorer(report: TestReport):
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
        name="high_qps_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="repl_db", size_bytes=5_000_000_000, size_gb=4.65,
        table_count=15, extensions=[], functions=[], triggers=[],
        has_logical_replication=True, replication_slots=["sub_analytics"],
    )
    result5 = compute_readiness_score(repl_db)
    report.add(
        "Logical replication -> HIGH blocker",
        any(b.severity == BlockerSeverity.HIGH and b.category == "replication" for b in result5.blockers),
        f"{len(result5.blockers)} blockers",
    )

    # Test 6: Heavy PL/pgSQL -> complexity blocker
    plpgsql_db = DatabaseProfile(
        name="plpgsql_db", size_bytes=5_000_000_000, size_gb=4.65,
        table_count=20, extensions=[], triggers=[],
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
        name="evt_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="lo_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="agg_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="excl_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="rls_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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
        name="coll_db", size_bytes=1_000_000_000, size_gb=0.93,
        table_count=5, extensions=[], functions=[], triggers=[],
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

def test_blueprint_generator(report: TestReport):
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
    report.add("Has post-checks", len(blueprint.post_migration_checks) > 0, f"{len(blueprint.post_migration_checks)} checks")
    report.add("Has rollback plan", len(blueprint.rollback_plan) > 0, "Rollback plan present")

    # Test markdown rendering
    md = render_blueprint_markdown(blueprint, db, assessment)
    report.add("Markdown rendered", len(md) > 500, f"{len(md)} chars")
    report.add("Markdown has title", "# Migration Blueprint" in md, "Title found")
    report.add("Markdown has phases", "## Phase 1" in md and "## Phase 4" in md, "All phases present")
    report.add("Markdown has commands", "pg_dump" in md, "pg_dump command found")
    report.add("Markdown has score", str(assessment.overall_score) in md, "Score in report")
    report.add("Markdown has disable-triggers warning", "disable-triggers" in md.lower() or "disable_triggers" in md.lower(), "Trigger warning present")
    report.add("Markdown has plain-text recommendation", "plain-text" in md.lower() or "plain text" in md.lower(), "Plain-text dump note present")


# =============================================================================
# Test: AssessmentMixin (4 Tools via ProvisioningAgent)
# =============================================================================

def test_assessment_mixin(report: TestReport):
    print("\n--- AssessmentMixin (4 Tools) ---")

    from utils.lakebase_client import LakebaseClient
    from utils.delta_writer import DeltaWriter
    from utils.alerting import AlertManager
    from agents import ProvisioningAgent

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
    report.add("Total tools = 21", len(tool_names) == 21, f"{len(tool_names)} tools")

    # Tool 1: connect_and_discover
    discovery = agent.connect_and_discover(
        endpoint="aurora.cluster-xxx.us-east-1.rds.amazonaws.com",
        database="app_production",
        source_engine="aurora-postgresql",
        mock=True,
    )
    report.add("connect_and_discover returns profile_id", "profile_id" in discovery, discovery.get("profile_id", ""))
    report.add("connect_and_discover returns tables", discovery.get("table_count", 0) > 0, f"{discovery.get('table_count')} tables")
    report.add("connect_and_discover returns extensions", discovery.get("extension_count", 0) > 0, f"{discovery.get('extension_count')} extensions")
    report.add("connect_and_discover returns size", discovery.get("size_gb", 0) > 0, f"{discovery.get('size_gb')} GB")

    # Tool 2: profile_workload
    workload = agent.profile_workload(profile_data=discovery, mock=True)
    report.add("profile_workload returns QPS", workload.get("avg_qps", 0) > 0, f"QPS={workload.get('avg_qps')}")
    report.add("profile_workload returns TPS", workload.get("avg_tps", 0) > 0, f"TPS={workload.get('avg_tps')}")
    report.add("profile_workload returns connections", workload.get("connection_count_peak", 0) > 0, f"Peak={workload.get('connection_count_peak')}")

    # Tool 3: assess_readiness
    assessment = agent.assess_readiness(profile_data=discovery, workload_data=workload)
    report.add("assess_readiness returns score", "overall_score" in assessment, f"Score={assessment.get('overall_score')}")
    report.add("assess_readiness returns category", "category" in assessment, f"Category={assessment.get('category')}")
    report.add("assess_readiness returns tier", "recommended_tier" in assessment, f"Tier={assessment.get('recommended_tier')}")
    report.add("assess_readiness returns dimensions", "dimensions" in assessment, f"{len(assessment.get('dimensions', {}))} dimensions")
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
    report.add("blueprint returns phases", blueprint.get("phase_count", 0) == 4, f"{blueprint.get('phase_count')} phases")
    report.add("blueprint returns days", blueprint.get("total_estimated_days", 0) > 0, f"{blueprint.get('total_estimated_days')} days")
    report.add("blueprint returns markdown", len(blueprint.get("report_markdown", "")) > 500, f"{len(blueprint.get('report_markdown', ''))} chars")


# =============================================================================
# Test: End-to-End Pipeline
# =============================================================================

def test_end_to_end(report: TestReport):
    print("\n--- End-to-End Pipeline ---")

    from utils.lakebase_client import LakebaseClient
    from utils.delta_writer import DeltaWriter
    from utils.alerting import AlertManager
    from agents import ProvisioningAgent

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
    report.add("E2E: Assessment scored", assessment.get("overall_score", 0) > 0, f"Score={assessment.get('overall_score')}")
    report.add("E2E: Blueprint generated", blueprint.get("phase_count", 0) == 4, "Blueprint OK")

    # Verify the markdown report contains key sections
    md = blueprint.get("report_markdown", "")
    report.add("E2E: Report has blockers section", "Blocker" in md or "blocker" in md.lower() or "Risk" in md, "Blockers section found")
    report.add("E2E: Report has pg_dump commands", "pg_dump" in md, "pg_dump in report")
    report.add("E2E: Report has Lakebase sizing", "CU" in md, "CU sizing in report")


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "=" * 70)
    print("  MIGRATION ASSESSMENT ACCELERATOR - TEST SUITE")
    print("  Postgres -> Lakebase Assessment & Migration")
    print("=" * 70)

    report = TestReport()

    test_dataclasses(report)
    test_readiness_scorer(report)
    test_blueprint_generator(report)
    test_assessment_mixin(report)
    test_end_to_end(report)

    success = report.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
