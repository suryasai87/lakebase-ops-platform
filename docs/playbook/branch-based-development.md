# Branch-Based Development Playbook

## Overview

Lakebase branches are analogous to Git branches for databases. They use copy-on-write storage for instant creation regardless of database size. This playbook covers patterns for integrating Lakebase branching into your development workflow.

## Branching Patterns

### 1. Simple Dev/Prod

Best for small teams (1-3 developers) with straightforward release cycles.

```
production (protected)
  └── development (TTL: 7 days, auto-renew)
```

- Developers work directly on `development`
- Schema migrations tested on `development`, then applied to `production`
- No staging gate

### 2. Multi-Environment Pipeline

Best for teams with formal release processes and QA requirements.

```
production (protected)
  ├── staging (protected)
  │     └── development (TTL: 7 days)
  └── ci-pr-{number} (TTL: 4 hours, auto-delete)
```

- Pull requests get ephemeral branches for integration testing
- Migrations flow: development -> staging -> production
- Schema diff validates each promotion

### 3. Per-Developer Branches

Best for larger teams where developers need isolated environments.

```
production (protected)
  ├── staging (protected)
  └── dev-{firstname} (TTL: 7 days each)
```

- Each developer gets a personal branch
- Branches reset nightly from staging (optional)
- Merge conflicts resolved at schema diff time

### 4. CI/CD Ephemeral

Best for automated pipelines where every PR gets a fresh database.

```
production (protected)
  └── ci-pr-{number} (TTL: 4 hours)
```

- GitHub Actions / GitLab CI creates branch on PR open
- Migrations applied automatically
- Schema diff posted as PR comment
- Branch deleted on PR close

## Branch Naming Conventions

All names must be RFC 1123 compliant: lowercase, alphanumeric, hyphens only, max 63 characters.

| Prefix | Pattern | TTL | Use Case |
|--------|---------|-----|----------|
| `ci-` | `ci-pr-{number}` | 4 hours | CI/CD pull request testing |
| `hotfix-` | `hotfix-{ticket_id}` | 24 hours | Emergency production fixes |
| `perf-` | `perf-{test_name}` | 48 hours | Performance/load testing |
| `feat-` | `feat-{description}` | 7 days | Feature development |
| `dev-` | `dev-{firstname}` | 7 days | Personal dev environment |
| `demo-` | `demo-{customer}` | 14 days | Customer demonstrations |
| `qa-` | `qa-release-{version}` | 14 days | QA release testing |
| `audit-` | `audit-{date}` | 30 days | Compliance/audit snapshots |
| `ai-agent-` | `ai-agent-test` | 1 hour | AI agent sandboxed testing |

## Workflow: Schema Migration via Branches

1. **Create branch** from staging or production
2. **Apply migration SQL** on the branch
3. **Run schema diff** comparing branch vs source
4. **Run integration tests** against the branch
5. **Review diff** -- human or automated approval
6. **Apply migration** to target (staging/production)
7. **Delete branch** (or let TTL auto-delete)

## Branch Limits

- Max 500 branches per project (10 unarchived at a time)
- Max 3 root branches
- Max 1 protected branch (production)
- Idle branches auto-archive after configurable period

## Cost Considerations

- Copy-on-write: creating branches is free (storage shared with parent)
- You pay only for changed data pages + compute time
- Enforce TTL policies to avoid orphaned branches consuming compute
- Use scale-to-zero on non-production branches
