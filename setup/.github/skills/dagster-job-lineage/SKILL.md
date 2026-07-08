---
name: dagster-job-lineage
description: >
  Given a Dagster job name (e.g. cmpgn_api_dtl_stg_ddly), queries the Dagster MCP
  server to discover all software-defined assets in that job along with their full
  upstream (source) and downstream (target) lineage, then generates a self-contained
  HTML lineage document saved to the workspace. Use this skill whenever a user asks
  to "create a lineage document", "show lineage", "trace pipeline dependencies", or
  "visualize the DAG" for a Dagster job.
---

## Purpose

Discover all assets in a Dagster job, traverse the full lineage graph (predecessors → job assets → successors), and write a self-contained interactive HTML file that visualizes the lineage from source to target.

---

## Inputs

| Parameter | Description |
|-----------|-------------|
| `job_name` | Dagster job/pipeline name, e.g. `cmpgn_api_dtl_stg_ddly`. Case-insensitive match attempted if exact not found. |
| `output_path` | *(Optional)* Where to write the HTML file. Default: `<workspace_root>/<job_name>/LINEAGE/<job_name>_lineage.html` |

---

## Step-by-Step Instructions

### Step 1 — Get job assets and direct lineage

Call **`dagster_get_job_assets`** with the provided `job_name`:

```
dagster_get_job_assets({ "job_name": "<job_name>" })
```

- If the result contains `"error"`, the job was not found. Try calling **`dagster_list_jobs`** with `search: "<job_name>"` to find the closest match, then retry.
- Extract the `assets` list — each item has: `key`, `upstream` (list of asset keys), `downstream` (list of asset keys), `group`, `compute_kind`, `description`.
- Note the full set of asset keys that belong to the job (call this the **job asset set**).

---

### Step 2 — Expand lineage: resolve upstream sources

For any `upstream` key in Step 1 that is **not** already in the job asset set, call **`dagster_get_asset_deps`** to resolve its own upstream chain:

```
dagster_get_asset_deps({ "asset_key": "<upstream_key>", "depth": 2 })
```

- Collect all returned nodes into the lineage graph.
- Repeat for up to **2 hops** beyond the job boundary to find true source assets (tables/files with no further upstream).
- Stop expanding when a node has an empty `upstream` list — it is a **source node**.

Do **not** expand downstream beyond the job boundary — the job's own downstream is sufficient.

---

### Step 3 — Classify nodes

Label every node in the graph with a role:

| Role | Condition |
|------|-----------|
| **SOURCE** | No upstream dependencies (root of the graph) |
| **JOB_ASSET** | In the job asset set |
| **DOWNSTREAM** | Has the job asset as upstream, not in job set |
| **INTERMEDIATE** | Has upstream and downstream, not in job set |

---

### Step 4 — Build and write the HTML lineage document

Generate a **self-contained HTML file** with no external CDN dependencies. Embed all JavaScript inline.

#### 4a. Graph data structure

Build a JSON object `lineageData` with:
```json
{
  "job": "<job_name>",
  "nodes": [
    { "id": "<asset_key>", "label": "<short_label>", "role": "SOURCE|JOB_ASSET|DOWNSTREAM|INTERMEDIATE", "group": "<group_name>", "compute_kind": "<kind>", "description": "<desc>" }
  ],
  "edges": [
    { "from": "<upstream_key>", "to": "<downstream_key>" }
  ]
}
```

#### 4b. HTML structure

The HTML must include:
1. **Header bar** — job name, generation timestamp, asset counts by role
2. **Legend** — color-coded by role:
   - SOURCE → blue (`#3b82f6`)
   - JOB_ASSET → green (`#22c55e`)
   - DOWNSTREAM → orange (`#f97316`)
   - INTERMEDIATE → gray (`#6b7280`)
3. **Interactive SVG graph** — rendered using an embedded Dagre/D3-based layout algorithm (see template below)
4. **Asset table** below the graph — columns: Asset Key, Role, Group, Compute Kind, Upstream Count, Downstream Count

#### 4c. Graph rendering (embedded JS template)

Use the following self-contained approach — **no CDN required**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Lineage: {JOB_NAME}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
  #header { padding: 16px 24px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 16px; }
  #header h1 { margin: 0; font-size: 20px; color: #f1f5f9; }
  .badge { padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge-source { background: #1d4ed8; color: #bfdbfe; }
  .badge-job { background: #15803d; color: #bbf7d0; }
  .badge-down { background: #c2410c; color: #fed7aa; }
  .badge-inter { background: #374151; color: #d1d5db; }
  #legend { padding: 8px 24px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; gap: 12px; font-size: 12px; align-items: center; }
  #legend span { display: flex; align-items: center; gap: 4px; }
  .dot { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  #canvas-container { width: 100%; height: 60vh; overflow: auto; background: #0f172a; }
  svg { width: 100%; height: 100%; }
  .node rect { rx: 6; stroke-width: 2; cursor: pointer; }
  .node text { font-size: 11px; fill: #f1f5f9; pointer-events: none; }
  .node.SOURCE rect { fill: #1e40af; stroke: #3b82f6; }
  .node.JOB_ASSET rect { fill: #14532d; stroke: #22c55e; }
  .node.DOWNSTREAM rect { fill: #7c2d12; stroke: #f97316; }
  .node.INTERMEDIATE rect { fill: #1f2937; stroke: #6b7280; }
  .node:hover rect { opacity: 0.85; }
  .edge path { fill: none; stroke: #475569; stroke-width: 1.5; }
  .edge marker path { fill: #475569; }
  #tooltip { position: fixed; background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 10px 14px; font-size: 12px; max-width: 280px; pointer-events: none; display: none; z-index: 100; }
  #table-section { padding: 16px 24px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { background: #1e293b; padding: 8px 12px; text-align: left; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #334155; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  tr:hover td { background: #1e293b22; }
  .ts { color: #64748b; font-size: 11px; margin-left: 8px; }
  input#search { background: #1e293b; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; padding: 6px 12px; font-size: 13px; width: 240px; margin-bottom: 12px; }
</style>
</head>
<body>
<div id="header">
  <h1>&#x1F517; Lineage: {JOB_NAME}</h1>
  <span class="ts">Generated: {TIMESTAMP}</span>
  <span class="badge badge-source">&#x25CF; SOURCE: {N_SOURCE}</span>
  <span class="badge badge-job">&#x25CF; JOB: {N_JOB}</span>
  <span class="badge badge-down">&#x25CF; DOWNSTREAM: {N_DOWN}</span>
</div>
<div id="legend">
  <strong>Legend:</strong>
  <span><span class="dot" style="background:#3b82f6"></span> Source</span>
  <span><span class="dot" style="background:#22c55e"></span> Job Asset</span>
  <span><span class="dot" style="background:#f97316"></span> Downstream</span>
  <span><span class="dot" style="background:#6b7280"></span> Intermediate</span>
</div>
<div id="canvas-container"><svg id="graph-svg"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#475569"/></marker></defs><g id="graph-g"></g></svg></div>
<div id="tooltip"></div>
<div id="table-section">
  <input id="search" placeholder="Filter assets..." oninput="filterTable(this.value)">
  <table id="asset-table">
    <thead><tr><th>Asset Key</th><th>Role</th><th>Group</th><th>Compute Kind</th><th>Upstream</th><th>Downstream</th></tr></thead>
    <tbody id="table-body"></tbody>
  </table>
</div>
<script>
const DATA = {LINEAGE_DATA_JSON};

// ── Simple left-to-right layout ──────────────────────────────────────────────
function buildLayout(nodes, edges) {
  const nodeMap = {};
  nodes.forEach(n => nodeMap[n.id] = n);

  // Assign column by longest path from sources
  const col = {};
  const inDeg = {};
  nodes.forEach(n => { col[n.id] = 0; inDeg[n.id] = 0; });
  edges.forEach(e => { inDeg[e.to] = (inDeg[e.to] || 0) + 1; });

  const queue = nodes.filter(n => !inDeg[n.id]).map(n => n.id);
  while (queue.length) {
    const id = queue.shift();
    edges.filter(e => e.from === id).forEach(e => {
      col[e.to] = Math.max(col[e.to] || 0, (col[id] || 0) + 1);
      inDeg[e.to]--;
      if (inDeg[e.to] === 0) queue.push(e.to);
    });
  }

  // Group nodes by column
  const cols = {};
  nodes.forEach(n => {
    const c = col[n.id] || 0;
    cols[c] = cols[c] || [];
    cols[c].push(n.id);
  });

  const W = 200, H = 50, HGAP = 80, VGAP = 20, PAD = 40;
  const positions = {};
  Object.keys(cols).sort((a,b)=>a-b).forEach(c => {
    const ids = cols[c];
    ids.forEach((id, i) => {
      positions[id] = {
        x: PAD + c * (W + HGAP),
        y: PAD + i * (H + VGAP),
        w: W, h: H
      };
    });
  });
  return positions;
}

function shortLabel(key) {
  const parts = key.split('/');
  const last = parts[parts.length - 1];
  return last.length > 28 ? last.substring(0, 26) + '…' : last;
}

function render() {
  const svg = document.getElementById('graph-svg');
  const g = document.getElementById('graph-g');
  const pos = buildLayout(DATA.nodes, DATA.edges);

  // Set SVG size
  const maxX = Math.max(...Object.values(pos).map(p => p.x + p.w)) + 60;
  const maxY = Math.max(...Object.values(pos).map(p => p.y + p.h)) + 60;
  svg.setAttribute('viewBox', `0 0 ${maxX} ${maxY}`);
  svg.style.minWidth = maxX + 'px';
  svg.style.minHeight = maxY + 'px';

  // Draw edges
  DATA.edges.forEach(e => {
    const from = pos[e.from], to = pos[e.to];
    if (!from || !to) return;
    const x1 = from.x + from.w, y1 = from.y + from.h / 2;
    const x2 = to.x, y2 = to.y + to.h / 2;
    const cx = (x1 + x2) / 2;
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    el.setAttribute('class', 'edge');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`);
    path.setAttribute('marker-end', 'url(#arrow)');
    el.appendChild(path);
    g.appendChild(el);
  });

  // Draw nodes
  const tooltip = document.getElementById('tooltip');
  DATA.nodes.forEach(n => {
    const p = pos[n.id];
    if (!p) return;
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    el.setAttribute('class', `node ${n.role}`);
    el.setAttribute('transform', `translate(${p.x},${p.y})`);

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', p.w); rect.setAttribute('height', p.h);
    rect.setAttribute('rx', 6);
    el.appendChild(rect);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', p.w / 2); label.setAttribute('y', p.h / 2 - 4);
    label.setAttribute('text-anchor', 'middle'); label.setAttribute('dominant-baseline', 'middle');
    label.textContent = shortLabel(n.id);
    el.appendChild(label);

    if (n.group) {
      const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      sub.setAttribute('x', p.w / 2); sub.setAttribute('y', p.h / 2 + 12);
      sub.setAttribute('text-anchor', 'middle'); sub.setAttribute('font-size', '9');
      sub.setAttribute('fill', '#94a3b8');
      sub.textContent = n.group;
      el.appendChild(sub);
    }

    el.addEventListener('mouseenter', evt => {
      const up = DATA.edges.filter(e => e.to === n.id).length;
      const dn = DATA.edges.filter(e => e.from === n.id).length;
      tooltip.innerHTML = `<strong>${n.id}</strong><br>Role: ${n.role}<br>Group: ${n.group || '—'}<br>Kind: ${n.compute_kind || '—'}<br>Upstream: ${up} | Downstream: ${dn}${n.description ? '<br><em>' + n.description.substring(0,120) + '</em>' : ''}`;
      tooltip.style.display = 'block';
      tooltip.style.left = evt.clientX + 12 + 'px';
      tooltip.style.top = evt.clientY + 12 + 'px';
    });
    el.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
    g.appendChild(el);
  });
}

// ── Table ─────────────────────────────────────────────────────────────────────
function buildTable() {
  const tbody = document.getElementById('table-body');
  DATA.nodes.forEach(n => {
    const up = DATA.edges.filter(e => e.to === n.id).length;
    const dn = DATA.edges.filter(e => e.from === n.id).length;
    const roleClass = {'SOURCE':'badge-source','JOB_ASSET':'badge-job','DOWNSTREAM':'badge-down','INTERMEDIATE':'badge-inter'}[n.role] || '';
    tbody.innerHTML += `<tr>
      <td title="${n.id}">${n.id}</td>
      <td><span class="badge ${roleClass}">${n.role}</span></td>
      <td>${n.group || '—'}</td>
      <td>${n.compute_kind || '—'}</td>
      <td>${up}</td>
      <td>${dn}</td>
    </tr>`;
  });
}

function filterTable(q) {
  q = q.toLowerCase();
  document.querySelectorAll('#table-body tr').forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

render();
buildTable();
</script>
</body>
</html>
```

Replace the placeholders:
- `{JOB_NAME}` — the job name
- `{TIMESTAMP}` — current UTC timestamp
- `{N_SOURCE}`, `{N_JOB}`, `{N_DOWN}` — counts by role
- `{LINEAGE_DATA_JSON}` — the full `lineageData` JSON object

---

### Step 5 — Write the file

Write the completed HTML to the output path. Default location:

```
<workspace_root>/<job_name>/LINEAGE/<job_name>_lineage.html
```

If the `<job_name>` folder doesn't exist at the workspace root, write to:
```
<USER_HOME>\<job_name>_lineage.html
```

After writing, report:
- File path
- Total nodes: SOURCE / JOB_ASSET / DOWNSTREAM / INTERMEDIATE counts
- Total edges
- Any assets that could not be resolved

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Job not found in `dagster_get_job_assets` | Call `dagster_list_jobs` with search keyword, list closest matches, ask user to confirm |
| No assets returned for job | Report that the job may not use software-defined assets; offer raw GraphQL introspection |
| Asset dep fetch fails | Mark node as `INTERMEDIATE` with empty upstream/downstream; continue |
| Write permission error | Try alternate path `<USER_HOME>\<job>_lineage.html`; report actual path written |
