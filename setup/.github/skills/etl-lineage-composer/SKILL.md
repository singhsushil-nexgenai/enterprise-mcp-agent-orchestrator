---
name: etl-lineage-composer
description: >
  Given a resolved job context (from the job-resolver skill), reads the job's JSON
  config directly from GitHub via the GitHub MCP server, extracts the complete task
  execution DAG, SQL file references, source systems, and target Snowflake tables.
  Generates a self-contained HTML lineage document saved locally under
  WORKSPACE_ROOT\<OUTPUT_FOLDER>\<job_name>\LINEAGE\<job_name>_etl_lineage.html.
  OUTPUT_FOLDER is CMPGN, UMA, or RVNU as resolved by the job-resolver.
  Use this skill when asked to trace ETL flow, visualize task dependencies, or
  produce a source-to-target lineage map for any CMPGN, UMA, or RVNU job.
---

## Purpose

Parse the job JSON config to build a complete **source-to-target ETL lineage graph**:
- Task execution DAG (nodes = tasks, edges = `next` relationships)
- SQL files per task
- External source systems (Vertica, S3, API, Snowflake)
- Snowflake target tables
- Data quality audit checkpoints

Produce a **self-contained HTML lineage document** with no external CDN dependencies.

---

## Inputs

| Parameter         | Description |
|-------------------|-------------|
| `job_context`     | The context block from `job-resolver`. Must include `job_name`, `github_org`, `github_repo`, `github_branch`, `json_config_path`, `output_folder`, `local_output_root`. |
| `output_path`     | *(Optional)* Override local save path. Default: `<local_output_root>\LINEAGE\<job_name>_etl_lineage.html` |

---

## Workspace Constants

| Constant         | Value |
|------------------|-------|
| `WORKSPACE_ROOT` | `<OUTPUT_ROOT>\etl-campaign-analytics` (source repo — skills & configs) |
| `OUTPUT_ROOT`    | `<OUTPUT_ROOT>` (parent folder — artifacts written here, outside the repo) |
| `LOCAL_OUTPUT`   | `OUTPUT_ROOT\<output_folder>\<job_name>\LINEAGE\` |

---

## Step-by-Step Instructions

### Step 1 — Read and parse the JSON config

Read the JSON config **directly from GitHub** using the GitHub MCP server:

```
get_file_contents(
  owner = job_context.github_org,       // "YOUR-ORG"
  repo  = job_context.github_repo,
  path  = job_context.json_config_path,  // e.g. "cmpgn_prm_ml_wkly/cmpgn_prm_ml_wkly.json"
  ref   = job_context.github_branch      // "prod"
)
```

Decode the base64 content returned by the GitHub API.

Extract the following top-level fields:
| Field | JSON key |
|-------|----------|
| App ID | `appid` |
| Source ID | `srcid` |
| Entry task | `startat` |
| Snowflake DB | `snowflake_database` |
| Snowflake Schema | `snowflake_schema` |
| Snowflake Warehouse | `snowflake_warehouse` |
| Vertica host | `vertica_hostname` (if present) |

---

### Step 2 — Build the task graph

Iterate over all keys in `tasks` object. For each task `<task_name>`:

**Node attributes:**
| Attribute | Source |
|-----------|--------|
| `id` | task key name |
| `label` | task key name (use friendly version: replace `_` with space, title case) |
| `type` | Classify using rules below |
| `next` | `tasks.<task_name>.next` array (outgoing edges) |
| `sql_files` | Basenames from `sources[*].sqlFileAbsolutePath` (strip path prefix) |
| `tmp_views` | `sources[*].tmp_view` values |
| `targets` | `targets[*]` → `<db>.<schema>.<table>` strings |
| `has_api` | `true` if `apis` key is present |
| `has_audit` | `true` if `audits` key is present |
| `has_surrogate_key` | `true` if `surrogate_key_list` key is present |

**Task type classification rules** (apply first match):
| Type | Condition |
|------|-----------|
| `SOURCE_EXTRACT` | task name contains `reader` OR `extract` OR entry task == this task AND `sources` references external SQL |
| `API_READER` | `apis` key present |
| `S3_READER` | `sources[*].s3_source_path` present |
| `TRUNCATE` | task name contains `truncate` OR SQL file name contains `truncate` |
| `TRANSFORM` | `transformations` key present OR `sources[*].sqlFileAbsolutePath` present AND `targets` absent |
| `SURROGATE_KEY` | `surrogate_key_list` key present |
| `LOAD_TARGET` | `targets` key present |
| `DATA_QUALITY` | `audits` key present |
| `CHECKPOINT` | task name contains `checkpoint` OR `updatecheckpoint` |
| `END` | task name equals `endstate` OR `end` OR `next` is empty/null |
| `GENERIC` | none of the above |

**Edge list:** For each task `T` and each entry in `T.next`, create edge `T → next_task`.

---

### Step 3 — Identify source and target nodes

**Source nodes** (nodes with no incoming edges in the task graph) represent the
entry points. Additionally, create virtual external-system nodes:
- If `vertica_hostname` present → add node `VERTICA_SOURCE` (type `EXTERNAL_SOURCE`)
- If any `s3_source_path` found → add node `S3_SOURCE` (type `EXTERNAL_SOURCE`)
- If any `apis` found → add node `API_SOURCE` (type `EXTERNAL_SOURCE`)
- Connect each external source node to the first task that consumes it.

**Target nodes**: For each unique `<db>.<schema>.<table>` collected across all tasks,
create a virtual target node `SNOWFLAKE:<table>` (type `SNOWFLAKE_TARGET`).
Connect each `LOAD_TARGET` task to its corresponding target nodes.

---

### Step 4 — Compute graph layout positions

Use a **left-to-right layered layout** (Sugiyama-style simplified):

1. Assign layers:
   - Layer 0: External source nodes
   - Layer 1: Entry task (value of `startat`)
   - Layer N+1: All tasks reachable only from layer N tasks
   - Last layer: Snowflake target nodes

2. Within each layer, distribute nodes vertically with 80px spacing.
3. Node width = 160px, height = 50px.
4. Layer horizontal spacing = 220px.
5. Start x = 60px, start y = 40px.

Assign `x, y` coordinates to each node.

---

### Step 5 — Generate the HTML lineage document

Build a self-contained HTML file. Embed all CSS and JavaScript inline.

#### Document structure:

```
1. Header bar  — job name, generation date, counts
2. Metadata card — app ID, DB, schema, warehouse, source systems
3. SVG task flow diagram
4. SQL File Reference table
5. Source-to-Target mapping table
6. DQ Audit summary (if audits present)
```

#### Color scheme by node type:

| Type | Fill | Stroke |
|------|------|--------|
| `EXTERNAL_SOURCE` | `#1e3a5f` | `#3b82f6` |
| `SOURCE_EXTRACT` | `#1a3a5f` | `#60a5fa` |
| `API_READER` | `#312e81` | `#818cf8` |
| `S3_READER` | `#1e3a5f` | `#38bdf8` |
| `TRUNCATE` | `#3f1515` | `#f87171` |
| `TRANSFORM` | `#14532d` | `#4ade80` |
| `SURROGATE_KEY` | `#3b2a00` | `#fbbf24` |
| `LOAD_TARGET` | `#065f46` | `#34d399` |
| `DATA_QUALITY` | `#3b0764` | `#c084fc` |
| `CHECKPOINT` | `#422006` | `#fb923c` |
| `END` | `#1f2937` | `#6b7280` |
| `SNOWFLAKE_TARGET` | `#0c4a6e` | `#38bdf8` |
| `GENERIC` | `#1e293b` | `#94a3b8` |

#### SVG Rendering template:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ETL Lineage: {JOB_NAME}</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", sans-serif; background: #0f172a; color: #e2e8f0; }
  #header { padding: 14px 24px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
  #header h1 { margin: 0; font-size: 20px; color: #f1f5f9; }
  .ts { color: #64748b; font-size: 11px; }
  .badge { padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; }
  .badge-blue  { background: #1d4ed8; color: #bfdbfe; }
  .badge-green { background: #15803d; color: #bbf7d0; }
  .badge-purple{ background: #6b21a8; color: #e9d5ff; }
  #meta { display: flex; gap: 10px; flex-wrap: wrap; padding: 10px 24px; background: #1e293b; border-bottom: 1px solid #334155; font-size: 12px; color: #94a3b8; }
  .meta-item strong { color: #cbd5e1; margin-right: 4px; }
  #diagram-wrap { width: 100%; overflow-x: auto; background: #0f172a; padding: 16px; }
  svg .node-rect { rx: 7; stroke-width: 2; cursor: pointer; transition: opacity 0.15s; }
  svg .node-rect:hover { opacity: 0.8; }
  svg .node-label { font-size: 10px; fill: #f1f5f9; pointer-events: none; font-family: "Segoe UI", sans-serif; }
  svg .edge-line { fill: none; stroke: #475569; stroke-width: 1.5; marker-end: url(#arr); }
  svg .edge-label { font-size: 9px; fill: #64748b; }
  #tooltip { position: fixed; background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 10px 14px; font-size: 12px; max-width: 300px; pointer-events: none; display: none; z-index: 200; line-height: 1.6; }
  #tooltip .tkey { color: #94a3b8; font-size: 11px; }
  #tooltip .tval { color: #e2e8f0; }
  .section { padding: 16px 24px; }
  .section h2 { font-size: 15px; color: #94a3b8; margin: 0 0 10px; text-transform: uppercase; letter-spacing: 0.05em; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { background: #1e293b; padding: 8px 12px; text-align: left; color: #64748b; font-weight: 600; border-bottom: 1px solid #334155; }
  td { padding: 7px 12px; border-bottom: 1px solid #1e293b44; color: #cbd5e1; }
  tr:hover td { background: #1e293b66; }
  .pill { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; margin: 1px; }
  .pill-sql  { background: #1d4ed822; border: 1px solid #3b82f666; color: #93c5fd; }
  .pill-view { background: #15803d22; border: 1px solid #22c55e66; color: #86efac; }
  .pill-tbl  { background: #0c4a6e22; border: 1px solid #38bdf866; color: #7dd3fc; }
</style>
</head>
<body>
<div id="header">
  <h1>&#x2194; ETL Lineage: {JOB_NAME}</h1>
  <span class="ts">Generated: {TIMESTAMP}</span>
  <span class="badge badge-blue">Tasks: {N_TASKS}</span>
  <span class="badge badge-green">SQL Files: {N_SQL}</span>
  <span class="badge badge-purple">Targets: {N_TARGETS}</span>
</div>
<div id="meta">
  <span class="meta-item"><strong>App ID:</strong>{APP_ID}</span>
  <span class="meta-item"><strong>Database:</strong>{SNOWFLAKE_DB}</span>
  <span class="meta-item"><strong>Schema:</strong>{SNOWFLAKE_SCHEMA}</span>
  <span class="meta-item"><strong>Warehouse:</strong>{WAREHOUSE}</span>
  <span class="meta-item"><strong>Sources:</strong>{SOURCE_SYSTEMS}</span>
  <span class="meta-item"><strong>Entry Task:</strong>{STARTAT}</span>
</div>
<div id="diagram-wrap">
  <svg id="graph" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#475569"/>
      </marker>
    </defs>
    {SVG_EDGES}
    {SVG_NODES}
  </svg>
</div>
<div id="tooltip"></div>
<div class="section">
  <h2>SQL File References</h2>
  <table>
    <thead><tr><th>Task</th><th>Task Type</th><th>SQL Files</th><th>Temp Views</th></tr></thead>
    <tbody>{SQL_TABLE_ROWS}</tbody>
  </table>
</div>
<div class="section">
  <h2>Source → Target Mapping</h2>
  <table>
    <thead><tr><th>Source System</th><th>Load Task</th><th>Target Table</th><th>Load Type</th></tr></thead>
    <tbody>{STT_TABLE_ROWS}</tbody>
  </table>
</div>
{DQ_SECTION}
<script>
const nodes = {NODES_JSON};
const tooltip = document.getElementById('tooltip');
nodes.forEach(n => {
  const el = document.getElementById('node-' + n.id);
  if (!el) return;
  el.addEventListener('mouseenter', e => {
    tooltip.style.display = 'block';
    tooltip.innerHTML = '<div class="tkey">Task</div><div class="tval">' + n.id + '</div>' +
      '<div class="tkey">Type</div><div class="tval">' + n.type + '</div>' +
      (n.sql_files.length ? '<div class="tkey">SQL Files</div><div class="tval">' + n.sql_files.join(', ') + '</div>' : '') +
      (n.targets.length ? '<div class="tkey">Targets</div><div class="tval">' + n.targets.join('<br>') + '</div>' : '');
  });
  el.addEventListener('mousemove', e => {
    tooltip.style.left = (e.clientX + 14) + 'px';
    tooltip.style.top = (e.clientY - 10) + 'px';
  });
  el.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
});
</script>
</body>
</html>
```

#### SVG node template (per task node):
```svg
<g id="node-{ID}" class="node-group" transform="translate({X},{Y})">
  <rect class="node-rect" width="160" height="50" fill="{FILL}" stroke="{STROKE}" rx="7"/>
  <text class="node-label" x="80" y="20" text-anchor="middle" font-weight="600">{LINE1}</text>
  <text class="node-label" x="80" y="36" text-anchor="middle" fill="#94a3b8">{TYPE_LABEL}</text>
</g>
```

#### SVG edge template (per directed edge):
Use a cubic bezier path from the right-center of the source node to the left-center
of the target node:
```
M {src_x + 160},{src_y + 25} C {mid_x},{src_y + 25} {mid_x},{tgt_y + 25} {tgt_x},{tgt_y + 25}
```
where `mid_x = (src_x + 160 + tgt_x) / 2`.

---

### Step 6 — Ensure output folder exists and save the file

1. Build the local output path from the job context:
   ```
   local_lineage_dir = job_context.local_output_root + "\LINEAGE"
   output_file       = local_lineage_dir + "\" + job_name + "_etl_lineage.html"
   ```
   `local_output_root` is from the job-resolver context, e.g.:
   `<OUTPUT_ROOT>\CMPGN\cmpgn_prm_ml_wkly`
   → output: `<OUTPUT_ROOT>\CMPGN\cmpgn_prm_ml_wkly\LINEAGE\cmpgn_prm_ml_wkly_etl_lineage.html`

2. Create `local_lineage_dir` with `create_directory` (it will create all parent folders).
3. Use `create_file` to write the complete HTML to `output_file`.
4. Report:
   ```
   ✅ ETL Lineage document written:
      <output_file>
      Repository : YOUR-ORG/<github_repo> (branch: prod)
      Tasks: <N> | SQL files: <M> | Target tables: <K>
   ```

---

## Data Quality Section Template

If any `DATA_QUALITY` tasks were found, append this section after the Source→Target table:

```html
<div class="section">
  <h2>Data Quality Audit Checkpoints</h2>
  <table>
    <thead><tr><th>Task</th><th>View Audited</th><th>Checks Applied</th><th>Key Columns</th></tr></thead>
    <tbody>
      <!-- one row per audit config -->
      <tr>
        <td>{TASK_NAME}</td>
        <td><span class="pill pill-view">{SRC_TMP_VIEW}</span></td>
        <td>{CHECK_TYPES}</td>
        <td>{COLUMN_LIST}</td>
      </tr>
    </tbody>
  </table>
</div>
```

Check types to list (comma-separated, based on which keys are present in the audit config):
`null_check`, `blank_check`, `duplicate_check`, `custom_check`

---

## Error Handling

| Situation | Action |
|-----------|--------|
| `json_config_path` is null | Build partial lineage from SQL file names only; note in report header |
| Task references SQL file not found on disk | Note mismatch in report; render node with warning icon |
| Circular dependency in task graph | Break cycle at the repeated edge; add a note in the header |
| LINEAGE folder creation fails | Try writing to `<job_folder_path>` directly with `_etl_lineage.html` suffix |
