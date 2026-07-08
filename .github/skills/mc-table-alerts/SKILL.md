---
name: mc-table-alerts
description: >
  Given a table name (full or partial), queries Monte Carlo via MCP to produce a
  consolidated report of all monitors, active alerts/incidents, and health status
  for that table. Use this skill whenever a user asks about Monte Carlo monitors,
  alerts, data quality checks, or incidents for a specific table.
---

## Purpose

Look up a table in Monte Carlo and return a single consolidated report covering:
- **Table identity** — resolved `full_table_id`, health status, SLA status, row count, last updated
- **Monitors** — every monitor (rule) attached to the table: type, status, name, description
- **Active Incidents / Alerts** — any open incidents where this table is an affected object

---

## Inputs

| Parameter | Description |
|-----------|-------------|
| `table_name` | Table name to look up. Can be full (`CMPGN.TGT.CMPGN_LYLT_OFFR_FCT`), partial (`cmpgn_lylt_offr_fct`), or a keyword. Case-insensitive. |

---

## Step-by-Step Instructions

### Step 1 — Resolve the full table ID

Call **`mc_list_tables`** with the `search` argument set to `table_name`.

```
mc_list_tables({ "search": "<table_name>" })
```

- If **no results** are returned, try again with a shorter keyword (strip schema prefix).
- If **multiple results** are returned, pick the best match (exact name match preferred). If ambiguous, list the candidates and ask the user to confirm before continuing.
- Extract the `full_table_id` from the matching result (e.g. `cmpgn:tgt.cmpgn_lylt_offr_fct`). Store it for the subsequent calls.

---

### Step 2 — Fetch monitors and health in parallel

Once `full_table_id` is confirmed, make **both** calls simultaneously:

**2a. Monitors**
```
mc_get_table_monitors({ "full_table_id": "<full_table_id>" })
```

**2b. Health / SLA**
```
mc_get_table_health({ "full_table_id": "<full_table_id>" })
```

---

### Step 3 — Fetch active incidents

Call **`mc_get_incidents`** for active incidents and filter the results client-side to only those where `affected` list contains the resolved `full_table_id` (case-insensitive substring match):

```
mc_get_incidents({ "limit": 50, "status": "ACTIVE" })
```

If the active results are empty, repeat with `status` omitted (all statuses) and limit to last 20, again filtering by table.

---

### Step 4 — Compose and present the report

Format the output as a structured Markdown report with four sections:

---

#### Section 1 — Table Identity

| Field | Value |
|-------|-------|
| Full Table ID | `<full_table_id>` |
| Status | `<status>` |
| SLA Status | `<sla_status>` |
| Row Count | `<row_count>` |
| Last Updated | `<last_updated>` |

---

#### Section 2 — Monitors (`<count>` total)

Render a table:

| # | Monitor Name | Type | Status | Description |
|---|-------------|------|--------|-------------|
| 1 | ... | ... | ... | ... |

- If `count = 0`, print: _"No monitors configured for this table."_
- Sort by: **ACTIVE** monitors first, then PAUSED, then others.
- Highlight rows where `status = PAUSED` with a ⚠️ prefix on the name.

---

#### Section 3 — Active Alerts / Incidents (`<count>` found)

Render a table:

| # | Incident ID | Type | Severity | Started At | Status |
|---|------------|------|----------|-----------|--------|
| 1 | ... | ... | ... | ... | ... |

- If no matching incidents, print: _"No active incidents found for this table."_
- Sort by `started_at` descending (most recent first).
- Flag `severity = HIGH` or `CRITICAL` rows with a 🔴 prefix.

---

#### Section 4 — Summary

End with a one-paragraph plain-English summary of the overall data quality posture:
- How many monitors are active vs. paused
- Whether there are open incidents and their severity
- SLA / health status
- Any recommended follow-up actions (e.g. "2 monitors are PAUSED — consider reactivating to restore coverage")

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Table not found in mc_list_tables | Inform the user and suggest checking the table name spelling or confirming it is registered in Monte Carlo |
| mc_get_table_monitors returns error | Show monitors as "unavailable", continue with other sections |
| mc_get_table_health returns error | Show health as "unavailable", continue with other sections |
| mc_get_incidents returns error | Show incidents as "unavailable", note error in summary |
| Multiple ambiguous table matches | List all candidates, ask user to confirm before proceeding |
