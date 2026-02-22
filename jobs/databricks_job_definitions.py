"""
Databricks Job Definitions for LakebaseOps Scheduled Tasks.

These replace pg_cron (not available in Lakebase) with Databricks Jobs.
Deploy via Databricks CLI or Asset Bundles.

PRD Schedule Reference:
- Metric Collector: Every 5 minutes
- Index Analyzer: Every hour
- Vacuum Scheduler: Daily 2 AM
- Sync Validator: Every 15 minutes
- Branch Manager: Every 6 hours
- Cold Archiver: Weekly Sunday 3 AM
- Connection Monitor: Every minute
- Cost Tracker: Daily 6 AM
"""

JOB_DEFINITIONS = {
    "metric_collector": {
        "name": "LakebaseOps - Metric Collector",
        "description": "Persists pg_stat_statements and health metrics to Delta (FR-01, FR-04)",
        "schedule": {"quartz_cron_expression": "0 */5 * * * ?", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "collect_metrics",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/metric_collector_notebook",
                "base_parameters": {
                    "project_id": "{{job.parameters.project_id}}",
                    "branches": "production,staging",
                },
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "job_clusters": [{
            "job_cluster_key": "lakebase_ops_cluster",
            "new_cluster": {
                "spark_version": "15.4.x-scala2.12",
                "num_workers": 0,
                "node_type_id": "i3.xlarge",
                "runtime_engine": "SERVERLESS",
            },
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 300,
        "tags": {"team": "lakebase-ops", "component": "metric-collector"},
    },

    "index_analyzer": {
        "name": "LakebaseOps - Index Analyzer",
        "description": "Analyzes index health and generates recommendations (FR-02)",
        "schedule": {"quartz_cron_expression": "0 0 * * * ?", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "analyze_indexes",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/index_analyzer_notebook",
                "base_parameters": {
                    "project_id": "{{job.parameters.project_id}}",
                    "branch_id": "production",
                },
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 600,
        "tags": {"team": "lakebase-ops", "component": "index-analyzer"},
    },

    "vacuum_scheduler": {
        "name": "LakebaseOps - Vacuum Scheduler",
        "description": "Scheduled VACUUM ANALYZE replacing pg_cron (FR-03)",
        "schedule": {"quartz_cron_expression": "0 0 2 * * ?", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "vacuum_tables",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/vacuum_scheduler_notebook",
                "base_parameters": {
                    "project_id": "{{job.parameters.project_id}}",
                    "branch_id": "production",
                },
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 3600,
        "tags": {"team": "lakebase-ops", "component": "vacuum-scheduler"},
    },

    "sync_validator": {
        "name": "LakebaseOps - Sync Validator",
        "description": "Validates OLTP-to-OLAP sync completeness and freshness (FR-05)",
        "schedule": {"quartz_cron_expression": "0 */15 * * * ?", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "validate_sync",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/sync_validator_notebook",
                "base_parameters": {
                    "project_id": "{{job.parameters.project_id}}",
                    "branch_id": "production",
                },
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 300,
        "tags": {"team": "lakebase-ops", "component": "sync-validator"},
    },

    "branch_manager": {
        "name": "LakebaseOps - Branch Manager",
        "description": "Enforces TTL policies and monitors branch counts (FR-06)",
        "schedule": {"quartz_cron_expression": "0 0 */6 * * ?", "timezone_id": "UTC"},
        "tasks": [
            {
                "task_key": "enforce_ttl",
                "notebook_task": {
                    "notebook_path": "/Repos/lakebase-ops/jobs/branch_manager_notebook",
                    "base_parameters": {"action": "enforce_ttl"},
                },
                "job_cluster_key": "lakebase_ops_cluster",
            },
            {
                "task_key": "reset_staging",
                "notebook_task": {
                    "notebook_path": "/Repos/lakebase-ops/jobs/branch_manager_notebook",
                    "base_parameters": {"action": "reset_staging"},
                },
                "job_cluster_key": "lakebase_ops_cluster",
                "depends_on": [{"task_key": "enforce_ttl"}],
            },
        ],
        "max_concurrent_runs": 1,
        "timeout_seconds": 600,
        "tags": {"team": "lakebase-ops", "component": "branch-manager"},
    },

    "cold_archiver": {
        "name": "LakebaseOps - Cold Data Archiver",
        "description": "Archives cold data from Lakebase to Delta Lake (FR-07)",
        "schedule": {"quartz_cron_expression": "0 0 3 ? * SUN", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "archive_cold_data",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/cold_archiver_notebook",
                "base_parameters": {
                    "project_id": "{{job.parameters.project_id}}",
                    "branch_id": "production",
                    "cold_threshold_days": "90",
                },
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 7200,
        "tags": {"team": "lakebase-ops", "component": "cold-archiver"},
    },

    "cost_tracker": {
        "name": "LakebaseOps - Cost Tracker",
        "description": "Tracks Lakebase costs from system.billing.usage (UC-11)",
        "schedule": {"quartz_cron_expression": "0 0 6 * * ?", "timezone_id": "UTC"},
        "tasks": [{
            "task_key": "track_costs",
            "notebook_task": {
                "notebook_path": "/Repos/lakebase-ops/jobs/cost_tracker_notebook",
            },
            "job_cluster_key": "lakebase_ops_cluster",
        }],
        "max_concurrent_runs": 1,
        "timeout_seconds": 600,
        "tags": {"team": "lakebase-ops", "component": "cost-tracker"},
    },
}


def generate_databricks_yml():
    """Generate databricks.yml for Asset Bundle deployment."""
    return """
bundle:
  name: lakebase-ops-platform

workspace:
  host: https://fe-vm-hls-amer.cloud.databricks.com

resources:
  jobs:
    metric_collector:
      name: "LakebaseOps - Metric Collector"
      schedule:
        quartz_cron_expression: "0 */5 * * * ?"
        timezone_id: UTC
      tasks:
        - task_key: collect_metrics
          notebook_task:
            notebook_path: ./jobs/metric_collector_notebook.py
          new_cluster:
            spark_version: 15.4.x-scala2.12
            num_workers: 0
      tags:
        team: lakebase-ops

    index_analyzer:
      name: "LakebaseOps - Index Analyzer"
      schedule:
        quartz_cron_expression: "0 0 * * * ?"
        timezone_id: UTC
      tasks:
        - task_key: analyze_indexes
          notebook_task:
            notebook_path: ./jobs/index_analyzer_notebook.py

    vacuum_scheduler:
      name: "LakebaseOps - Vacuum Scheduler"
      schedule:
        quartz_cron_expression: "0 0 2 * * ?"
        timezone_id: UTC
      tasks:
        - task_key: vacuum_tables
          notebook_task:
            notebook_path: ./jobs/vacuum_scheduler_notebook.py

    sync_validator:
      name: "LakebaseOps - Sync Validator"
      schedule:
        quartz_cron_expression: "0 */15 * * * ?"
        timezone_id: UTC
      tasks:
        - task_key: validate_sync
          notebook_task:
            notebook_path: ./jobs/sync_validator_notebook.py

    branch_manager:
      name: "LakebaseOps - Branch Manager"
      schedule:
        quartz_cron_expression: "0 0 */6 * * ?"
        timezone_id: UTC
      tasks:
        - task_key: enforce_ttl
          notebook_task:
            notebook_path: ./jobs/branch_manager_notebook.py
        - task_key: reset_staging
          notebook_task:
            notebook_path: ./jobs/branch_manager_notebook.py
          depends_on:
            - task_key: enforce_ttl

    cold_archiver:
      name: "LakebaseOps - Cold Data Archiver"
      schedule:
        quartz_cron_expression: "0 0 3 ? * SUN"
        timezone_id: UTC
      tasks:
        - task_key: archive_cold_data
          notebook_task:
            notebook_path: ./jobs/cold_archiver_notebook.py

targets:
  dev:
    default: true
    workspace:
      host: https://fe-vm-hls-amer.cloud.databricks.com

  staging:
    workspace:
      host: https://fe-vm-hls-amer.cloud.databricks.com

  prod:
    workspace:
      host: https://fe-vm-hls-amer.cloud.databricks.com
"""
