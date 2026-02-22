"""
CICDMixin — CI/CD Pipeline (Tasks 26-32)

Contains:
- setup_cicd_pipeline
"""

from __future__ import annotations

import logging

logger = logging.getLogger("lakebase_ops.provisioning")


class CICDMixin:
    """Mixin providing CI/CD pipeline generation."""

    def setup_cicd_pipeline(self, project_id: str, repo_owner: str = "org",
                            repo_name: str = "app") -> dict:
        """
        Generate GitHub Actions YAML for branch automation.
        Tasks 26-32 + PRD FR-06.
        """
        create_yaml = f"""name: Lakebase Branch on PR Open
on:
  pull_request:
    types: [opened, reopened]

env:
  LAKEBASE_PROJECT: {project_id}

jobs:
  create-branch:
    runs-on: ubuntu-latest
    steps:
      - name: Install Databricks CLI
        run: curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

      - name: Create Lakebase Branch
        env:
          DATABRICKS_HOST: ${{{{ secrets.DATABRICKS_HOST }}}}
          DATABRICKS_TOKEN: ${{{{ secrets.DATABRICKS_TOKEN }}}}
        run: |
          databricks postgres create-branch \\
            "projects/${{{{ env.LAKEBASE_PROJECT }}}}" \\
            "ci-pr-${{{{ github.event.pull_request.number }}}}" \\
            --json '{{
              "spec": {{
                "source_branch": "projects/'${{{{ env.LAKEBASE_PROJECT }}}}'/branches/staging",
                "ttl": "14400s"
              }}
            }}'

      - name: Wait for Branch Active
        run: |
          for i in $(seq 1 30); do
            STATUS=$(databricks postgres get-branch \\
              "projects/${{{{ env.LAKEBASE_PROJECT }}}}/branches/ci-pr-${{{{ github.event.pull_request.number }}}}" \\
              --output json | jq -r '.status.state')
            if [ "$STATUS" = "ACTIVE" ]; then break; fi
            sleep 10
          done

      - name: Apply Migrations
        run: |
          # Apply migrations to ephemeral branch
          echo "Applying migrations to ci-pr-${{{{ github.event.pull_request.number }}}}"
"""

        delete_yaml = f"""name: Lakebase Branch Cleanup on PR Close
on:
  pull_request:
    types: [closed]

env:
  LAKEBASE_PROJECT: {project_id}

jobs:
  delete-branch:
    runs-on: ubuntu-latest
    steps:
      - name: Install Databricks CLI
        run: curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

      - name: Delete Lakebase Branch
        env:
          DATABRICKS_HOST: ${{{{ secrets.DATABRICKS_HOST }}}}
          DATABRICKS_TOKEN: ${{{{ secrets.DATABRICKS_TOKEN }}}}
        run: |
          databricks postgres delete-branch \\
            "projects/${{{{ env.LAKEBASE_PROJECT }}}}/branches/ci-pr-${{{{ github.event.pull_request.number }}}}" \\
            || true
"""

        return {
            "project_id": project_id,
            "create_branch_yaml": create_yaml,
            "delete_branch_yaml": delete_yaml,
            "secrets_required": ["DATABRICKS_HOST", "DATABRICKS_TOKEN"],
            "variables_required": ["LAKEBASE_PROJECT"],
        }
