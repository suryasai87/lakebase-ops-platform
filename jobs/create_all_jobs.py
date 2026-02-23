"""Create all LakebaseOps Databricks Jobs from definitions."""

import json
import subprocess
import sys

from databricks_job_definitions import JOB_DEFINITIONS

PROFILE = "DEFAULT"


def create_job(key: str, definition: dict):
    """Create a single Databricks job."""
    print(f"\nCreating job: {definition['name']}")

    # Update notebook paths to workspace location
    for task in definition.get("tasks", []):
        nb = task.get("notebook_task", {})
        if "notebook_path" in nb:
            nb["notebook_path"] = nb["notebook_path"].replace(
                "/Repos/lakebase-ops", "/Workspace/Repos/lakebase-ops"
            )

    # Use serverless compute instead of job clusters
    for task in definition.get("tasks", []):
        task.pop("job_cluster_key", None)

    definition.pop("job_clusters", None)

    payload = json.dumps(definition)
    result = subprocess.run(
        ["databricks", "jobs", "create", "--json", payload, "--profile", PROFILE],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        job_id = json.loads(result.stdout).get("job_id", "unknown")
        print(f"  Created: job_id={job_id}")
        return job_id
    else:
        print(f"  Error: {result.stderr.strip()}")
        return None


def main():
    print("=" * 60)
    print("LakebaseOps - Creating All Databricks Jobs")
    print("=" * 60)

    created = {}
    for key, defn in JOB_DEFINITIONS.items():
        job_id = create_job(key, defn.copy())
        if job_id:
            created[key] = job_id

    print(f"\n{'=' * 60}")
    print(f"Created {len(created)}/{len(JOB_DEFINITIONS)} jobs")
    for k, v in created.items():
        print(f"  {k}: {v}")

    if len(created) < len(JOB_DEFINITIONS):
        sys.exit(1)


if __name__ == "__main__":
    main()
