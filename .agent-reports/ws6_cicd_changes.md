# WS6 CI/CD Changes Summary

**Agent:** WS6-CICD
**Date:** 2026-04-05
**Branch:** including_serverless_tags
**Gaps Addressed:** GAP-024, GAP-025, GAP-026, GAP-045

---

## GAP-024 (HIGH): Active CI Pipeline

**Created:** `.github/workflows/ci.yml`

Active CI pipeline triggered on push to `main` and all PRs. Three parallel jobs:

1. **python-tests** — Matrix across Python 3.10/3.11/3.12:
   - pip cache via `actions/cache@v4`
   - Install deps from `requirements.txt` + `.[dev]`
   - `ruff check .` with GitHub output format
   - `mypy` type check on `agents/`, `utils/`, `framework/` (non-blocking)
   - `pytest tests/ -v`

2. **frontend-tests** — Node.js 20:
   - `node_modules` cache via `actions/cache@v4`
   - `npm ci` (with `npm install` fallback)
   - `npm test` (runs vitest)

3. **backend-tests** — Python 3.11:
   - `pytest app/backend/tests/ -v`

Concurrency group set to cancel redundant runs on the same ref.

---

## GAP-025 (HIGH): CI/CD Platform Templates

**Created directory:** `cicd_templates/`

All four templates implement the same branch-per-PR Lakebase workflow:
1. Create ephemeral branch from staging with 4-hour TTL
2. Wait for ACTIVE state (30 attempts, 10s interval)
3. Apply migrations (placeholder for Flyway/Liquibase)
4. Run integration tests
5. Generate schema diff
6. Cleanup branch on completion

| File | Platform | Notes |
|------|----------|-------|
| `cicd_templates/Jenkinsfile` | Jenkins | Multibranch Pipeline, `changeRequest()` guard, post-always cleanup |
| `cicd_templates/.gitlab-ci.yml` | GitLab CI | `merge_request_event` rules, 6-stage pipeline, YAML anchors for CLI install |
| `cicd_templates/azure-pipelines.yml` | Azure DevOps | 5-stage pipeline, `PullRequest` condition, `Bash@3` tasks |
| `cicd_templates/.circleci/config.yml` | CircleCI | Reusable commands, workflow with job dependencies, branch filter |

All templates use Databricks CLI v0.278+ (`databricks postgres` commands).

**Created:** `cicd_templates/README.md` — Documents the workflow, prerequisites, and template inventory.

---

## GAP-026 (MEDIUM): Schema Diff PR Posting

**Created:** `cicd_templates/post_schema_diff.py`

Standalone script that:
- Introspects schema from two Lakebase branches via Databricks CLI
- Computes diff (added/removed tables, column-level changes)
- Posts diff as a PR comment on **GitHub** (via REST API, with upsert to avoid duplicates)
- Posts diff as a MR note on **GitLab** (via REST API)
- Supports `--dry-run` and `--output-file` modes
- Uses `<!-- lakebase-schema-diff -->` HTML marker for idempotent comment updates

CLI usage:
```bash
python cicd_templates/post_schema_diff.py \
    --project my-project \
    --source-branch staging \
    --target-branch ci-pr-123 \
    --pr-number 123 \
    --repo-owner myorg \
    --repo-name myrepo
```

Decision: Created as standalone script rather than modifying `agents/provisioning/cicd.py` (per the rule "Do NOT modify source code or agent files").

---

## GAP-045 (LOW): Template Location

**Created:** `templates/github-actions/` directory with copies of the original templates:
- `templates/github-actions/create_branch_on_pr.yml` — with added documentation header
- `templates/github-actions/delete_branch_on_pr_close.yml` — with added documentation header

**Preserved:** `github_actions/` directory left in place (not deleted) to avoid breaking any existing references.

**Updated:** `README.md` project structure section to reflect new directory layout including `templates/github-actions/`, `cicd_templates/`, and `.github/workflows/`.

---

## Files Created

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | Active CI pipeline |
| `templates/github-actions/create_branch_on_pr.yml` | Relocated GH Actions template (branch create) |
| `templates/github-actions/delete_branch_on_pr_close.yml` | Relocated GH Actions template (branch cleanup) |
| `cicd_templates/Jenkinsfile` | Jenkins branch-per-PR template |
| `cicd_templates/.gitlab-ci.yml` | GitLab CI branch-per-PR template |
| `cicd_templates/azure-pipelines.yml` | Azure DevOps branch-per-PR template |
| `cicd_templates/.circleci/config.yml` | CircleCI branch-per-PR template |
| `cicd_templates/post_schema_diff.py` | Schema diff generator + PR comment poster |
| `cicd_templates/README.md` | CI/CD templates documentation |

## Files Modified

| File | Change |
|------|--------|
| `README.md` | Updated project structure to include new directories |

## Files NOT Modified (per rules)

- `agents/provisioning/cicd.py` — Existing agent file, not touched
- `github_actions/` — Original templates preserved for backward compatibility
