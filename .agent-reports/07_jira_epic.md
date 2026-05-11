# Jira Epic Analysis: FEIP-5484 -- lakebase-scm extension

**Generated:** 2026-04-05
**Source:** Jira FEIP project (live MCP API)

---

## 1. Epic Overview

| Field | Value |
|-------|-------|
| **Key** | FEIP-5484 |
| **Summary** | lakebase-scm extension |
| **Type** | Task |
| **Status** | In Progress |
| **Priority** | Major |
| **Assignee** | Kevin Hartman (FE Indirect) |
| **Created** | 2026-03-25 |
| **Updated** | 2026-03-25 |
| **Labels** | `LADT`, `developer-experience`, `lakebase`, `lakebase-for-agile-dev` |
| **Components** | None |
| **Story Points** | Not set |
| **Sprint** | Not assigned |

## 2. Description

A VS Code / Cursor extension that synchronizes Git branches with Lakebase database branches, providing automatic branch creation, connection string management, and branch visualization for agile developers.

**GitHub Repo:** https://github.com/kevin-hartman_data/lakebase-scm-extension

## 3. Progress to Date

- Extension built and functional in VS Code and Cursor
- Automatic Git-to-Lakebase branch synchronization -- when a developer creates a new Git branch, a corresponding Lakebase database branch is automatically created
- Connection string management -- the DB connection string automatically follows the active branch
- Demoed to ThoughtWorks (March 2026) -- well received, sparked discussion about commercial offerings and blog collaboration with Pramod Sadalage

## 4. Acceptance Criteria

No explicit acceptance criteria defined in the ticket. Based on description, implicit criteria:

1. Extension installs and runs in VS Code and Cursor
2. Creating a Git branch automatically creates a matching Lakebase database branch
3. Connection string updates automatically when switching Git branches
4. Branch visualization available in the IDE sidebar

## 5. Comments

| Date | Author | Content |
|------|--------|---------|
| 2026-03-25 | Automation for Jira | "Please review the submission." |

No implementation decision comments found.

---

## 6. Parent Initiative: LADT (Lakebase for Agile Dev Teams)

FEIP-5484 is part of a broader initiative tracked under **FEIP-5081** -- "LADT-WS0 - Lakebase for Agile Dev Teams - Overview & Planning". This is a 12-month campaign with 7 workstreams.

### 6.1 Initiative Summary

Lakebase delivers instant, copy-on-write database branching for Postgres -- the missing capability that has constrained agile development for 25 years. The initiative covers tooling, methodology codification, internal dogfooding, and community evangelism.

### 6.2 Key Stakeholders

Kevin Hartman, Jonathan Katz, Ryan DeCosmo, Denny Lee, Alex Moore, Lakebase Engineering, Unity Catalog PM

### 6.3 Key Resources

- [Position Paper: Lakebase for Agile Dev Teams](https://docs.google.com/document/d/1rvhrQDb86vkMwrIZTqu8HwC3mql-RH44uP32VKcp3Cw/edit)
- [Slide Deck: Lakebase for Agile Dev Teams Presentation](https://docs.google.com/presentation/d/1IzJ1imXNqdNzi7L25VBjEe0v4ZqkITf0VyZDPvpfHyU/edit)

---

## 7. All Workstream Issues (Linked to FEIP-5081)

| # | Key | Summary | Type | Status | Assignee | Labels |
|---|-----|---------|------|--------|----------|--------|
| 0 | [FEIP-5081](https://databricks.atlassian.net/browse/FEIP-5081) | LADT-WS0: Overview & Planning | Epic | **Active** | Kevin Hartman | LADT, agile, database-branching, developer-experience, lakebase, lakebase-for-agile-dev |
| 1 | [FEIP-5091](https://databricks.atlassian.net/browse/FEIP-5091) | LADT-WS1: Lakebase CLI & API Compatibility | Epic | Idea | Kevin Hartman | LADT, agile, database-branching, developer-experience, lakebase, lakebase-for-agile-dev |
| 2 | [FEIP-5089](https://databricks.atlassian.net/browse/FEIP-5089) | LADT-WS2: IDE Plugins | Epic | Idea | Kevin Hartman | LADT, agile, database-branching, developer-experience, lakebase, lakebase-for-agile-dev |
| 3 | [FEIP-5092](https://databricks.atlassian.net/browse/FEIP-5092) | LADT-WS3: CI/CD Integrations | Epic | Idea | Kevin Hartman | LADT, agile, database-branching, developer-experience, lakebase, lakebase-for-agile-dev |
| 4 | [FEIP-5082](https://databricks.atlassian.net/browse/FEIP-5082) | LADT-WS4: Unity Catalog Masking Propagation | Epic | Idea | Kevin Hartman | -- |
| 5 | [FEIP-5090](https://databricks.atlassian.net/browse/FEIP-5090) | LADT-WS5: Methodology Codification | Epic | Idea | Unassigned | -- |
| 6 | [FEIP-5084](https://databricks.atlassian.net/browse/FEIP-5084) | LADT-WS6: Internal Dogfooding & Demo | Epic | Idea | Kevin Hartman | -- |
| 7 | [FEIP-5088](https://databricks.atlassian.net/browse/FEIP-5088) | LADT-WS7: Community & Partner Evangelism | Epic | Idea | Kevin Hartman | -- |
| -- | [FEIP-5484](https://databricks.atlassian.net/browse/FEIP-5484) | **lakebase-scm extension** (this ticket) | Task | **In Progress** | Kevin Hartman | LADT, developer-experience, lakebase, lakebase-for-agile-dev |

### Status Distribution

- **Active / In Progress:** 2 (FEIP-5081 overview, FEIP-5484 extension)
- **Idea (backlog):** 7 (all other workstreams)
- **No subtasks** found on any workstream epic

---

## 8. Workstream Detail Breakdown

### WS1: Lakebase CLI & API Compatibility (FEIP-5091) -- Idea

- Build Databricks Lakebase CLI with `branches create/delete/list/reset` commands
- Port Schema Diff capabilities from Neon CLI to Databricks CLI
- Implement post-checkout Git hook -- auto-create DB branch on `git checkout`, write `DATABASE_URL` to `.env`
- Build Lakebase MCP Server for AI agent integration (Claude Code, Cursor, Jules)
- Validate Claude Code `--worktree` flow end-to-end against Lakebase

### WS2: IDE Plugins (FEIP-5089) -- Idea

**Phase 1: VS Code / Cursor Extension** (FEIP-5484 is the active implementation of this)
- Core SCM sync, branch visualization, schema diff/migration, CI/CD integration, Unity Catalog integration

**Phase 2: JetBrains Plugin** (IntelliJ, DataGrip, Rider)
- Port core logic from VS Code extension

**Phase 3: Visual Studio Extension**
- Windows/.NET enterprise support

### WS3: CI/CD Integrations (FEIP-5092) -- Idea

- Port Neon GitHub Actions to Lakebase (create-branch, delete-branch, reset-branch, schema-diff)
- Build Jenkins shared library for Lakebase branch lifecycle
- Build GitLab CI component -- native MR integration, collapsible schema diff
- Build Azure DevOps marketplace extension
- Port Neon CircleCI Orb to Lakebase
- Schema diff as first-class PR artifact via GitHub Checks API

### WS4: Unity Catalog Masking Propagation (FEIP-5082) -- Idea

- Confirm UC column-level masking propagation timeline with UC PM
- Validate masking auto-applies on branch creation (PII/PHI/PCI)
- Build masking validation test suite for QA
- Document interim manual RLS workaround until auto-propagation ships

### WS5: Methodology Codification (FEIP-5090) -- Idea (Unassigned)

- Branch-Based Development Playbook (M1)
- DBA Platform Architect Transition Guide (M2)
- Database Branching Maturity Model (M3) -- 5-level staged adoption
- Story Estimation Impact Guide (M4) and Business Case Template (M5)
- Updated Definition of Done

### WS6: Internal Dogfooding & Demo (FEIP-5084) -- Idea

- Identify 2-3 internal Databricks projects for dogfooding
- Build Lakebase Developer Experience demo -- live demo + talk track
- Build Easy Path Use Case Guide for field implementation
- Capture dogfooding metrics (time saved, mocks retired, DBA ticket reduction)
- Create Customer Case Study Template

### WS7: Community & Partner Evangelism (FEIP-5088) -- Idea

- Brief Denny Lee + DevRel (Data Brew, DevConnect, Open Source Day)
- Engage ThoughtWorks (Alex Moore) -- co-develop plugin, co-author thought leadership
- Submit conference talks: Agile Alliance, QCon, GOTO, DevOpsDays, PGConf
- Publish blog series
- Partner practice briefings (Accenture, Deloitte, Slalom)
- Engage thought leaders: Martin Fowler, Kent Beck, Scott Ambler

---

## 9. Related Issues (Not Part of LADT)

| Key | Summary | Status | Assignee |
|-----|---------|--------|----------|
| [FEIP-5589](https://databricks.atlassian.net/browse/FEIP-5589) | Define column-level encryption approach for Lakehouse and Lakebase | Active | Andrew Weaver (FE Direct - International) |
| [FEIP-1167](https://databricks.atlassian.net/browse/FEIP-1167) | Lakebase Migrations: Extend Hybrid SQL Dialect Translation for PostgreSQL | Idea | Sajith Appukuttan |

---

## 10. Blockers and Dependencies

### Explicit Blockers

None formally linked in Jira.

### Identified Risks (from FEIP-5081)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Unity Catalog masking may not propagate to branches | Blocks compliant dev with real data | Requires engineering validation; interim manual RLS workaround documented in WS4 |
| No branch merge capability yet | Branch reset only; limits workflow flexibility | Engineering dependency -- no workaround |
| No GCP region support | Limits customer reach | AWS/Azure only for now |
| 10 branch limit per database | Constrains large teams with many parallel features | May need engineering uplift |
| Velocity improvement claims (20-40%) unvalidated | Marketing/positioning risk | WS6 dogfooding will generate real data |

### Implicit Dependencies

```
FEIP-5484 (lakebase-scm extension)
  DEPENDS ON:
    FEIP-5091 (WS1: CLI & API) -- Extension needs CLI/API for branch operations
    FEIP-5082 (WS4: UC Masking) -- For compliant dev data in branches
  
  FEEDS INTO:
    FEIP-5089 (WS2: IDE Plugins) -- Extension IS Phase 1 of WS2
    FEIP-5092 (WS3: CI/CD) -- Extension hooks enable CI/CD integration
    FEIP-5084 (WS6: Dogfooding) -- Extension is the primary dogfooding vehicle
    FEIP-5088 (WS7: Evangelism) -- ThoughtWorks demo already happened
```

---

## 11. Task Dependency Graph

```
                    FEIP-5081 (WS0: Overview & Planning) [Active]
                                    |
                 ┌──────────────────┼──────────────────────────────┐
                 |                  |                               |
         FEIP-5091 (WS1)    FEIP-5082 (WS4)                FEIP-5090 (WS5)
         CLI & API [Idea]   UC Masking [Idea]               Methodology [Idea]
                 |                  |                               |
                 v                  v                               v
    ┌────────────────────────────────────┐                  (documentation
    |                                    |                   deliverables)
    |     FEIP-5484 (this ticket)        |
    |     lakebase-scm extension         |
    |     [IN PROGRESS]                  |
    |                                    |
    └────────┬───────────┬───────────────┘
             |           |
             v           v
      FEIP-5089 (WS2)  FEIP-5092 (WS3)
      IDE Plugins       CI/CD Integrations
      [Idea]            [Idea]
             |           |
             v           v
      FEIP-5084 (WS6: Dogfooding) [Idea]
                    |
                    v
      FEIP-5088 (WS7: Evangelism) [Idea]
```

**Critical path:** WS1 (CLI/API) --> FEIP-5484 (Extension) --> WS2 (IDE Plugins) --> WS3 (CI/CD) --> WS6 (Dogfooding) --> WS7 (Evangelism)

---

## 12. 12-Month Campaign Timeline

| Phase | Timeframe | Focus | Key Deliverables |
|-------|-----------|-------|-----------------|
| **Phase 1 -- Foundation** | Q1 2026 | CLI, MCP Server, position paper, internal dogfooding kickoff | FEIP-5091, FEIP-5484 (in progress), FEIP-5081 |
| **Phase 2 -- Community Seeding** | Q1-Q2 2026 | IDE plugins, CI/CD integrations, playbook, conference CFPs | FEIP-5089, FEIP-5092, FEIP-5090, FEIP-5088 |
| **Phase 3 -- Scaling** | Q2-Q4 2026 | Partner enablement, conference talks, case studies, maturity model | FEIP-5084, FEIP-5088 continued |

---

## 13. Observations and Gaps

1. **FEIP-5484 is running ahead of its dependencies.** The extension is In Progress while WS1 (CLI & API) is still in Idea status. This suggests Kevin built the extension directly against Lakebase APIs rather than waiting for CLI tooling.

2. **No story points or sprint assignments** on any of the 9 tickets. This makes capacity planning difficult.

3. **No subtasks** on any workstream epic. The work items within each workstream are listed in descriptions but not broken into trackable subtasks.

4. **WS5 (Methodology Codification) is unassigned.** All other workstreams are assigned to Kevin Hartman, creating a single-point-of-failure risk.

5. **ThoughtWorks demo already happened** (March 2026), which means WS7 evangelism has started informally even though the ticket is in Idea status.

6. **The extension GitHub repo** (kevin-hartman_data/lakebase-scm-extension) should be reviewed for completeness against the WS2 Phase 1 scope in FEIP-5089.

7. **No formal link** between FEIP-5484 and FEIP-5089 (WS2: IDE Plugins) in Jira, despite FEIP-5484 being the implementation of WS2 Phase 1.

---

*Report generated from Jira MCP API on 2026-04-05.*
