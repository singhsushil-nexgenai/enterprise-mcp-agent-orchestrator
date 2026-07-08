---
name: dagster-ops-intelligence
description: >
  Given a resolved job context (from the job-resolver skill), queries the Dagster
  MCP server to produce a full operational intelligence report for the job:
  schedule configuration, recent run history (last 20 runs), average/min/max
  runtime, success/failure rates, upstream and downstream job dependencies, and
  active run alerts. Outputs a structured Markdown section consumed by the
  mcp-orchestrator for inclusion in the consolidated HTML report.
  Use this skill when asked about Dagster schedule, run history, SLA, or pipeline
  operational health for a CMPGN job.
---

## Purpose

Retrieve live operational data for a CMPGN job from the Dagster MCP server and
produce a structured intelligence report covering:

- **Schedule** — cron expression, next scheduled run, schedule state (RUNNING / STOPPED)
- **Run History** — last 20 runs with status, start time, end time, duration
- **Run Statistics** — avg / min / max duration, success rate, failure rate
- **Asset Dependencies** — upstream and downstream Dagster assets
- **Sensor / Freshness alerts** — any active freshness or schedule missed alerts

---

## Inputs

| Parameter     | Description |
|---------------|-------------|
| `job_context` | Context block from `job-resolver`. Must include `job_name`. |
| `date_window` | *(Optional)* Time window for run history. Default: `last_30_days`. Format: `last_N_days` (e.g. `last_90_days`). |

---

## Step-by-Step Instructions

### Step 1 — Locate the Dagster job

Call **`dagster_list_jobs`** with the `job_name` from context:

```
dagster_list_jobs({ "search": "<job_name>" })
```

- If the result contains an exact match: use that job name as the canonical Dagster job identifier.
- If no exact match: try a partial match (first result containing `job_name` as substring).
- If no match at all: report
  ```
  ⚠️  Job "<job_name>" not found in Dagster. Dagster intelligence section unavailable.
  ```
  and return an empty intelligence block (do not fail the orchestrator).

---

### Step 2 — Get job assets

Call **`dagster_get_job_assets`** with the confirmed job name:

```
dagster_get_job_assets({ "job_name": "<dagster_job_name>" })
```

Extract:
- List of asset keys belonging to this job (the **job asset set**)
- For each asset: `key`, `group`, `compute_kind`, `description`

---

### Step 3 — Get upstream and downstream dependencies

For each asset in the job asset set, call **`dagster_get_asset_deps`** to get
its immediate dependencies (depth = 1):

```
dagster_get_asset_deps({ "asset_key": "<asset_key>", "depth": 1 })
```

Aggregate results:
- **Upstream assets**: all `upstream` keys NOT in the job asset set → these are source dependencies
- **Downstream assets**: all `downstream` keys NOT in the job asset set → these are consumer jobs/tables

Limit API calls: if the job has more than 10 assets, sample the first 5 and last 5
by alphabetical order to avoid excessive calls.

---

### Step 4 — Get schedule information

Call **`dagster_run_graphql`** with the following query to retrieve the schedule
associated with this job:

```graphql
{
  schedulesOrError(repositorySelector: {repositoryName: "__repository__", repositoryLocationName: "__repository__"}) {
    ... on Schedules {
      results {
        name
        cronSchedule
        scheduleState { status }
        nextTick { timestamp }
        pipelineName
      }
    }
  }
}
```

Filter results where `pipelineName` equals the Dagster job name (case-insensitive).

If the above query fails (e.g. repository selector issues), retry with a simpler
query:
```graphql
{ schedulesOrError { ... on Schedules { results { name cronSchedule scheduleState { status } pipelineName nextTick { timestamp } } } } }
```

Extract:
- `schedule_name`: name of the schedule
- `cron_schedule`: cron expression (e.g. `0 6 * * *`)
- `schedule_status`: `RUNNING` or `STOPPED`
- `next_tick_ts`: Unix timestamp of next scheduled run; convert to human-readable UTC datetime

If no matching schedule is found, note: `No schedule configured for this job.`

---

### Step 5 — Get recent run history

Call **`dagster_run_graphql`** with the following query:

```graphql
{
  runsOrError(
    filter: { pipelineName: "<dagster_job_name>", statuses: [SUCCESS, FAILURE, CANCELED, STARTED] }
    limit: 20
  ) {
    ... on Runs {
      results {
        runId
        status
        startTime
        endTime
        tags { key value }
      }
    }
  }
}
```

For each run, compute:
- `duration_seconds = endTime - startTime` (null if still running)
- `duration_hms`: formatted as `HH:MM:SS`
- `start_datetime`: UTC datetime from `startTime` Unix timestamp
- `end_datetime`: UTC datetime from `endTime` Unix timestamp

Apply the `date_window` filter client-side:
- Parse `date_window` as `last_N_days` → cutoff = today minus N days
- Exclude runs where `startTime` is before the cutoff

---

### Step 6 — Compute run statistics

From the filtered run list, compute:

| Metric | Calculation |
|--------|-------------|
| Total runs | count of runs in window |
| Successful runs | count where `status = SUCCESS` |
| Failed runs | count where `status = FAILURE` |
| Canceled runs | count where `status = CANCELED` |
| Success rate | `(successful / total) * 100` rounded to 1 decimal |
| Avg duration | mean of `duration_seconds` for completed runs (SUCCESS + FAILURE) |
| Min duration | min of `duration_seconds` for completed runs |
| Max duration | max of `duration_seconds` for completed runs |
| Last run status | status of the most recent run |
| Last run time | start datetime of the most recent run |

Format durations as `HH:MM:SS`.

---

### Step 7 — Check for active alerts / missed runs

Call **`dagster_run_graphql`** with the following query to check for any active
instigations with errors or missed ticks:

```graphql
{
  instigationStatesOrError {
    ... on InstigationStates {
      results {
        name
        instigationType
        status
        ticks(limit: 3) {
          status
          timestamp
          error { message }
        }
      }
    }
  }
}
```

Filter to entries where `name` matches the schedule/sensor for this job.
Flag any tick where `status = FAILURE` or `status = SKIPPED` within the last 3 ticks.

---

### Step 8 — Compose the intelligence report

Output a structured block for the orchestrator to embed in the HTML report:

```
DAGSTER OPERATIONAL INTELLIGENCE
═══════════════════════════════════════════════════════════════
Job Name         : <dagster_job_name>
Assets in Job    : <N> assets
─────────────────────────────────────────────────────────────
SCHEDULE
  Name           : <schedule_name>
  Cron           : <cron_expression>  (<human-readable: e.g. "Daily at 06:00 UTC">)
  Status         : <RUNNING | STOPPED>
  Next Run       : <next_tick_datetime>
─────────────────────────────────────────────────────────────
RUN STATISTICS  (window: <date_window>)
  Total Runs     : <N>
  Successful     : <N> (<success_rate>%)
  Failed         : <N>
  Canceled       : <N>
  Avg Duration   : <HH:MM:SS>
  Min Duration   : <HH:MM:SS>
  Max Duration   : <HH:MM:SS>
  Last Run       : <datetime> — <status>
─────────────────────────────────────────────────────────────
RECENT RUNS (last <N> in window)
  <ISO_DATETIME>  <STATUS padded>  <HH:MM:SS>
  ...
─────────────────────────────────────────────────────────────
ASSET DEPENDENCIES
  Upstream  : <list of upstream asset keys (cross-job sources)>
  Downstream: <list of downstream asset keys (consumers)>
─────────────────────────────────────────────────────────────
ALERTS / MISSED RUNS
  <alert entries or "No active alerts detected.">
═══════════════════════════════════════════════════════════════
```

Also produce a **machine-readable JSON object** `dagster_intelligence_json` for
the orchestrator to embed in the HTML report:

```json
{
  "job_name": "<>",
  "schedule": { "name": "<>", "cron": "<>", "status": "<>", "next_run": "<>" },
  "stats": { "total": 0, "success": 0, "failed": 0, "canceled": 0, "success_rate": 0.0, "avg_duration_s": 0, "min_duration_s": 0, "max_duration_s": 0 },
  "recent_runs": [ { "run_id": "<>", "status": "<>", "start": "<>", "end": "<>", "duration_s": 0 } ],
  "upstream_assets": [],
  "downstream_assets": [],
  "alerts": []
}
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Job not found in Dagster | Return empty block with warning; do not block orchestrator |
| GraphQL query fails | Retry once with simplified query; if still failing, mark section as "unavailable" |
| No runs in date window | Report "No runs found in the last N days"; show stats as zeros |
| Schedule query returns no match | Note "No schedule found"; continue with run history |
| `endTime` null for a run | Mark as "In Progress"; exclude from duration stats |
