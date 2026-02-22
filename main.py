"""
LakebaseOps Platform — Main Orchestrator

Demonstrates the full multi-agent system executing all 16 weeks of
automation tasks from the PRD in a single simulation cycle.

Phases:
  1. Foundation (Weeks 1-3): Ops catalog, metric collection, alerts
  2. Index & Vacuum (Weeks 4-6): Index analysis, vacuum scheduling
  3. Sync & Branches (Weeks 7-9): Sync validation, branch lifecycle
  4. Cold Archival (Weeks 10-12): Data archival pipeline
  5. AI Operations (Weeks 13-16): Query optimization, self-healing, NL DBA

Usage:
  python main.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from framework.agent_framework import AgentFramework, EventType
from agents.provisioning_agent import ProvisioningAgent
from agents.performance_agent import PerformanceAgent
from agents.health_agent import HealthAgent
from utils.lakebase_client import LakebaseClient
from utils.delta_writer import DeltaWriter
from utils.alerting import AlertManager, AlertChannel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("lakebase_ops.main")


async def run_full_platform_simulation():
    """
    Execute the complete LakebaseOps platform simulation.
    Covers all 16 weeks of PRD implementation in a single run.
    """

    print("\n" + "=" * 80)
    print("  LAKEBASE AUTONOMOUS DATABASE OPERATIONS PLATFORM (LakebaseOps)")
    print("  Simulating 16-Week Implementation — All 5 Phases")
    print("=" * 80 + "\n")

    # -----------------------------------------------------------------------
    # Initialize shared infrastructure
    # -----------------------------------------------------------------------
    logger.info("Initializing shared infrastructure...")

    lakebase_client = LakebaseClient(
        workspace_host="fe-vm-hls-amer.cloud.databricks.com",
        mock_mode=True,
    )
    delta_writer = DeltaWriter(mock_mode=True)
    alert_manager = AlertManager(mock_mode=True)

    # Configure alert channels
    alert_manager.configure_channel(AlertChannel.SLACK, {"webhook_url": "https://hooks.slack.com/..."})
    alert_manager.configure_channel(AlertChannel.PAGERDUTY, {"routing_key": "..."})

    # -----------------------------------------------------------------------
    # Initialize the AgentFramework
    # -----------------------------------------------------------------------
    framework = AgentFramework(
        workspace_host="fe-vm-hls-amer.cloud.databricks.com",
        mock_mode=True,
    )

    # -----------------------------------------------------------------------
    # Instantiate and register agents
    # -----------------------------------------------------------------------
    provisioning_agent = ProvisioningAgent(lakebase_client, delta_writer, alert_manager)
    performance_agent = PerformanceAgent(lakebase_client, delta_writer, alert_manager)
    health_agent = HealthAgent(lakebase_client, delta_writer, alert_manager)

    framework.register_agent(provisioning_agent)
    framework.register_agent(performance_agent)
    framework.register_agent(health_agent)

    # -----------------------------------------------------------------------
    # Set up inter-agent event subscriptions
    # -----------------------------------------------------------------------

    # When provisioning completes, Health Agent starts monitoring
    def on_provisioning_complete(event):
        logger.info(f"[EVENT] Provisioning complete for {event.data.get('project_id')} "
                     f"-> Health Agent will begin monitoring branches: {event.data.get('branches')}")

    # When thresholds are breached, Performance Agent may need to act
    def on_threshold_breached(event):
        metric = event.data.get("metric", "")
        if "dead_tuple" in metric:
            logger.info(f"[EVENT] Dead tuple threshold breached -> Performance Agent will schedule vacuum")

    # When vacuum completes, Health Agent updates its metrics
    def on_vacuum_completed(event):
        logger.info(f"[EVENT] Vacuum completed on {event.data.get('tables_vacuumed', 0)} tables "
                     f"-> Health Agent will refresh metrics")

    # When index recommendations are generated, log for review
    def on_index_recommendation(event):
        logger.info(f"[EVENT] {event.data.get('total_issues', 0)} index issues detected "
                     f"-> Added to review queue")

    framework.subscribe(EventType.PROVISIONING_COMPLETE, on_provisioning_complete)
    framework.subscribe(EventType.THRESHOLD_BREACHED, on_threshold_breached)
    framework.subscribe(EventType.VACUUM_COMPLETED, on_vacuum_completed)
    framework.subscribe(EventType.INDEX_RECOMMENDATION, on_index_recommendation)

    # -----------------------------------------------------------------------
    # Execute full automation cycle
    # -----------------------------------------------------------------------

    context = {
        "project_id": "supply-chain-prod",
        "domain": "supply-chain",
        "catalog": "ops_catalog",
        "is_new_project": True,
        "branches": ["production", "staging"],
        "pending_prs": [
            {"number": 42, "action": "opened"},
        ],
        "pending_migrations": [
            {
                "pr_number": 42,
                "files": [
                    "CREATE TABLE IF NOT EXISTS audit_log (id SERIAL PRIMARY KEY, action TEXT, created_at TIMESTAMPTZ DEFAULT NOW());",
                    "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);",
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
                ],
            },
        ],
        "sync_table_pairs": [
            {"source": "orders", "target": "ops_catalog.lakebase_ops.orders_delta"},
            {"source": "events", "target": "ops_catalog.lakebase_ops.events_delta"},
        ],
    }

    results = await framework.run_full_cycle(context)

    # -----------------------------------------------------------------------
    # Print comprehensive results
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("  AUTOMATION CYCLE RESULTS")
    print("=" * 80)

    print(f"\n  Total Duration: {results['duration_seconds']:.2f}s")
    print(f"  Total Events Dispatched: {results['events']}")

    print("\n  Agent Summaries:")
    for agent_name, summary in results["agent_summaries"].items():
        print(f"    {agent_name}:")
        print(f"      Tasks: {summary['total_tasks']} ({summary['successful']} success, {summary['failed']} failed)")
        print(f"      Success Rate: {summary['success_rate']}")

    # Alert summary
    alert_summary = alert_manager.get_alert_summary()
    print(f"\n  Alert Summary:")
    print(f"    Total Alerts: {alert_summary['total_alerts']}")
    for severity, count in alert_summary["by_severity"].items():
        if count > 0:
            print(f"    {severity.upper()}: {count}")
    print(f"    Auto-Remediated: {alert_summary['auto_remediated']}")

    # Delta write summary
    write_log = delta_writer.get_write_log()
    print(f"\n  Delta Lake Writes:")
    print(f"    Total Write Operations: {len(write_log)}")
    total_records = sum(w.get("records", 0) for w in write_log)
    print(f"    Total Records Written: {total_records}")
    tables_written = set(w.get("table", "") for w in write_log)
    print(f"    Tables Written To: {len(tables_written)}")
    for table in sorted(tables_written):
        table_records = sum(w.get("records", 0) for w in write_log if w.get("table") == table)
        print(f"      - {table}: {table_records} records")

    # -----------------------------------------------------------------------
    # Demonstrate individual agent capabilities
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("  INDIVIDUAL AGENT DEMONSTRATIONS")
    print("=" * 80)

    # Demo: Natural Language DBA
    print("\n  --- UC-14: Natural Language DBA ---")
    nl_result = health_agent.natural_language_dba(
        "Why is my orders query slow?",
        project_id="supply-chain-prod",
        branch_id="production",
    )
    print(f"    Q: Why is my orders query slow?")
    print(f"    A: {nl_result.get('analysis', '')}")
    print(f"    Fix: {nl_result.get('recommendation', '')}")

    # Demo: AI Query Optimization
    print("\n  --- UC-12: AI Query Optimization ---")
    ai_result = performance_agent.analyze_slow_queries_with_ai(
        "supply-chain-prod", "production"
    )
    print(f"    Slow queries analyzed: {ai_result['slow_queries_analyzed']}")
    if ai_result.get("analyses"):
        first = ai_result["analyses"][0]
        print(f"    Top query: {first['original_query'][:60]}...")
        print(f"    Bottleneck: {first['ai_analysis']['bottleneck']}")
        print(f"    Fix: {first['ai_analysis']['index_suggestion']}")

    # Demo: Capacity Forecast
    print("\n  --- UC-15: Capacity Planning ---")
    forecast = performance_agent.forecast_capacity_needs("supply-chain-prod")
    storage = forecast["storage_forecast"]
    print(f"    Current storage: {storage['current_gb']} GB")
    print(f"    Projected (30d): {storage['projected_gb']} GB")
    print(f"    Growth rate: {storage['growth_rate_gb_per_day']} GB/day")

    # Demo: Self-Healing
    print("\n  --- UC-13: Self-Healing ---")
    diagnosis = health_agent.diagnose_root_cause({
        "metric": "dead_tuple_ratio",
        "value": 0.35,
    })
    print(f"    Anomaly: {diagnosis['anomaly']}")
    print(f"    Auto-fixable: {diagnosis['auto_fixable']}")
    print(f"    Causes: {diagnosis['probable_causes'][:2]}")

    # Demo: Cost Attribution
    print("\n  --- UC-11: Cost Attribution ---")
    costs = health_agent.track_cost_attribution("supply-chain-prod")
    print(f"    Total DBUs (7d): {costs['total_dbus']}")
    for branch, data in costs["cost_breakdown"].items():
        print(f"    {branch}: {data['dbus']} DBUs ({data['pct']}%)")

    # -----------------------------------------------------------------------
    # Generate CI/CD artifacts
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("  CI/CD ARTIFACTS GENERATED")
    print("=" * 80)

    cicd = provisioning_agent.setup_cicd_pipeline("supply-chain-prod")
    print(f"\n  GitHub Actions workflows generated for project: supply-chain-prod")
    print(f"  Secrets required: {cicd['secrets_required']}")
    print(f"  Variables required: {cicd['variables_required']}")

    # -----------------------------------------------------------------------
    # Generate DBSQL Alert Definitions
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("  DBSQL ALERT DEFINITIONS")
    print("=" * 80)

    dbsql_alerts = alert_manager.create_dbsql_alert_definitions()
    for alert_def in dbsql_alerts:
        print(f"\n  Alert: {alert_def['name']}")
        print(f"  Severity: {alert_def['severity']}")
        print(f"  Condition: {alert_def['condition']}")

    # -----------------------------------------------------------------------
    # Print tool inventory
    # -----------------------------------------------------------------------

    print("\n" + "=" * 80)
    print("  TOOL INVENTORY")
    print("=" * 80)

    for agent_name, agent in framework.agents.items():
        print(f"\n  {agent_name} ({len(agent.tools)} tools):")
        for tool_name, tool in sorted(agent.tools.items()):
            schedule = f" [Schedule: {tool.schedule}]" if tool.schedule else ""
            risk = f" [Risk: {tool.risk_level}]" if tool.risk_level != "low" else ""
            approval = " [REQUIRES APPROVAL]" if tool.requires_approval else ""
            print(f"    - {tool_name}{schedule}{risk}{approval}")

    print("\n" + "=" * 80)
    print("  SIMULATION COMPLETE")
    print(f"  All 16 weeks of PRD implementation demonstrated successfully.")
    print(f"  3 Agents | {sum(len(a.tools) for a in framework.agents.values())} Tools | "
          f"{results['events']} Events | {total_records} Records Written")
    print("=" * 80 + "\n")

    # Cleanup
    lakebase_client.close_all()

    return results


if __name__ == "__main__":
    asyncio.run(run_full_platform_simulation())
