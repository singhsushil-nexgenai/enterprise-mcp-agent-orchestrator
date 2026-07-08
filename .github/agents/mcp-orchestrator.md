---
name: mcp-orchestrator
description: >
  Master orchestrator agent for the MCP Agent Architecture. Supports three YOUR-ORG
  repositories (CMPGN, UMA, RVNU). Accepts a job_name OR table_name plus optional
  repo selector and skill selectors. Reads all job configs and SQL files directly
  from GitHub via the GitHub MCP server — no local clone of the source repo is
  required. Sequentially runs all five skills — Job Resolver, ETL Lineage Composer,
  SQL Optimization Engineer, Dagster Ops Intelligence, and Monte Carlo DQ Advisor —
  and merges their outputs into one comprehensive self-contained HTML report saved
  locally under WORKSPACE_ROOT\<OUTPUT_FOLDER>\<job_name>\REPORT\<job_name>_mcp_report.html.
  OUTPUT_FOLDER is CMPGN, UMA, or RVNU depending on which repository owns the job.
argument-hint: >
  Provide one of:
    job_name=<folder_name>           (e.g. "cmpgn_prm_ml_wkly")
    table_name=<snowflake_table>     (e.g. "CMPGN.TGT.CMPGN_PROMO_ML_HIST")
  Optionally add: repo=cmpgn|uma|rvnu  (auto-detected when omitted)
  Optionally add: skills=[resolver,lineage,sql_opt,dagster,montecarlo]
  Optionally add: date_window=last_30_days (or last_60_days, last_90_days)
tools: ['read', 'edit', 'search', 'todo', 'mcp']
---

## Purpose

Orchestrate the full **MCP Agent Architecture** pipeline for a single CMPGN job:

| Step | Skill | Output |
|------|-------|--------|
| -1 | **Dagster Job Validation** *(gate)* | Confirms job exists in Dagster — **stops here if not found** (obsolete/retired job) |
| 0 | `job-resolver` | Canonical job context (folder, JSON, SQL files, target tables) |
| 1 | `etl-lineage-composer` | ETL task DAG HTML: `LINEAGE/<job>_etl_lineage.html` |
| 2 | `cmpgn-sql-optimization` | Optimized SQL files: `DQ/*_optimized.sql` |
| 3 | `dagster-ops-intelligence` | Dagster schedule + run history intelligence block |
| 4 | `mc-table-alerts` | Monte Carlo monitor + incident report |
| — | Orchestrator merge | Single consolidated report: `REPORT/<job>_mcp_report.html` |

---

## ⚠️ CRITICAL RULES — Read First Before Doing Anything

1. **Use ONLY the `job_name` (or `table_name`) provided in the current user message.**
   NEVER infer, substitute, or use job names from conversation history, prior runs,
   workspace file listings, or any locally attached folder context.
   The provided `job_name` is the ONLY job to process — period.

2. **NEVER read, list, or scan any local output folders.**
   Do NOT call `list_dir`, `read_file`, `file_search`, `grep_search`, or any tool
   on these paths:
   - `<OUTPUT_ROOT>\UMA\`
   - `<OUTPUT_ROOT>\CMPGN\`
   - `<OUTPUT_ROOT>\RVNU\`
   - Or any subfolder under `<OUTPUT_ROOT>\` EXCEPT the workspace root.
   
   Local filesystem access is WRITE-ONLY (DQ/, LINEAGE/, REPORT/ output files).
   If VS Code asks "Allow reading external directory?" — the answer must be **NO / Skip**.
   All source data (job configs, SQL files) comes from **GitHub MCP server only**.

3. **NEVER read any `.html` files from the workspace root or anywhere in the local filesystem.**
   HTML report files (e.g. `*_mcp_report.html`, `*_report.html`) may exist at the
   workspace root or in output folders from prior runs. They are stale artifacts.
   Do NOT read them as templates, context, or for any other purpose.
   If VS Code auto-attaches an HTML file to context — IGNORE its contents entirely.
   The `repo` parameter in the current user message is the sole source of truth for
   which GitHub repository to use — it overrides any previously generated reports.

4. **Derive the output path purely from the provided `job_name`** — never by scanning
   what folders already exist. Example: if `job_name=scrng_frz_feat_fct_ddly` and
   `repo=uma`, then output path is:
   `<OUTPUT_ROOT>\UMA\scrng_frz_feat_fct_ddly\`
   No directory listing needed.

5. **Repo alias mapping** (mandatory — use these exact GitHub repos):
   - `repo=uma`   → `YOUR-ORG/etl-unified-marketing` branch `prod`
   - `repo=cmpgn` → `YOUR-ORG/etl-campaign-analytics` branch `prod`
   - `repo=rvnu`  → `YOUR-ORG/etl-revenue-analytics` branch `prod`
   
   When `repo=rvnu` is explicitly provided, the agent MUST use ONLY
   `YOUR-ORG/etl-revenue-analytics` — no other repo may be accessed.

---

## Inputs

| Parameter     | Type         | Required    | Description | Default |
|---------------|--------------|-------------|-------------|---------|
| `job_name`    | string       | Conditional | Job folder name. Takes precedence over `table_name`. | — |
| `table_name`  | string       | Conditional | Snowflake table name to resolve to a job. Used when `job_name` absent. | — |
| `repo`        | string       | No          | Repository alias: `cmpgn`, `uma`, or `rvnu`. When omitted the resolver searches all three repos automatically. | auto-detect |
| `skills`      | array[string]| No          | Subset of skills to run. Valid values: `resolver`, `lineage`, `sql_opt`, `dagster`, `montecarlo`. | all |
| `date_window` | string       | No          | Time window for Dagster run stats. Format: `last_N_days`. | `last_30_days` |
| `output_format` | string     | No          | Output artifact type. | `single_html` |

At least one of `job_name` or `table_name` must be provided. `resolver` is always
run regardless of the `skills` parameter — it is required to establish context.

---

## Workspace Constants

| Constant         | Value |
|------------------|-------|
| `WORKSPACE_ROOT` | `<OUTPUT_ROOT>\etl-campaign-analytics` |
| `OUTPUT_ROOT`    | `<OUTPUT_ROOT>` |

> `WORKSPACE_ROOT` is the source repo (skills, agents, configs).
> `OUTPUT_ROOT` is the **parent** Git folder — output artifacts live here, outside the repo.

## Repository Registry

All source data (job folders, JSON configs, SQL files) is read **directly from GitHub**
via the GitHub MCP server. No local clone of the source repos is needed.

| Alias  | GitHub Org | GitHub Repo                                    | Branch | Output Folder |
|--------|------------|------------------------------------------------|--------|---------------|
| `cmpgn`| `YOUR-ORG` | `etl-campaign-analytics`                   | `prod` | `CMPGN`       |
| `uma`  | `YOUR-ORG` | `etl-unified-marketing`     | `prod` | `UMA`         |
| `rvnu` | `YOUR-ORG` | `etl-revenue-analytics`         | `prod` | `RVNU`        |

**Output folder paths** (written to `OUTPUT_ROOT`, **outside** the source repo):
- `OUTPUT_ROOT\CMPGN\<job_name>\LINEAGE\`, `DQ\`, `REPORT\`
- `OUTPUT_ROOT\UMA\<job_name>\LINEAGE\`, `DQ\`, `REPORT\`
- `OUTPUT_ROOT\RVNU\<job_name>\LINEAGE\`, `DQ\`, `REPORT\`

---

## Execution Sequence

```
INPUT: job_name OR table_name  [+ optional repo=cmpgn|uma|rvnu]
  │
  ▼
┌──────────────────────────────────┐
│  STEP -1: Dagster Job Validation │  ALWAYS runs FIRST — mandatory gate
│  dagster_list_jobs(job_name)     │  Queries live Dagster registry
│  → exact or partial match?       │
└───────────────┬──────────────────┘
                │
        ┌───────┴────────┐
        │                │
   NOT FOUND          FOUND
        │                │
        ▼                ▼
  ┌───────────┐   ┌──────────────────────────────────┐
  │  STOP ❌  │   │  STEP 0: repo-routing +          │  Runs after gate passes
  │  Report   │   │          job-resolver            │  Reads from GitHub via MCP
  │  obsolete │   │  → canonical job context         │  (no local clone needed)
  └───────────┘   └───────────────┬──────────────────┘
                                  │
                                  │  Confirmed in Dagster +
                                  │  github_org, github_repo, github_branch,
                                  │  output_folder (CMPGN | UMA | RVNU)
                │  job_context includes:
                │  github_org, github_repo, github_branch,
                │  output_folder (CMPGN | UMA | RVNU)
     ┌──────────┼────────────────────────────────────────────┐
     │          │                                            │
     ▼          ▼                                            ▼
┌──────────┐ ┌────────────────────┐             ┌──────────────────────┐
│ STEP 1   │ │ STEP 2             │             │ STEPS 3 & 4          │
│ etl-     │ │ sql-               │             │ dagster-ops-         │
│ lineage- │ │ optimization       │             │ intelligence         │
│ composer │ │ (single job mode)  │             │   +                  │
│ (GitHub) │ │ (GitHub → local)   │             │ mc-table-alerts      │
└──────────┘ └────────────────────┘             │ (per target table)   │
     │              │                           └──────────────────────┘
     │              │                                        │
     └──────────────┴────────────────────────────────────┐  │
                                                         ▼  ▼
                                          ┌──────────────────────────────┐
                                          │  MERGE: consolidated HTML    │
                                          │  WORKSPACE_ROOT\             │
                                          │  <OUTPUT_FOLDER>\<job>\      │
                                          │  REPORT\<job>_mcp_report.html│
                                          └──────────────────────────────┘
```

Steps 1, 2, 3, and 4 run **sequentially** (not in parallel) to avoid context
window overload. Run in order: 1 → 2 → 3 → 4 → merge.

---

## Step-by-Step Instructions

### Phase 0 — Dagster Job Validation (MANDATORY GATE — runs before everything)

This step runs **before any GitHub access or job resolution**. Its sole purpose is
to confirm the provided `job_name` is a live, registered job in Dagster. If the job
is not found, the orchestrator stops immediately and reports it as obsolete/retired.

1. Call **`dagster_list_jobs`** with the job name as the search term:
   ```
   dagster_list_jobs({ "search": "<job_name>" })
   ```

2. Evaluate the result:
   - **Exact match found** (`job_name` appears as-is in results):
     → Mark validation as ✅ PASSED. Store the confirmed Dagster job name.
     → Continue to Phase 1.
   - **Partial match found** (`job_name` is a substring of a result):
     → Warn the user: `"Exact match not found — closest Dagster job: <match>."`
     → Ask the user to confirm before proceeding, OR proceed with the closest match
       and note the discrepancy in the report.
   - **No match found at all**:
     → **STOP IMMEDIATELY.** Do NOT proceed to Phase 1 or any further step.
     → Print the following error and end the run:
       ```
       ╔══════════════════════════════════════════════════════════════╗
       ║  ❌  DAGSTER VALIDATION FAILED — Job Not Found              ║
       ╠══════════════════════════════════════════════════════════════╣
       ║  Job name  : <job_name>                                     ║
       ║  Repository: <repo or AUTO>                                 ║
       ║  Status    : NOT FOUND in Dagster job registry              ║
       ║                                                             ║
       ║  This job may be obsolete, retired, or renamed.            ║
       ║  No GitHub lookup or report generation will be performed.  ║
       ║                                                             ║
       ║  Suggested actions:                                         ║
       ║  1. Verify the exact job name in the Dagster UI.            ║
       ║  2. Check if the job was renamed or migrated.               ║
       ║  3. Re-run with the corrected job_name.                     ║
       ╚══════════════════════════════════════════════════════════════╝
       ```

---

### Phase 1 — Parse, validate, and route to repository

1. Parse the user input to extract `job_name`, `table_name`, `repo`, `skills`, `date_window`.
2. Defaults: `skills = ["resolver","lineage","sql_opt","dagster","montecarlo"]`, `date_window = "last_30_days"`, `repo = "auto"`.
3. Validate `skills` values against the allowed list; warn and ignore unknown values.
4. **Validate `repo`**: if provided, must be one of `cmpgn`, `uma`, `rvnu`. If unknown, warn and set to `auto`.
5. Resolve `output_folder` from the repo alias:
   - `cmpgn` → `CMPGN`
   - `uma` → `UMA`
   - `rvnu` → `RVNU`
   - `auto` → will be determined by the job-resolver in Step 0
6. Print execution plan:
   ```
   ╔═══════════════════════════════════════════════════════════╗
   ║  MCP ORCHESTRATOR — Execution Plan (Multi-Repo)          ║
   ╠═══════════════════════════════════════════════════════════╣
   ║  Input        : <job_name or table: value>               ║
   ║  Repository   : <repo alias or AUTO-DETECT>              ║
   ║  Skills       : <list>                                   ║
   ║  Date window  : <date_window>                            ║
   ║  Source       : GitHub (YOUR-ORG / <repo>)               ║
   ║  Output       : OUTPUT_ROOT\<OUTPUT_FOLDER>\<job>\       ║
   ║                 REPORT\<job>_mcp_report.html             ║
   ╚═══════════════════════════════════════════════════════════╝
   ```

---

### Phase 2 — Step 0: Job Resolution (always runs)

Follow all instructions in `.github/skills/job-resolver/SKILL.md`.

Supply:
- `job_name` if provided by user, otherwise `table_name`.
- `repo` alias if the user provided one (pass `"auto"` when not provided).

The job-resolver will read job folders and JSON configs **directly from GitHub** using
the GitHub MCP server — no local filesystem access to the source repo is required.

On success: store the returned **JOB CONTEXT** block (which now includes `github_org`,
`github_repo`, `github_branch`, `output_folder`) for use in all subsequent steps.
On failure: stop and report the error. Do not proceed to further steps.

---

### Phase 3 — Step 1: ETL Lineage (runs if `lineage` in skills)

Follow all instructions in `.github/skills/etl-lineage-composer/SKILL.md`.

Supply:
- `job_context`: the context block from Step 0.

On completion: note the lineage HTML path for inclusion in the final report.
On failure: log the error, mark the lineage section as "Generation failed", continue.

---

### Phase 4 — Step 2: SQL Optimization (runs if `sql_opt` in skills)

Follow the **single-job mode** instructions in `.github/skills/cmpgn-sql-optimization/SKILL.md`.

Supply:
- `job_context`: full context block from Step 0 (includes `github_org`, `github_repo`,
  `github_branch`, `output_folder`, `job_name`, `sql_files`).

The skill reads SQL files directly from GitHub and writes optimized files locally to:
`WORKSPACE_ROOT\<output_folder>\<job_name>\DQ\*_optimized.sql`

On completion: note the list of optimized files for inclusion in the final report.
On failure: log the error, mark the SQL section as "Generation failed", continue.

---

### Phase 5 — Step 3: Dagster Ops Intelligence (runs if `dagster` in skills)

Follow all instructions in `.github/skills/dagster-ops-intelligence/SKILL.md`.

Supply:
- `job_context`: context from Step 0.
- `date_window`: from orchestrator input.

On completion: store the `dagster_intelligence_json` object and formatted text block.
On failure or unavailability: mark section as "Dagster data unavailable", continue.

---

### Phase 6 — Step 4: Monte Carlo DQ Advisor (runs if `montecarlo` in skills)

For **each target table** in `job_context.target_tables` (limit to first 5 tables
to avoid excessive API calls — note any skipped tables in the report):

Follow all instructions in `.github/skills/mc-table-alerts/SKILL.md`.

Supply:
- `table_name`: each target table from the job context.

Collect a Monte Carlo report section per table.

On failure for a specific table: mark that table's section as "Monte Carlo data
unavailable", continue to the next table.

---

### Phase 7 — Merge: Generate the Consolidated HTML Report

Build a **single self-contained HTML file** with the following 8 sections.
No external CDN dependencies — embed all CSS and JavaScript inline.

#### Report file path:
`OUTPUT_ROOT\<output_folder>\<job_name>\REPORT\<job_name>_mcp_report.html`

Where `<output_folder>` is `CMPGN`, `UMA`, or `RVNU` as resolved by the job-resolver.
`OUTPUT_ROOT = <OUTPUT_ROOT>` (parent of the source repo — artifacts live outside it).

Ensure the `REPORT\` subfolder exists (create with `create_directory` if needed).
Path examples:
- `<OUTPUT_ROOT>\CMPGN\cmpgn_prm_ml_wkly\REPORT\cmpgn_prm_ml_wkly_mcp_report.html`
- `<OUTPUT_ROOT>\UMA\unifd_mktg_anltcs_job\REPORT\unifd_mktg_anltcs_job_mcp_report.html`
- `<OUTPUT_ROOT>\RVNU\rvnu_mktg_job\REPORT\rvnu_mktg_job_mcp_report.html`

---

#### HTML Report Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCP Report: {JOB_NAME}</title>
<style>
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #64748b; --accent: #38bdf8;
    --green: #4ade80; --yellow: #fbbf24; --red: #f87171;
    --purple: #c084fc; --orange: #fb923c;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", Tahoma, sans-serif; background: var(--bg); color: var(--text); line-height: 1.55; }
  /* ── Top header ── */
  .top-header { background: linear-gradient(120deg, #0f3977, #0a66c2 55%, #00897b); padding: 20px 28px; }
  .top-header h1 { margin: 0 0 6px; font-size: 24px; color: #fff; }
  .top-header p { margin: 0; color: #cce8ff; font-size: 13px; }
  .top-meta { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
  .chip { padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; }
  .chip-blue   { background: #1d4ed8; color: #bfdbfe; }
  .chip-green  { background: #15803d; color: #bbf7d0; }
  .chip-yellow { background: #92400e; color: #fde68a; }
  .chip-purple { background: #6b21a8; color: #e9d5ff; }
  /* ── Nav sidebar ── */
  .layout { display: flex; min-height: 100vh; }
  .sidebar { width: 220px; min-width: 220px; background: var(--surface); border-right: 1px solid var(--border); padding: 16px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
  .sidebar a { display: block; padding: 8px 20px; color: var(--muted); text-decoration: none; font-size: 13px; border-left: 3px solid transparent; transition: all 0.15s; }
  .sidebar a:hover, .sidebar a.active { color: var(--accent); border-left-color: var(--accent); background: #1a3a5f22; }
  .sidebar .nav-label { padding: 16px 20px 6px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
  /* ── Main content ── */
  .main { flex: 1; padding: 24px 32px; max-width: 1100px; }
  .section { margin-bottom: 40px; scroll-margin-top: 20px; }
  .section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
  .section-header h2 { margin: 0; font-size: 18px; color: var(--text); }
  .section-number { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
  .sn-blue   { background: #1d4ed8; color: #bfdbfe; }
  .sn-green  { background: #15803d; color: #bbf7d0; }
  .sn-yellow { background: #92400e; color: #fde68a; }
  .sn-purple { background: #6b21a8; color: #e9d5ff; }
  .sn-red    { background: #991b1b; color: #fecaca; }
  .sn-cyan   { background: #0e7490; color: #cffafe; }
  .sn-gray   { background: #374151; color: #d1d5db; }
  /* ── Cards ── */
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
  .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; }
  .stat-card .stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-card .stat-value { font-size: 24px; font-weight: 700; color: var(--text); margin-top: 4px; }
  .stat-card .stat-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
  /* ── Tables ── */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #1a2740; padding: 9px 12px; text-align: left; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b66; color: #cbd5e1; }
  tr:hover td { background: #1e293b88; }
  /* ── Status badges ── */
  .status { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
  .status-success { background: #14532d; color: #86efac; }
  .status-failure { background: #7f1d1d; color: #fca5a5; }
  .status-running { background: #1e40af; color: #93c5fd; }
  .status-paused  { background: #78350f; color: #fcd34d; }
  .status-active  { background: #14532d; color: #86efac; }
  .status-warn    { background: #78350f; color: #fcd34d; }
  /* ── Inline frame for lineage ── */
  .lineage-frame { width: 100%; height: 420px; border: 1px solid var(--border); border-radius: 8px; }
  /* ── Code blocks ── */
  .code-block { background: #0d1117; border: 1px solid var(--border); border-radius: 7px; padding: 12px 16px; font-family: Consolas, Menlo, monospace; font-size: 12px; color: #c9d1d9; overflow-x: auto; white-space: pre; margin: 8px 0; }
  /* ── Pills ── */
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; margin: 2px; }
  .pill-sql  { background: #1d4ed822; border: 1px solid #3b82f666; color: #93c5fd; }
  .pill-tbl  { background: #0c4a6e22; border: 1px solid #38bdf866; color: #7dd3fc; }
  .pill-src  { background: #3b0764;   border: 1px solid #c084fc66; color: #e9d5ff; }
  /* ── Alert banner ── */
  .alert-banner { border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px; border-left: 4px solid; }
  .alert-info  { background: #1e3a5f33; border-color: #3b82f6; color: #93c5fd; }
  .alert-warn  { background: #78350f33; border-color: #f59e0b; color: #fde68a; }
  .alert-error { background: #7f1d1d33; border-color: #ef4444; color: #fca5a5; }
  .alert-ok    { background: #14532d33; border-color: #22c55e; color: #86efac; }
  /* ── Responsive ── */
  @media (max-width: 700px) { .sidebar { display: none; } .main { padding: 16px; } }
</style>
</head>
<body>

<!-- TOP HEADER -->
<div class="top-header">
  <h1>&#x1F9E0; MCP Intelligence Report: {JOB_NAME}</h1>
  <p>Local-first MCP orchestration report — ETL lineage, SQL optimization, Dagster ops, Monte Carlo DQ</p>
  <div class="top-meta">
    <span class="chip chip-blue">Generated: {TIMESTAMP}</span>
    <span class="chip chip-green">Job: {JOB_NAME}</span>
    <span class="chip chip-yellow">Skills: {SKILLS_RUN}</span>
    <span class="chip chip-purple">Window: {DATE_WINDOW}</span>
  </div>
</div>

<div class="layout">
<!-- SIDEBAR NAV -->
<nav class="sidebar">
  <div class="nav-label">Sections</div>
  <a href="#s1">1 · Execution Summary</a>
  <a href="#s2">2 · Job Resolution</a>
  <a href="#s3">3 · ETL Lineage</a>
  <a href="#s4">4 · SQL Optimization</a>
  <a href="#s5">5 · Dagster Ops</a>
  <a href="#s6">6 · Monte Carlo DQ</a>
  <a href="#s7">7 · Recommendations</a>
  <a href="#s8">8 · Appendix</a>
</nav>

<!-- MAIN CONTENT -->
<main class="main">

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 1: Execution Summary -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s1">
  <div class="section-header">
    <div class="section-number sn-blue">1</div>
    <h2>Execution Summary</h2>
  </div>
  <div class="card-grid">
    <div class="stat-card">
      <div class="stat-label">Job Name</div>
      <div class="stat-value" style="font-size:16px">{JOB_NAME}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Input Mode</div>
      <div class="stat-value" style="font-size:16px">{INPUT_MODE}</div>
      <div class="stat-sub">{INPUT_VALUE}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Skills Executed</div>
      <div class="stat-value" style="font-size:16px">{SKILL_COUNT}</div>
      <div class="stat-sub">{SKILLS_RUN}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Report Generated</div>
      <div class="stat-value" style="font-size:14px">{TIMESTAMP}</div>
    </div>
  </div>
  <div class="card" style="margin-top:12px;">
    <table>
      <thead><tr><th>Skill</th><th>Status</th><th>Output</th><th>Notes</th></tr></thead>
      <tbody>
        {SKILL_STATUS_ROWS}
      </tbody>
    </table>
  </div>
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 2: Job Resolution & Metadata -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s2">
  <div class="section-header">
    <div class="section-number sn-blue">2</div>
    <h2>Job Resolution &amp; Metadata</h2>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Job Name</td><td>{JOB_NAME}</td></tr>
        <tr><td>Repository</td><td><code>{GITHUB_REPO}</code> (<span class="chip chip-blue">{OUTPUT_FOLDER}</span>)</td></tr>
        <tr><td>GitHub Org / Branch</td><td>{GITHUB_ORG} / {GITHUB_BRANCH}</td></tr>
        <tr><td>GitHub Job Path</td><td><code>{JOB_FOLDER_PATH}</code></td></tr>
        <tr><td>JSON Config (GitHub)</td><td><code>{JSON_CONFIG_PATH}</code></td></tr>
        <tr><td>Local Output Root</td><td><code>WORKSPACE_ROOT\{OUTPUT_FOLDER}\{JOB_NAME}\</code></td></tr>
        <tr><td>Resolution Method</td><td>{RESOLUTION_METHOD}</td></tr>
        <tr><td>Confidence</td><td><span class="status {CONFIDENCE_CLASS}">{CONFIDENCE}</span></td></tr>
        <tr><td>SQL Files</td><td>{SQL_FILES_PILLS}</td></tr>
        <tr><td>Target Tables</td><td>{TARGET_TABLE_PILLS}</td></tr>
        <tr><td>Source Systems</td><td>{SOURCE_SYSTEM_PILLS}</td></tr>
        <tr><td>Notes</td><td>{RESOLUTION_NOTES}</td></tr>
      </tbody>
    </table>
  </div>
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 3: ETL Lineage & Flow -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s3">
  <div class="section-header">
    <div class="section-number sn-green">3</div>
    <h2>ETL Lineage &amp; Task Flow</h2>
  </div>
  {LINEAGE_CONTENT}
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 4: SQL Optimization Results -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s4">
  <div class="section-header">
    <div class="section-number sn-yellow">4</div>
    <h2>SQL Optimization Results</h2>
  </div>
  {SQL_OPT_CONTENT}
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 5: Dagster Operational Intelligence -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s5">
  <div class="section-header">
    <div class="section-number sn-purple">5</div>
    <h2>Dagster Operational Intelligence</h2>
  </div>
  {DAGSTER_CONTENT}
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 6: Monte Carlo Data Quality -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s6">
  <div class="section-header">
    <div class="section-number sn-cyan">6</div>
    <h2>Monte Carlo Data Quality Intelligence</h2>
  </div>
  {MONTECARLO_CONTENT}
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 7: Consolidated Recommendations -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s7">
  <div class="section-header">
    <div class="section-number sn-red">7</div>
    <h2>Consolidated Recommendations</h2>
  </div>
  {RECOMMENDATIONS_CONTENT}
</section>

<!-- ──────────────────────────────────────────────── -->
<!-- SECTION 8: Appendix -->
<!-- ──────────────────────────────────────────────── -->
<section class="section" id="s8">
  <div class="section-header">
    <div class="section-number sn-gray">8</div>
    <h2>Appendix</h2>
  </div>
  {APPENDIX_CONTENT}
</section>

</main>
</div>

<script>
// Active nav highlight on scroll
const sections = document.querySelectorAll('.section');
const navLinks = document.querySelectorAll('.sidebar a');
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      navLinks.forEach(a => a.classList.remove('active'));
      const link = document.querySelector('.sidebar a[href="#' + e.target.id + '"]');
      if (link) link.classList.add('active');
    }
  });
}, { threshold: 0.3 });
sections.forEach(s => observer.observe(s));
</script>
</body>
</html>
```

---

### Content Generation Rules for Each Section

#### Section 3 — ETL Lineage Content (`{LINEAGE_CONTENT}`)

If `lineage` skill ran successfully:
- Embed the ETL lineage SVG diagram inline (read from `LINEAGE/<job_name>_etl_lineage.html` and extract the SVG + task tables).
- If the file is too large to embed fully, provide a link card:
  ```html
  <div class="alert-info alert-banner">
    &#x1F517; Full lineage document: <code>LINEAGE/{JOB_NAME}_etl_lineage.html</code>
  </div>
  ```
  followed by a summary table of tasks and SQL file references.

If skill was skipped:
```html
<div class="alert-warn alert-banner">Lineage skill was not included in this run.</div>
```

If skill failed:
```html
<div class="alert-error alert-banner">&#x26A0; Lineage generation failed: {ERROR_MESSAGE}</div>
```

---

#### Section 4 — SQL Optimization Content (`{SQL_OPT_CONTENT}`)

If `sql_opt` skill ran successfully:
- Show a summary table:

| SQL File | Optimized File | Optimizations Applied |
|----------|---------------|----------------------|
| `file.sql` | `DQ/file_optimized.sql` | CTE refactor, removed SELECT *, … |

- Extract and render the OPTIMIZATION SUMMARY header from each `*_optimized.sql` file
  (read the first 50 lines of each file to get the comment header block).
- Show the summary as a collapsible `<details>` block per file.

---

#### Section 5 — Dagster Content (`{DAGSTER_CONTENT}`)

If `dagster` skill produced data:
- Render stat cards: Total Runs, Success Rate, Avg Duration, Last Run Status
- Render run history table (last 20 runs): datetime, status badge, duration
- Render schedule info card: name, cron, status, next run
- Render asset dependency lists (upstream / downstream)
- Render alert banner if any missed ticks or failures detected

---

#### Section 6 — Monte Carlo Content (`{MONTECARLO_CONTENT}`)

For each target table processed:
- Render a sub-card with table identity, monitor count, incident count
- Render monitors table: name, type, status badge
- Render active incidents table (if any): severity badge, start time, status
- Summary blurb (the plain-English paragraph from `mc-table-alerts`)

---

#### Section 7 — Recommendations (`{RECOMMENDATIONS_CONTENT}`)

Synthesize actionable recommendations from all skills in a **priority-ordered list**:

Priority levels:
- 🔴 **Critical** — open incidents, failed runs, PAUSED monitors with no backup
- 🟡 **High** — optimization opportunities, frequent failures, missing monitors
- 🟢 **Medium** — schedule improvements, SQL refactoring suggestions
- ⚪ **Low** — informational, cosmetic, or low-risk improvements

Render as a table:

| Priority | Area | Recommendation | Source Skill |
|----------|------|---------------|-------------|
| 🔴 Critical | Monte Carlo | 2 monitors are PAUSED — reactivate to restore coverage | montecarlo |
| 🟡 High | SQL | Replace `SELECT *` in 3 files with explicit column lists | sql_opt |
| … | … | … | … |

---

#### Section 8 — Appendix (`{APPENDIX_CONTENT}`)

Include:
- Raw job context block (formatted `<code>` block)
- List of all files referenced (SQL source files, optimized files, lineage HTML)
- List of all Snowflake tables identified
- Any unresolved items or partial-failure notes
- Skill execution timestamps

---

### Step 7 — Save the consolidated report

1. Ensure `OUTPUT_ROOT\<output_folder>\<job_name>\REPORT\` exists (create with `create_directory` if needed).
2. Write the HTML to `OUTPUT_ROOT\<output_folder>\<job_name>\REPORT\<job_name>_mcp_report.html`.
   (`OUTPUT_ROOT = <OUTPUT_ROOT>` — outside the source repo)
3. Print final completion banner:

```
╔══════════════════════════════════════════════════════════════════════╗
║  ✅ MCP ORCHESTRATOR COMPLETE (Multi-Repo)                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Job           : <job_name>                                         ║
║  Repository    : YOUR-ORG / <github_repo> (branch: prod)           ║
║  Output folder : OUTPUT_ROOT\<output_folder>  (CMPGN | UMA | RVNU) ║
║  Skills run    : <list>                                             ║
║  Artifacts (OUTPUT_ROOT\<output_folder>\<job>\):                   ║
║    • LINEAGE\<job>_etl_lineage.html                                ║
║    • DQ\*_optimized.sql                                            ║
║    • REPORT\<job>_mcp_report.html                                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Error Handling Summary

| Situation | Behavior |
|-----------|----------|
| Job resolution fails (Step 0) | Stop immediately; report error with suggestions |
| `repo` alias unrecognised | Warn user, set to `auto` and search all 3 repos |
| Job not found in any repo | List the 3 repos searched and suggest checking job name spelling |
| Individual skill fails | Log error in skill status table; continue to next skill; mark section as failed in report |
| No target tables found | Skip Monte Carlo step; add warning in Section 6 |
| Dagster job not found | Mark Section 5 as "Unavailable"; continue |
| GitHub MCP call fails | Retry once; if still fails log error and skip that skill step |
| REPORT folder creation fails | Try writing to `OUTPUT_ROOT\<output_folder>\` directly |
| All skills skipped (empty `skills` list) | Warn user: "No skills selected. At minimum provide skills=[resolver]" |
