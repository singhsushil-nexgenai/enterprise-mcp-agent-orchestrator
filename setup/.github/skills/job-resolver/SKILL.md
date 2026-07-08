---
name: job-resolver
description: >
  Given a job_name OR a table_name (plus an optional repo alias), resolves the
  canonical execution context for the MCP orchestrator by reading directly from
  GitHub via the GitHub MCP server — no local clone of the source repos is required.
  Searches across three YOUR-ORG repositories (CMPGN, UMA, RVNU) and returns a
  full job context including GitHub coordinates, output folder mapping, SQL file
  list, and target Snowflake table list. Produces a structured context object
  consumed by all downstream skills.
---

## Purpose

Produce a **canonical job context** from a single user input — either a job folder
name or a target Snowflake table name — so every downstream skill works from the
same resolved ground truth.

---

## Inputs

| Parameter    | Type   | Required    | Description |
|--------------|--------|-------------|-------------|
| `job_name`   | string | Conditional | Job folder name, e.g. `cmpgn_prm_ml_wkly`. Exact match preferred; case-insensitive fallback attempted. |
| `table_name` | string | Conditional | Snowflake table name (full or partial), e.g. `CMPGN.TGT.CMPGN_PROMO_ML_HIST`. Used when `job_name` is not provided. |
| `repo`       | string | No          | Repository alias: `cmpgn`, `uma`, or `rvnu`. When omitted, all three repos are searched. |

At least one of `job_name` or `table_name` must be supplied.

---

## Repository Registry

| Alias  | GitHub Org | GitHub Repo                                    | Branch | Output Folder | Excluded Folders |
|--------|------------|------------------------------------------------|--------|---------------|------------------|
| `cmpgn`| `YOUR-ORG` | `etl-campaign-analytics`                   | `prod` | `CMPGN`       | `.github`, `.git`, `deploy_list` |
| `uma`  | `YOUR-ORG` | `etl-unified-marketing`     | `prod` | `UMA`         | `.github`, `.git`, `deploy_list` |
| `rvnu` | `YOUR-ORG` | `etl-revenue-analytics`         | `prod` | `RVNU`        | `.github`, `.git`, `deploy_list` |

**Local output root** (where all artifacts are written — **outside** the source repo):
`<OUTPUT_ROOT>\<OUTPUT_FOLDER>\<job_name>\`

**JSON config pattern** (within each repo): `<job_folder>/<job_folder>.json`

---

## Output Context Object

On success, produce a structured context block that subsequent skills consume:

```
JOB CONTEXT
═══════════════════════════════════════════════════════════════
job_name          : <resolved job folder name>
github_org        : YOUR-ORG
github_repo       : <repo name, e.g. etl-campaign-analytics>
github_branch     : prod
repo_alias        : <cmpgn | uma | rvnu>
output_folder     : <CMPGN | UMA | RVNU>
job_folder_path   : <GitHub relative path, e.g. cmpgn_prm_ml_wkly>
json_config_path  : <GitHub relative path, e.g. cmpgn_prm_ml_wkly/cmpgn_prm_ml_wkly.json>
local_output_root : <OUTPUT_ROOT>\<OUTPUT_FOLDER>\<job_name>
sql_files         : [<list of SQL file basenames in job folder on GitHub>]
target_tables     : [<FULLY_QUALIFIED table names from JSON targets>]
source_systems    : [<unique source types: vertica | s3 | api | snowflake>]
startat_task      : <value of "startat" field in JSON>
resolution_method : job_name_direct | table_name_json_scan | table_name_sql_scan
confidence        : high | medium | low
resolution_notes  : <any caveats or fallback details>
═══════════════════════════════════════════════════════════════
```

---

## GitHub MCP Tool Reference

All GitHub access uses the **GitHub MCP server**. Use these tool calls:

| Operation | Tool call |
|-----------|-----------|
| List directory | `list_directory_contents(owner, repo, path, ref)` |
| Read a file | `get_file_contents(owner, repo, path, ref)` |
| Search code | `search_code(query)` — query format: `<term> repo:YOUR-ORG/<repo>` |

For all calls: `ref = "prod"`.

---

## Step-by-Step Instructions

### Step 1 — Determine which repos to search

If `repo` is provided and is one of `cmpgn`, `uma`, `rvnu`:
- Set `search_repos = [<that single Registry entry>]`.

If `repo` is `"auto"` or not provided:
- Set `search_repos = [cmpgn, uma, rvnu]` (all three Registry entries).

---

### Step 2A — Resolve by job_name (use when job_name is provided)

For each repo entry in `search_repos`:

1. Call **`list_directory_contents`** to get the root-level directory listing:
   ```
   list_directory_contents(
     owner = "YOUR-ORG",
     repo  = <github_repo>,
     path  = "",
     ref   = "prod"
   )
   ```

2. Filter to entries with `type = "dir"`. Exclude names starting with `.` or equal to
   `deploy_list`. This is the **master job list** for this repo.

3. Match `job_name` (case-insensitive) against the master job list.
   - **No match**: continue to next repo in `search_repos`.
   - **Match found**: record `(repo_entry, matched_folder_name)` and stop searching.

4. After all repos searched — if **no match found anywhere**, stop and report:
   ```
   ERROR: Job folder "<job_name>" not found in any searched repository:
     • YOUR-ORG/etl-campaign-analytics (CMPGN)
     • YOUR-ORG/etl-unified-marketing (UMA)
     • YOUR-ORG/etl-revenue-analytics (RVNU)
   Check the job name spelling or add repo=cmpgn|uma|rvnu to narrow the search.
   ```

5. Confirm the JSON config exists by calling `list_directory_contents` on the matched
   job folder and checking for `<job_name>.json` in the result.
   - If missing: set `json_config_path = null`, warn, continue with SQL-only context.

6. Set `resolution_method = job_name_direct`, `confidence = high`.
7. Proceed to **Step 3**.

---

### Step 2B — Resolve by table_name (use when only table_name is provided)

#### Phase 1: Normalize the table name

Extract the **bare table name** (last segment, uppercase):
- `CMPGN.TGT.CMPGN_PROMO_ML_HIST` → `CMPGN_PROMO_ML_HIST`
- `cmpgn_promo_ml_hist` → `CMPGN_PROMO_ML_HIST`

#### Phase 2: Scan JSON configs via GitHub

For each repo in `search_repos`:

1. Get the master job list via `list_directory_contents` (same as Step 2A items 1–2).

2. For each job folder, read its JSON config:
   ```
   get_file_contents(
     owner = "YOUR-ORG",
     repo  = <github_repo>,
     path  = "<job_folder>/<job_folder>.json",
     ref   = "prod"
   )
   ```
   Decode the base64 content. Search for the bare table name (case-insensitive
   substring match in `"snowflake_table"` values).
   If matched: add `(repo_entry, job_folder)` to the **candidate list**.

   > **Tip**: Scan CMPGN repo first; stop cross-repo scanning once a unique match
   > is confirmed.

3. After all repos scanned:
   - **One match**: set `resolution_method = table_name_json_scan`, `confidence = high`. Proceed to **Step 3**.
   - **Multiple matches**: list candidates with repo alias and ask user to confirm. Stop.
   - **Zero matches**: proceed to Phase 3 (SQL scan).

#### Phase 3: SQL text scan fallback via GitHub search

```
search_code(query = "<BARE_TABLE_NAME> repo:YOUR-ORG/<github_repo>")
```

Run for each repo in `search_repos`. Filter results to `.sql` files containing
INSERT INTO, MERGE INTO, or CREATE TABLE targeting the bare table name.

- One match → `resolution_method = table_name_sql_scan`, `confidence = medium`.
- Multiple → present candidates; ask user to confirm.
- None → `ERROR: No job found loading table "<table_name>" in any searched repo.`

---

### Step 3 — Hydrate the context from JSON config

```
get_file_contents(
  owner = "YOUR-ORG",
  repo  = <github_repo>,
  path  = "<job_folder>/<job_folder>.json",
  ref   = "prod"
)
```

Decode base64. Parse or text-scan to extract:

**Target tables** — all `tasks[*].targets[*]` entries:
```
<snowflake_database>.<snowflake_schema>.<snowflake_table>   (uppercase, de-duplicated)
```

**Source systems**:
- `sources[*].sqlFileAbsolutePath` present → `snowflake`
- `sources[*].s3_source_path` present → `s3`
- `apis[*]` key present → `api`
- Top-level `vertica_hostname` present → `vertica`

**SQL files** — unique basenames from `sources[*].sqlFileAbsolutePath`
(strip the `$CONFIG_PATH/…/<job_folder>/` prefix; keep `<filename>.sql` only).

**startat_task** — top-level `"startat"` field value.

---

### Step 4 — Confirm SQL files on GitHub

```
list_directory_contents(
  owner = "YOUR-ORG",
  repo  = <github_repo>,
  path  = "<job_folder>",
  ref   = "prod"
)
```

Cross-reference SQL basenames from Step 3 against the actual listing.
Note mismatches in `resolution_notes`.
Record the full list of `.sql` files found for use by downstream SQL skills.

---

### Step 5 — Emit the context block

Print the **JOB CONTEXT** block as defined in the Output Context Object section.

---

## Error Reference

| Situation | Action |
|-----------|--------|
| `job_name` not found in any repo | Stop; list repos searched; suggest checking spelling |
| `repo` alias is invalid | Warn; fall back to auto-detect (search all 3 repos) |
| GitHub MCP call fails | Retry once; if still fails, stop with GitHub API error details |
| JSON config missing for a known job | Continue with SQL-only context; warn |
| `table_name` matches zero jobs | Try SQL scan; if still zero, stop with clear error |
| `table_name` matches multiple jobs | List candidates with repo alias; ask user to confirm |
| JSON parse produces no targets | Set `target_tables = []`; note in `resolution_notes` |
