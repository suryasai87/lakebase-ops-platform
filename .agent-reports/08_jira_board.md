# FEIP Jira Board Analysis (Board 19732)

**Generated:** 2026-04-05
**Project:** FEIP (Field Engineering Innovation Platform)
**Source:** Jira Cloud API via MCP

---

## Board Status Summary

| Status | Count (sampled) | Notes |
|--------|----------------|-------|
| **In Progress** | 50+ | Largest column by far |
| **Blocked** | 20 | Significant blockers needing triage |
| **Idea** | 15+ | Backlog / ideation pipeline |
| **NOT STARTED** | 15+ | Accepted but not yet picked up |
| **Active** | 6+ | Actively being worked (distinct from In Progress) |
| **Done / Completed** | 30+ | Recently completed items |
| **Github - Repo Creation** | 1 | FEIP-5423 |

---

## Priority Distribution

| Priority | Count (sampled) | Key Examples |
|----------|----------------|--------------|
| **Critical** | 1 | FEIP-5271: Centralized Lakebase Sync Monitor (Idea) |
| **Major** | ~80+ | Bulk of the board |
| **Minor** | ~20+ | Lower-priority features and improvements |
| **Trivial** | ~5 | Older items, low urgency |

**Notable:** Only 1 Critical-priority ticket exists (FEIP-5271 -- Lakebase Sync Monitor), and it is still in "Idea" status. This is directly relevant to lakebase-ops-platform.

---

## Blocked Items (20 tickets)

These require attention and potential escalation:

| Key | Summary | Assignee | Priority |
|-----|---------|----------|----------|
| FEIP-5306 | Fix MAS polling issue -- Background polling for async MAS responses | Carlota Lopes Dias | Major |
| FEIP-5101 | Automate dashboard definition export to git repo (blocked by IP allow lists) | Unassigned | Major |
| FEIP-2790 | **TF Exporter: Support for Lakebase, including branches** | Unassigned | Major |
| FEIP-2619 | Airtable Connector - Lakeflow Community Connector template | Kaustav Paul | Major |
| FEIP-2607 | Azure Graph API connector | Anshu Roy | Major |
| FEIP-2602 | IBM Maximo Connector | Drew Triplett | Major |
| FEIP-2280 | Serverless access control and Ratelimits collateral | Debadatta Mohapatra | Major |
| FEIP-2191 | UC Foreign catalog configuration (on-prem HMS) | PJ Singh | Major |
| FEIP-2190 | Establish secure network path (Databricks <-> on-prem HMS) | PJ Singh | Major |
| FEIP-2136 | HMS Iceberg | PJ Singh | Major |
| FEIP-1510 | MapAid - ML Modeling | Michael Berk | Major |
| **FEIP-1444** | **Lakebase cost attribution** | Unassigned | Major |
| FEIP-1442 | Query Syntax conversion | Unassigned | Major |
| FEIP-1367 | Get Opal fixed for DBLDatagen access | Guenia Izquierdo Delgado | Major |
| FEIP-1330 | Front end app for Champion table (logfood schema) | Arijit Banerjee | Major |
| FEIP-1157 | Adjust agent case (sensor data + tools) | Nikolaos Servos | Major |
| FEIP-1156 | Genie Space | Nikolaos Servos | Major |
| FEIP-1153 | Databricks App on top of Agent | Nikolaos Servos | Major |
| FEIP-1118 | Access to Google Sheets | Cathy Snell | Major |
| FEIP-1114 | Access to QualtricsXM | Cathy Snell | Major |

**Lakebase-specific blockers:** FEIP-2790 (TF Exporter Lakebase support) and FEIP-1444 (Lakebase cost attribution) are both blocked and unassigned.

---

## Lakebase-Related Tickets (All Statuses)

### In Progress / Active

| Key | Summary | Assignee | Status | Labels |
|-----|---------|----------|--------|--------|
| FEIP-5685 | Lakebase (cross-vertical) - Intro to 200 level | Mofeed Nagib | In Progress | -- |
| FEIP-5589 | Column-level encryption for Lakehouse and Lakebase | Andrew Weaver | Active | emea-sme, platform-sme-emea |
| FEIP-5584 | Agent Control Plane - unified control plane for AI agents | Kaan Kuguoglu | In Progress | -- |
| FEIP-5484 | **lakebase-scm extension** | Kevin Hartman | In Progress | LADT, lakebase, lakebase-for-agile-dev |
| FEIP-5315 | **Add Lakebase Autoscaling Sizing Support** | Stefan Bjelcevic | In Progress | -- |
| FEIP-5307 | **Lakebase integration for caching** (Postgres-backed session/cache via Autoscale) | Carlota Lopes Dias | In Progress | -- |
| FEIP-5276 | **Lakebase State Management for Agentic Applications** | Elliott Stam | Active | -- |
| FEIP-5275 | Smart Merchandising Agent (Genie + Lakebase + data enrichment) | Elliott Stam | Active | Apps, Lakebase, retail-cpg |
| FEIP-3106 | **[Ops] Lakebase & Genie Field Intelligence Hub** | Rishi Ghose | In Progress | Genie, Lakebase, adoption-wg, aibi |

### Ideas / Not Started (Backlog)

| Key | Summary | Assignee | Status | Labels |
|-----|---------|----------|--------|--------|
| **FEIP-5271** | **Centralized Lakebase Sync Monitor** | Unassigned | Idea | fe-ip, lakebase, monitoring -- **CRITICAL priority** |
| FEIP-5433 | Lakebase MCP Server (hosted on Databricks Apps) | Unassigned | Idea | lakebase, lakebase-emea |
| FEIP-5425 | Cohort Builder - NLP-to-SQL RWE Patient Cohort App | Unassigned | Idea | hls, lakebase, open-source |
| FEIP-5424 | Protocol Designer - Eligibility Simulator App | Unassigned | Idea | hls, lakebase, open-source |
| FEIP-5423 | Public Site Workbench (ClinicalTrials.gov) | Nicholas Siebenlist | Github - Repo Creation | hls, lakebase |
| FEIP-5422 | Enrollment Optimizer - ML Site Enrollment Forecasting | Unassigned | Idea | hls, lakebase |
| FEIP-5420 | Clinical Operations Hub - HLS Industry App Suite | Unassigned | Idea | hls, lakebase |
| FEIP-5371 | Nominatim Geocoding Server on Lakebase | Unassigned | Idea | -- |
| FEIP-5292 | **Lakebase in a box** workshop and demo | Benjamin Nwokeleme | Idea | -- |
| FEIP-5291 | **[Lakebase Compete] Competitive Intelligence Plugin** | Srikant Das | Idea | lakebase, competitive-intelligence |
| FEIP-5107 | Lakebase Demos (EMEA) | Unassigned | Idea | Lakebase, emea-lakebase-sme |
| FEIP-5100 | GenAI App Builder (LangGraph + Lakebase) | Unassigned | Idea | emea-lakebase-sme |
| FEIP-5092 | LADT-WS3: CI/CD Integrations | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-5091 | LADT-WS1: Lakebase CLI & API Compatibility | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-5089 | LADT-WS2: IDE Plugins | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-5088 | LADT-WS7: Community & Partner Evangelism | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-5084 | LADT-WS6: Internal Dogfooding & Demo | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-5082 | LADT-WS4: Unity Catalog Masking Propagation | Kevin Hartman | Idea | LADT, lakebase |
| FEIP-4807 | LakeShift: Pluggable Code Migration Workbench | Irvin Umana | Idea | lakebase, ucx |
| FEIP-4805 | Packaging: dbdemos Format + Distribution (care-coordination) | Unassigned | NOT STARTED | HLS, lakebase |
| FEIP-4800 | Backend API: Persistent Alerts (care-coordination) | Unassigned | NOT STARTED | HLS, lakebase |
| FEIP-4799 | Backend API: Clinical Trends (care-coordination) | Unassigned | NOT STARTED | HLS, lakebase |
| FEIP-4798 | Backend API: Conversation History (care-coordination) | Unassigned | NOT STARTED | HLS, lakebase |
| FEIP-4797 | Backend API: Agent State Viewer (care-coordination) | Unassigned | NOT STARTED | HLS, lakebase |

### Blocked (Lakebase)

| Key | Summary | Status |
|-----|---------|--------|
| **FEIP-2790** | TF Exporter: Support for Lakebase (branches, new features) | Blocked |
| **FEIP-1444** | Lakebase cost attribution | Blocked |

### Completed (Lakebase)

| Key | Summary | Assignee | Status |
|-----|---------|----------|--------|
| FEIP-5393 | Cohort Builder -- NLP-to-SQL RWE Patient Cohort App (Open Source) | Unassigned | Done |
| FEIP-5392 | Protocol Designer -- Eligibility Simulator App (Open Source) | Unassigned | Done |
| FEIP-5391 | Public Site Workbench -- ClinicalTrials.gov App (Open Source) | Unassigned | Done |
| FEIP-5390 | Enrollment Optimizer -- ML Site Enrollment Forecasting App | Unassigned | Done |
| FEIP-5102 | **Lakebase Lineage & Branch Visualizer** | Unassigned | Completed |
| FEIP-2927 | Add demo data to Lakebase instance and deploy App | Sander Lam | Done |
| FEIP-2862 | Lakebase Examples | Grant Doyle | Completed |
| FEIP-2185 | GenAI blog: cybersecurity AI agent with Lakebase memory | Austin Choi | Completed |
| FEIP-2141 | TF Exporter: Add exporting of Lakebase instances | Alex Ott | Done |

---

## Relevance to lakebase-ops-platform

The following tickets are **directly relevant** to the lakebase-ops-platform codebase:

1. **FEIP-5271 (CRITICAL)** -- Centralized Lakebase Sync Monitor. This is the only Critical-priority ticket in FEIP. It is unassigned and in "Idea" status. The lakebase-ops-platform's monitoring capabilities could address this.

2. **FEIP-5315** -- Add Lakebase Autoscaling Sizing Support (Stefan Bjelcevic, In Progress). Directly related to the sizing/performance pages in lakebase-ops-platform.

3. **FEIP-5307** -- Lakebase integration for caching (Carlota Lopes Dias, In Progress). Postgres-backed session/cache/audit storage via Lakebase Autoscale.

4. **FEIP-5276** -- Lakebase State Management for Agentic Applications (Elliott Stam, Active). Reusable pattern for persistent agent context.

5. **FEIP-3106** -- [Ops] Lakebase & Genie Field Intelligence Hub (Rishi Ghose, In Progress). Directly overlaps with ops monitoring use case.

6. **FEIP-1444 (BLOCKED)** -- Lakebase cost attribution. Unassigned and blocked. The lakebase-ops-platform could potentially help unblock this with cost tracking features.

7. **FEIP-5484** -- lakebase-scm extension (Kevin Hartman, In Progress). SCM tooling for Lakebase -- developer experience focus.

---

## Assignee Workload (Top Contributors by Active Ticket Count)

| Assignee | Active Tickets | Focus Areas |
|----------|---------------|-------------|
| Kevin Hartman | 7+ | LADT (Lakebase for Agile Dev) -- SCM, CI/CD, IDE, CLI |
| Mattia Zeni | 8 | [LOAD] Energy APIs (Italy) |
| Alex Ott | 4+ | Lakewatch Presets (security log sources) |
| Leighton Nelson | 2 | BrickBoard, Tech Gym platforms |
| Greg Hansen | 2 | Copy/Ingestion from SQL DBs and SFTP |
| Carlota Lopes Dias | 2 | Lakebase caching, MAS evaluation |
| Elliott Stam | 2 | Lakebase state mgmt, Smart Merchandising |
| Ash Sultan | 2 | dbt on Databricks setup |
| David Rogers | 2 | Open Upstream Ref Architecture, Order Processing |
| Sepideh Ebrahimi | 2 | AI Roadmap delivery, AI in Action |

---

## Recently Completed Items (Last 14 Days)

| Key | Summary | Assignee |
|-----|---------|----------|
| FEIP-5687 | [slack-taxonomy] Iterative rehydration -- run until schema-validate passes | Unassigned |
| FEIP-5686 | [slack-taxonomy] Schema validation enforcement for pipeline outputs | Unassigned |
| FEIP-5682 | [slack-taxonomy] taxonomy-hydrate skill -- deep initial hydration | Unassigned |
| FEIP-5679 | [slack-taxonomy] Dynamic relationship strength from thread overlap | Unassigned |
| FEIP-5677 | [slack-taxonomy] Cross-channel signal amplification | Unassigned |
| FEIP-5676 | [slack-taxonomy] memory-sync skill -- git backup | Unassigned |
| FEIP-5675 | [slack-taxonomy] topic-recall skill -- 'What's happening with X?' | Unassigned |
| FEIP-5674 | [slack-taxonomy] Message ingestion + memory bank generation | Unassigned |
| FEIP-5673 | [slack-taxonomy] SME auto-discovery and authority registry | Unassigned |
| FEIP-5672 | [slack-taxonomy] Obsidian-compliant per-topic memory banks | Unassigned |
| FEIP-5670 | [slack-taxonomy] Map all 605 channels to taxonomy -- 100% coverage | Unassigned |
| FEIP-5669 | [slack-taxonomy] Re-seed taxonomy v2.0.0 with 605-channel dataset | Unassigned |
| FEIP-5640 | [Tech Gym] Implement real user auth via Databricks Apps headers | Unassigned |
| FEIP-5627 | BOLT: 6 Collectors Implementation | Lingeshwaran Kanniappan |
| FEIP-5488 | BOLT: Scaffold project structure + docs + core patterns | Lingeshwaran Kanniappan |
| FEIP-5359 | ASQ Hygiene Dashboard - Real-time SSA team monitoring | Howard Horowitz |
| FEIP-5273 | Data Intelligence in Cybersecurity Threat Hunting | Alan Mazankiewicz |
| FEIP-5200 | Data quality auto-triage (Levenshtein detection) | Scott Smith |

**Trend:** Heavy recent velocity on slack-taxonomy features (12 tickets completed). BOLT project scaffolding also shipped.

---

## Key Observations

1. **Lakebase is the dominant theme** -- 40+ tickets reference Lakebase across all statuses. It is the single most active area in FEIP.

2. **The only CRITICAL ticket (FEIP-5271) is Lakebase-related** and unassigned. "Centralized Lakebase Sync Monitor" aligns directly with lakebase-ops-platform's mission. This should be claimed.

3. **Two Lakebase tickets are blocked** (FEIP-2790 TF Exporter Lakebase support, FEIP-1444 cost attribution) -- both unassigned. These represent stalled infrastructure work.

4. **Kevin Hartman owns the LADT (Lakebase for Agile Dev) workstream** with 7+ tickets spanning CLI, IDE plugins, CI/CD, and SCM extensions. All are in "Idea" status except FEIP-5484 (lakebase-scm, In Progress).

5. **HLS vertical has a large Lakebase backlog** -- 6+ care-coordination API tickets (FEIP-4797 through FEIP-4805) are all NOT STARTED with no assignee.

6. **No tickets explicitly reference "lakebase-ops-platform"** by repo name. The closest match is FEIP-3106 ([Ops] Lakebase & Genie Field Intelligence Hub) and FEIP-5271 (Centralized Lakebase Sync Monitor).

7. **Board hygiene concern:** Many In Progress tickets (FEIP-1013, FEIP-1536, FEIP-2442, FEIP-2558, FEIP-2844, FEIP-2888) appear to be stale (ticket numbers suggest they are months old). Consider a sprint cleanup.
