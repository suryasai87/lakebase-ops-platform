# CI/CD Templates for Lakebase Branch-per-PR Workflow

This directory contains CI/CD pipeline templates demonstrating the **branch-per-PR** pattern for Databricks Lakebase. Each template implements the same workflow adapted to its respective CI/CD platform.

## Workflow Steps

1. **Create Branch** — Fork an ephemeral Lakebase branch from staging when a PR/MR is opened
2. **Wait for Active** — Poll until the branch reaches `ACTIVE` state
3. **Apply Migrations** — Run database migrations (Flyway, Liquibase, etc.) against the ephemeral branch
4. **Run Tests** — Execute integration tests targeting the ephemeral branch
5. **Schema Diff** — Generate and post a schema diff comparing the branch to staging
6. **Cleanup** — Delete the ephemeral branch when the PR/MR is closed or merged

## Templates

| File | Platform | Trigger |
|------|----------|---------|
| `Jenkinsfile` | Jenkins (Multibranch Pipeline) | PR via `changeRequest()` |
| `.gitlab-ci.yml` | GitLab CI | `merge_request_event` |
| `azure-pipelines.yml` | Azure DevOps | `pr:` trigger |
| `.circleci/config.yml` | CircleCI | Branch push (non-main) |

## Schema Diff Script

`post_schema_diff.py` is a standalone script that:
- Introspects schema from two Lakebase branches via the Databricks CLI
- Computes a human-readable diff (added/removed tables, column changes)
- Posts the diff as a comment on GitHub PRs or GitLab MRs
- Supports `--dry-run` and `--output-file` modes

## Active GitHub Actions CI

The active CI pipeline for this repository lives at `.github/workflows/ci.yml` and runs:
- Python tests (`pytest`)
- Frontend tests (`vitest`)
- Linting (`ruff`)
- Type checking (`mypy`)

The Lakebase branch-per-PR GitHub Actions templates are in `templates/github-actions/`.

## Prerequisites

- **Databricks CLI v0.278+** — All templates install it automatically
- **Credentials** — `DATABRICKS_HOST` and `DATABRICKS_TOKEN` must be configured as secrets/variables in your CI/CD platform
- **`LAKEBASE_PROJECT`** — Set as an environment variable or CI/CD variable
