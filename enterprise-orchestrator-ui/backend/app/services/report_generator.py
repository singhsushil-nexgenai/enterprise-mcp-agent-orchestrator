"""
Rich HTML report generator — replicates exact MCP orchestrator format.
Accepts job config and SQL files as parameters (from GitHub API).
No local folder dependency — all data comes from the runner pipeline.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_tasks(config: dict) -> list[dict]:
    """Parse the tasks DAG from config."""
    tasks_raw = config.get("tasks", {})
    tasks = []
    for name, details in tasks_raw.items():
        task = {
            "name": name,
            "type": details.get("type", "unknown"),
            "next": details.get("next", []),
            "sql_files": [],
            "targets": [],
            "tmp_view": details.get("tmp_view", ""),
            "load_type": "",
        }
        for src in details.get("sources", []):
            path = src.get("sqlFileAbsolutePath", "")
            if path:
                task["sql_files"].append(path.split("/")[-1])
        for tgt in details.get("targets", []):
            tbl = f"{tgt.get('snowflake_database', '')}.{tgt.get('snowflake_schema', '')}.{tgt.get('snowflake_table', '')}"
            task["targets"].append(tbl)
            task["load_type"] = tgt.get("load_type", "")
        tasks.append(task)
    return tasks


def extract_target_tables(config: dict) -> list[str]:
    """Extract all target tables from config."""
    tables = []
    for _, details in config.get("tasks", {}).items():
        for tgt in details.get("targets", []):
            db = tgt.get("snowflake_database", "")
            schema = tgt.get("snowflake_schema", "")
            table = tgt.get("snowflake_table", "")
            if table:
                tables.append(f"{db}.{schema}.{table}")

    # Fallback: derive target table from job name + top-level config
    if not tables:
        sf_db = config.get("snowflake_database", "")
        dest_schema = config.get("destinationschema", "") or config.get("snowflake_schema", "") or "STG"
        # Job name typically maps to a table name
        for _, details in config.get("tasks", {}).items():
            for src in details.get("sources", []):
                path = src.get("sqlFileAbsolutePath", "")
                fname = path.split("/")[-1].replace(".sql", "") if path else ""
                # Look for load/insert/merge patterns → derive table name
                for keyword in ["_load", "_insert", "_merge", "_stg"]:
                    if keyword in fname:
                        tbl_name = fname.replace("_load", "").replace("_insert", "").replace("_merge", "").upper()
                        candidate = f"{sf_db}.{dest_schema}.{tbl_name}"
                        if candidate not in tables:
                            tables.append(candidate)

    return list(set(tables))


def _classify_task_type(task_name: str, task: dict) -> str:
    """Infer a display type for the task based on name/content."""
    name_lower = task_name.lower()
    if task["targets"]:
        return "LOAD_TARGET"
    if "truncate" in name_lower:
        return "TRUNCATE"
    if "reader" in name_lower or "extract" in name_lower:
        return "SOURCE_EXTRACT"
    if "surrogatekey" in name_lower or "surrogate" in name_lower:
        return "SURROGATE_KEY"
    if "dataqualityaudit" in name_lower or "dq" in name_lower:
        return "DQ_AUDIT"
    if "end" in name_lower:
        return "END"
    if task["sql_files"]:
        return "TRANSFORM"
    return "TASK"


def _task_type_badge(task_type: str) -> str:
    """Return HTML badge for task type."""
    badges = {
        "LOAD_TARGET": '<span class="status s-ok">LOAD_TARGET</span>',
        "TRUNCATE": '<span class="status s-warn">TRUNCATE</span>',
        "SOURCE_EXTRACT": '<span class="status s-info">SOURCE_EXTRACT</span>',
        "SURROGATE_KEY": '<span class="status s-info">SURROGATE_KEY</span>',
        "DQ_AUDIT": '<span class="status" style="background:#3b076422;color:#e9d5ff;border:1px solid #c084fc44">DQ_AUDIT</span>',
        "END": '<span class="status s-na">END</span>',
        "TRANSFORM": '<span class="status s-ok">TRANSFORM</span>',
        "TASK": '<span class="status s-info">TASK</span>',
    }
    return badges.get(task_type, '<span class="status s-info">TASK</span>')


def _extract_optimization_summary(content: str) -> str:
    """Extract optimization summary comments from optimized SQL."""
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- [OPT-") or stripped.startswith("--  "):
            lines.append(line)
        elif lines and stripped.startswith("--") and not stripped.startswith("---"):
            lines.append(line)
        elif lines and not stripped.startswith("--"):
            break
    return "\n".join(lines) if lines else "-- No optimization summary header found"


def generate_report(
    job_id: str,
    job_name: str | None,
    table_name: str | None,
    repo: str | None,
    live_data: dict | None = None,
    job_config: dict | None = None,
    sql_files: list[tuple[str, str]] | None = None,
) -> str:
    """
    Generate a rich self-contained HTML report matching MCP orchestrator format.
    All data is passed as parameters — no local folder dependency.

    Args:
        job_config: Parsed JSON config dict (from GitHub API)
        sql_files: List of (filename, content) tuples (from GitHub API)
        live_data: Real API results from dagster/montecarlo/snowflake/github
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    live_data = live_data or {}
    config = job_config or {}
    sql_files = sql_files or []
    resolved_name = job_name or "unknown"

    # Gather data from config
    optimized_files: list[tuple[str, str]] = []  # no local DQ/ folder
    tasks = extract_tasks(config) if config else []
    target_tables = extract_target_tables(config) if config else []

    # Metadata
    app_id = config.get("appid", "N/A")
    src_id = config.get("srcid", "N/A")
    sf_role = config.get("snowflake_role", "N/A")
    sf_warehouse = config.get("snowflake_warehouse", "N/A")
    sf_database = config.get("snowflake_database", "N/A")
    sf_schema = config.get("snowflake_schema", "N/A")
    start_at = config.get("startat", "N/A")
    version = config.get("version", "N/A")

    # Source system detection
    source_systems = []
    if config.get("vertica_hostname"):
        source_systems.append(("Vertica", config["vertica_hostname"], config.get("vertica_database", "")))
    if not source_systems:
        source_systems.append(("Snowflake", "internal", sf_database))

    # Incremental params
    incr = config.get("incremental_type_parameters", {})

    # Skills status
    dagster_data = live_data.get("dagster", {})
    mc_data = live_data.get("montecarlo", {})
    sf_data = live_data.get("snowflake", {})
    gh_data = live_data.get("github", {})

    dagster_available = dagster_data.get("available", False) and dagster_data.get("job_found", False)
    mc_available = bool(mc_data) and any(v.get("found") for v in mc_data.values()) if isinstance(mc_data, dict) else False

    skills_run = []
    gh_status = "SUCCESS" if config else "SKIP"
    gh_source = gh_data.get("source", "unknown")
    gh_note = f"Resolved to {resolved_name} (via {gh_source}: {gh_data.get('org_repo', '')})" if config else (gh_data.get("error", "Job not found"))
    skills_run.append(("job-resolver", gh_status, gh_note))
    skills_run.append(("etl-lineage-composer", "SUCCESS" if tasks else "SKIP", f"{len(tasks)} tasks &middot; {len(sql_files)} SQL files &middot; {len(target_tables)} target tables"))
    skills_run.append(("cmpgn-sql-optimization", "SKIP", "SQL optimization not available in web mode"))
    skills_run.append(("dagster-ops-intelligence", "SUCCESS" if dagster_available else ("SKIP" if dagster_data.get("available") else "UNAVAILABLE"), _dagster_skill_note(dagster_data)))
    skills_run.append(("mc-table-alerts", "SUCCESS" if mc_available else "UNAVAILABLE", f"Checked {len(mc_data)} tables" if mc_available else "Monte Carlo not configured or no tables found"))

    return _build_html(
        job_id=job_id,
        job_name=resolved_name,
        table_name=table_name,
        repo=repo,
        generated_at=now,
        app_id=app_id,
        src_id=src_id,
        sf_role=sf_role,
        sf_warehouse=sf_warehouse,
        sf_database=sf_database,
        sf_schema=sf_schema,
        start_at=start_at,
        version=version,
        source_systems=source_systems,
        target_tables=target_tables,
        tasks=tasks,
        sql_files=sql_files,
        optimized_files=optimized_files,
        incr_params=incr,
        job_source=f"{gh_data.get('source', 'local').title()}: {gh_data.get('org_repo', 'N/A')} (branch: {gh_data.get('branch', 'prod')})" if config else "Not resolved",
        skills_run=skills_run,
        dagster_data=dagster_data,
        mc_data=mc_data,
        sf_data=sf_data,
    )


def _dagster_skill_note(dagster_data: dict) -> str:
    """Generate a summary note for the Dagster skill status row."""
    if not dagster_data.get("available"):
        return dagster_data.get("error", "Dagster token not configured")
    if not dagster_data.get("job_found"):
        return "Job not found in Dagster"
    runs = dagster_data.get("runs", {})
    assets = dagster_data.get("assets", {})
    parts = []
    if runs.get("run_count"):
        parts.append(f"{runs['run_count']} runs")
    if assets.get("asset_count"):
        parts.append(f"{assets['asset_count']} assets")
    schedule = dagster_data.get("schedule", {})
    if schedule.get("found"):
        parts.append(f"schedule: {schedule.get('cron', 'N/A')}")
    return " &middot; ".join(parts) if parts else "Connected"


# ──────────────────────────────────────────────────────────────────
# HTML BUILDER — exact MCP orchestrator format
# ──────────────────────────────────────────────────────────────────

MCP_CSS = """:root {
  --bg:#0f172a; --surface:#1e293b; --surface2:#162032; --border:#334155;
  --text:#e2e8f0; --muted:#64748b; --accent:#38bdf8;
  --green:#4ade80; --yellow:#fbbf24; --red:#f87171; --purple:#c084fc; --orange:#fb923c;
}
*{box-sizing:border-box;}
body{margin:0;font-family:"Segoe UI",Tahoma,sans-serif;background:var(--bg);color:var(--text);line-height:1.55;}
.top-header{background:linear-gradient(120deg,#0f3977,#0a66c2 55%,#00897b);padding:20px 28px;}
.top-header h1{margin:0 0 6px;font-size:22px;color:#fff;}
.top-header p{margin:0;color:#cce8ff;font-size:13px;}
.top-meta{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}
.chip{padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700;}
.chip-blue{background:#1d4ed8;color:#bfdbfe;}
.chip-green{background:#15803d;color:#bbf7d0;}
.chip-yellow{background:#92400e;color:#fde68a;}
.chip-purple{background:#6b21a8;color:#e9d5ff;}
.chip-red{background:#991b1b;color:#fecaca;}
.layout{display:flex;min-height:100vh;}
.sidebar{width:210px;min-width:210px;background:var(--surface);border-right:1px solid var(--border);padding:12px 0;position:sticky;top:0;height:100vh;overflow-y:auto;}
.sidebar a{display:block;padding:7px 18px;color:var(--muted);text-decoration:none;font-size:12px;border-left:3px solid transparent;transition:all .15s;}
.sidebar a:hover,.sidebar a.active{color:var(--accent);border-left-color:var(--accent);background:#1a3a5f22;}
.sidebar .nav-label{padding:14px 18px 5px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);}
.main{flex:1;padding:22px 30px;max-width:1120px;}
.section{margin-bottom:38px;scroll-margin-top:16px;}
.section-header{display:flex;align-items:center;gap:10px;margin-bottom:12px;padding-bottom:9px;border-bottom:1px solid var(--border);}
.section-header h2{margin:0;font-size:17px;color:var(--text);}
.sn{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;}
.sn-blue{background:#1d4ed8;color:#bfdbfe;} .sn-green{background:#15803d;color:#bbf7d0;}
.sn-yellow{background:#92400e;color:#fde68a;} .sn-purple{background:#6b21a8;color:#e9d5ff;}
.sn-red{background:#991b1b;color:#fecaca;} .sn-cyan{background:#0e7490;color:#cffafe;}
.sn-gray{background:#374151;color:#d1d5db;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:10px;}
.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:13px 16px;}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;}
.stat-value{font-size:22px;font-weight:700;color:var(--text);margin-top:3px;}
.stat-sub{font-size:11px;color:var(--muted);margin-top:2px;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{background:#1a2740;padding:8px 12px;text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--border);font-size:10px;text-transform:uppercase;letter-spacing:.04em;}
td{padding:7px 12px;border-bottom:1px solid #1e293b66;color:#cbd5e1;vertical-align:top;}
tr:hover td{background:#1e293b88;}
.status{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:700;}
.s-ok{background:#14532d;color:#86efac;} .s-warn{background:#78350f;color:#fcd34d;}
.s-err{background:#7f1d1d;color:#fca5a5;} .s-skip{background:#1e293b;color:#64748b;}
.s-info{background:#1e40af;color:#93c5fd;} .s-na{background:#374151;color:#9ca3af;}
.alert{border-radius:8px;padding:10px 14px;margin:8px 0;font-size:12px;border-left:4px solid;}
.alert-info{background:#1e3a5f33;border-color:#3b82f6;color:#93c5fd;}
.alert-warn{background:#78350f33;border-color:#f59e0b;color:#fde68a;}
.alert-error{background:#7f1d1d33;border-color:#ef4444;color:#fca5a5;}
.alert-ok{background:#14532d33;border-color:#22c55e;color:#86efac;}
.pill{display:inline-block;padding:2px 7px;border-radius:999px;font-size:10px;margin:1px;}
.pill-sql{background:#1d4ed822;border:1px solid #3b82f666;color:#93c5fd;}
.pill-tbl{background:#0c4a6e22;border:1px solid #38bdf866;color:#7dd3fc;}
.pill-src{background:#3b076422;border:1px solid #c084fc66;color:#e9d5ff;}
.pill-ok{background:#14532d22;border:1px solid #22c55e66;color:#86efac;}
.code-block{background:#0d1117;border:1px solid var(--border);border-radius:7px;padding:12px 16px;font-family:Consolas,Menlo,monospace;font-size:11px;color:#c9d1d9;overflow-x:auto;white-space:pre;margin:8px 0;}
details{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin:6px 0;}
summary{cursor:pointer;font-size:12px;font-weight:600;color:#94a3b8;list-style:none;}
summary::-webkit-details-marker{display:none;}
summary::before{content:"\\25B6 ";font-size:10px;color:var(--muted);}
details[open] summary::before{content:"\\25BC ";}
details .code-block{margin-top:10px;}
.pri-critical{background:#7f1d1d22;} .pri-high{background:#78350f22;} .pri-medium{background:#3b2a0022;}
@media(max-width:700px){.sidebar{display:none;}.main{padding:14px;}}"""


def _build_dagster_section(dagster_data: dict) -> str:
    """Build HTML for Dagster Ops section from live data."""
    if not dagster_data.get("available"):
        return """  <div class="alert alert-warn">
    <strong>&#x26A0; Dagster data unavailable.</strong>
    {error}. Configure DAGSTER_TOKEN or place token at ~/.dagster/token to enable.
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Check</th><th>Result</th></tr></thead>
      <tbody>
        <tr><td>Job found in Dagster</td><td><span class="status s-na">NOT CHECKED</span></td></tr>
        <tr><td>Schedule intelligence</td><td><span class="status s-na">UNAVAILABLE</span></td></tr>
        <tr><td>Run history</td><td><span class="status s-na">UNAVAILABLE</span></td></tr>
        <tr><td>Asset dependencies</td><td><span class="status s-na">UNAVAILABLE</span></td></tr>
      </tbody>
    </table>
  </div>""".format(error=dagster_data.get("error", "Token not configured"))

    if not dagster_data.get("job_found"):
        return """  <div class="alert alert-info">
    <strong>Dagster connected</strong> but job was not found in any code location.
  </div>"""

    parts = []

    # Schedule card
    schedule = dagster_data.get("schedule", {})
    if schedule.get("found"):
        sched_status = schedule.get("status", "UNKNOWN")
        badge = '<span class="status s-ok">RUNNING</span>' if sched_status == "RUNNING" else f'<span class="status s-warn">{sched_status}</span>'
        parts.append(f"""  <div class="card-grid">
    <div class="stat-card"><div class="stat-label">Schedule</div><div class="stat-value" style="font-size:14px">{schedule.get("name", "N/A")}</div></div>
    <div class="stat-card"><div class="stat-label">Cron</div><div class="stat-value" style="font-size:14px">{schedule.get("cron", "N/A")}</div></div>
    <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="font-size:14px">{badge}</div></div>
  </div>""")

    # Run history
    runs = dagster_data.get("runs", {})
    if runs.get("found") and runs.get("runs"):
        stats = runs.get("stats", {})
        status_counts = runs.get("status_counts", {})
        parts.append(f"""  <div class="card-grid" style="margin-top:10px;">
    <div class="stat-card"><div class="stat-label">Total Runs</div><div class="stat-value">{runs.get("run_count", 0)}</div><div class="stat-sub">last 20</div></div>
    <div class="stat-card"><div class="stat-label">Success Rate</div><div class="stat-value">{runs.get("success_rate", 0)}%</div></div>
    <div class="stat-card"><div class="stat-label">Avg Duration</div><div class="stat-value" style="font-size:15px">{_fmt_duration(stats.get("avg_duration_s"))}</div></div>
    <div class="stat-card"><div class="stat-label">Min / Max</div><div class="stat-value" style="font-size:13px">{_fmt_duration(stats.get("min_duration_s"))} / {_fmt_duration(stats.get("max_duration_s"))}</div></div>
  </div>""")

        # Run history table
        run_rows = ""
        for r in runs["runs"][:10]:
            status = r.get("status", "UNKNOWN")
            if status == "SUCCESS":
                badge = '<span class="status s-ok">SUCCESS</span>'
            elif status == "FAILURE":
                badge = '<span class="status s-err">FAILURE</span>'
            elif status == "CANCELED":
                badge = '<span class="status s-warn">CANCELED</span>'
            else:
                badge = f'<span class="status s-info">{status}</span>'
            run_rows += f'        <tr><td><code style="font-size:10px">{r.get("run_id", "")[:8]}</code></td><td>{badge}</td><td>{r.get("start_time", "N/A")}</td><td>{_fmt_duration(r.get("duration_s"))}</td></tr>\n'

        parts.append(f"""  <div class="card" style="margin-top:10px;">
    <strong style="font-size:12px;color:#94a3b8">RECENT RUN HISTORY</strong>
    <table style="margin-top:8px;">
      <thead><tr><th>Run ID</th><th>Status</th><th>Started</th><th>Duration</th></tr></thead>
      <tbody>
{run_rows}      </tbody>
    </table>
  </div>""")

    # Assets
    assets = dagster_data.get("assets", {})
    if assets.get("found") and assets.get("assets"):
        asset_rows = ""
        for a in assets["assets"]:
            upstream = ", ".join(a.get("upstream", [])) or "&mdash;"
            downstream = ", ".join(a.get("downstream", [])) or "&mdash;"
            asset_rows += f'        <tr><td><strong>{a.get("key", "")}</strong></td><td>{a.get("group", "N/A")}</td><td>{a.get("compute_kind", "N/A")}</td><td style="font-size:10px">{upstream}</td><td style="font-size:10px">{downstream}</td></tr>\n'

        parts.append(f"""  <div class="card" style="margin-top:10px;">
    <strong style="font-size:12px;color:#94a3b8">SOFTWARE-DEFINED ASSETS ({assets.get("asset_count", 0)})</strong>
    <table style="margin-top:8px;">
      <thead><tr><th>Asset Key</th><th>Group</th><th>Compute Kind</th><th>Upstream</th><th>Downstream</th></tr></thead>
      <tbody>
{asset_rows}      </tbody>
    </table>
  </div>""")

    return "\n".join(parts) if parts else '  <div class="alert alert-info">Dagster connected but no detailed data available.</div>'


def _build_mc_section(mc_data: dict, target_tables: list[str]) -> str:
    """Build HTML for Monte Carlo section from live data."""
    if not mc_data:
        # Fallback: show placeholder cards per target table
        cards = ""
        for tbl in target_tables:
            cards += f"""  <div class="card" style="border-left: 4px solid #f59e0b;">
    <strong style="font-size:13px;color:#f1f5f9">{tbl}</strong>
    <table style="margin-top:10px;">
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Monitor Status</td><td><span class="status s-na">NOT CHECKED</span></td></tr>
        <tr><td>Active Incidents</td><td><span class="status s-na">UNKNOWN</span></td></tr>
        <tr><td>Health Status</td><td><span class="status s-na">UNAVAILABLE</span></td></tr>
      </tbody>
    </table>
    <div class="alert alert-warn" style="margin-top:10px;">Configure MCD_API_KEY and MCD_API_SECRET to enable Monte Carlo checks.</div>
  </div>
"""
        return f"""  <div class="alert alert-warn">
    <strong>&#x26A0; Monte Carlo data unavailable.</strong>
    Configure MCD_API_KEY and MCD_API_SECRET environment variables, or place credentials in ~/.mcd/profiles.ini.
  </div>
{cards}"""

    # Real data available
    parts = []
    total_monitors = 0
    total_incidents = 0
    total_active = 0

    for tbl, info in mc_data.items():
        if not info.get("found"):
            parts.append(f"""  <div class="card" style="border-left: 4px solid #64748b;">
    <strong style="font-size:13px;color:#f1f5f9">{tbl}</strong>
    <div class="alert alert-info" style="margin-top:8px;">Table not found in Monte Carlo</div>
  </div>""")
            continue

        health = info.get("health", {})
        monitors = info.get("monitors", [])
        incidents = info.get("incidents", [])
        active = info.get("active_incidents", 0)
        total_monitors += len(monitors)
        total_incidents += len(incidents)
        total_active += active

        # Health status badge
        h_status = health.get("status", "UNKNOWN")
        if h_status and "healthy" in str(h_status).lower():
            h_badge = '<span class="status s-ok">HEALTHY</span>'
        elif h_status and "warning" in str(h_status).lower():
            h_badge = '<span class="status s-warn">WARNING</span>'
        elif h_status and ("error" in str(h_status).lower() or "critical" in str(h_status).lower()):
            h_badge = '<span class="status s-err">ERROR</span>'
        else:
            h_badge = f'<span class="status s-info">{h_status or "UNKNOWN"}</span>'

        border_color = "#4ade80" if active == 0 else "#f87171"

        # Monitor rows
        monitor_rows = ""
        for m in monitors:
            m_status = m.get("status", "UNKNOWN")
            if m_status == "ACTIVE" or m_status == "HEALTHY":
                m_badge = f'<span class="status s-ok">{m_status}</span>'
            elif m_status == "PAUSED":
                m_badge = '<span class="status s-warn">PAUSED</span>'
            else:
                m_badge = f'<span class="status s-info">{m_status}</span>'
            monitor_rows += f'        <tr><td>{m.get("name", "N/A")}</td><td>{m.get("type", "N/A")}</td><td>{m_badge}</td><td>{m.get("incidents_7d", 0)}</td><td>{m.get("incidents_30d", 0)}</td></tr>\n'

        # Incident rows
        incident_rows = ""
        for inc in incidents[:5]:
            i_state = inc.get("state", "unknown")
            if i_state == "active":
                i_badge = '<span class="status s-err">ACTIVE</span>'
            elif i_state == "no_action_required":
                i_badge = '<span class="status s-ok">NO ACTION</span>'
            else:
                i_badge = f'<span class="status s-info">{i_state}</span>'
            incident_rows += f'        <tr><td><code style="font-size:10px">{inc.get("id", "")[:12]}</code></td><td>{inc.get("type", "N/A")}</td><td>{i_badge}</td><td>{inc.get("created_at", "N/A")}</td></tr>\n'

        card = f"""  <div class="card" style="border-left: 4px solid {border_color};">
    <strong style="font-size:13px;color:#f1f5f9">{tbl}</strong>
    <table style="margin-top:10px;">
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Health Status</td><td>{h_badge}</td></tr>
        <tr><td>Is Monitored</td><td>{'<span class="status s-ok">YES</span>' if health.get("is_monitored") else '<span class="status s-warn">NO</span>'}</td></tr>
        <tr><td>Monitor Count</td><td><strong>{len(monitors)}</strong></td></tr>
        <tr><td>Active Incidents</td><td>{'<span class="status s-err">' + str(active) + '</span>' if active > 0 else '<span class="status s-ok">0</span>'}</td></tr>
        <tr><td>Last Modified</td><td>{health.get("last_modified", "N/A")}</td></tr>
        <tr><td>Last Observed</td><td>{health.get("last_observed", "N/A")}</td></tr>
      </tbody>
    </table>"""

        if monitor_rows:
            card += f"""
    <div style="margin-top:12px;">
      <strong style="font-size:11px;color:#94a3b8">MONITORS ({len(monitors)})</strong>
      <table style="margin-top:6px;">
        <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>7d Inc</th><th>30d Inc</th></tr></thead>
        <tbody>
{monitor_rows}        </tbody>
      </table>
    </div>"""

        if incident_rows:
            card += f"""
    <div style="margin-top:12px;">
      <strong style="font-size:11px;color:#94a3b8">RECENT INCIDENTS ({len(incidents)})</strong>
      <table style="margin-top:6px;">
        <thead><tr><th>ID</th><th>Type</th><th>State</th><th>Created</th></tr></thead>
        <tbody>
{incident_rows}        </tbody>
      </table>
    </div>"""

        card += "\n  </div>"
        parts.append(card)

    # Summary cards at the top
    summary = f"""  <div class="card-grid" style="margin-bottom:12px;">
    <div class="stat-card"><div class="stat-label">Tables Checked</div><div class="stat-value">{len(mc_data)}</div></div>
    <div class="stat-card"><div class="stat-label">Total Monitors</div><div class="stat-value">{total_monitors}</div></div>
    <div class="stat-card"><div class="stat-label">Active Incidents</div><div class="stat-value" style="color:{'var(--red)' if total_active > 0 else 'var(--green)'}">{total_active}</div></div>
    <div class="stat-card"><div class="stat-label">Total Incidents</div><div class="stat-value">{total_incidents}</div></div>
  </div>"""

    return summary + "\n" + "\n".join(parts)


def _fmt_duration(seconds: float | None) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def _build_html(**ctx) -> str:
    """Construct the full HTML report in MCP orchestrator format."""

    # ── Section 1: Execution Summary ──
    skills_rows = ""
    for i, (skill, status, note) in enumerate(ctx["skills_run"]):
        if status == "SUCCESS":
            badge = '<span class="status s-ok">&#x2713; SUCCESS</span>'
        elif status == "SKIP":
            badge = '<span class="status s-skip">&mdash; SKIP</span>'
        else:
            badge = '<span class="status s-na">&mdash; UNAVAILABLE</span>'
        skills_rows += f'        <tr><td>{i}</td><td>{skill}</td><td>{badge}</td><td>{note}</td></tr>\n'

    # ── Section 2: Job Resolution ──
    sql_pills = " ".join(f'<span class="pill pill-sql">{f}</span>' for f, _ in ctx["sql_files"])
    target_pills_html = " ".join(f'<span class="pill pill-tbl">{t}</span>' for t in ctx["target_tables"]) or "None detected"
    source_pills = " ".join(f'<span class="pill pill-src">{name} &middot; {host}</span>' for name, host, _ in ctx["source_systems"])

    incr_rows = ""
    if ctx["incr_params"]:
        ip = ctx["incr_params"]
        incr_rows = f"""        <tr><td>Incremental Type</td><td><strong>{ip.get("incremental_type", "N/A")}</strong></td></tr>
        <tr><td>Partition Table</td><td>{ip.get("table_name", "N/A")}</td></tr>
        <tr><td>Migration Column</td><td>{ip.get("incremental_migration_column", "N/A")}</td></tr>
        <tr><td>Date Range</td><td>{ip.get("start_date", "")} &rarr; {ip.get("end_date", "")}</td></tr>"""

    # ── Section 3: ETL Lineage ──
    tasks_rows = ""
    for t in ctx["tasks"]:
        task_type = _classify_task_type(t["name"], t)
        type_badge = _task_type_badge(task_type)
        sql_cell = " ".join(f'<span class="pill pill-sql">{f}</span>' for f in t["sql_files"]) or "&mdash;"
        target_cell = " ".join(f'<span class="pill pill-tbl">{tbl}</span>' for tbl in t["targets"]) or (t["tmp_view"] or "&mdash;")
        next_str = " &rarr; ".join(t["next"]) if t["next"] else "END"
        tasks_rows += f'        <tr><td>{t["name"]}</td><td>{type_badge}</td><td>{next_str}</td><td>{sql_cell}</td><td>{target_cell}</td></tr>\n'

    # Source to Target summary
    src_tgt_rows = ""
    for t in ctx["tasks"]:
        if t["targets"]:
            src_name = ctx["source_systems"][0][0] if ctx["source_systems"] else "Snowflake"
            for tbl in t["targets"]:
                src_tgt_rows += f'        <tr><td><span class="pill pill-src">{src_name}</span></td><td>{t["name"]}</td><td><span class="pill pill-tbl">{tbl}</span></td><td>{t["load_type"] or "N/A"}</td></tr>\n'

    src_tgt_section = ""
    if src_tgt_rows:
        src_tgt_section = f"""  <div class="card" style="margin-top:10px;">
    <strong style="font-size:12px;color:#94a3b8">SOURCE &rarr; TARGET SUMMARY</strong>
    <table style="margin-top:8px;">
      <thead><tr><th>Source</th><th>Load Task</th><th>Target Table</th><th>Load Type</th></tr></thead>
      <tbody>
{src_tgt_rows}      </tbody>
    </table>
  </div>"""

    # ── Section 4: SQL Optimization ──
    opt_rows = ""
    opt_details = ""
    if ctx["optimized_files"]:
        for fname, content in ctx["optimized_files"]:
            summary = _extract_optimization_summary(content)
            opt_count = summary.count("[OPT-")
            original = fname.replace("_optimized.sql", ".sql")
            opt_rows += f'        <tr><td><span class="pill pill-sql">{original}</span></td><td>{fname}</td><td>Snowflake</td><td>{opt_count}</td></tr>\n'
            escaped_summary = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            opt_details += f"""  <details>
    <summary>{fname} &mdash; OPTIMIZATION SUMMARY</summary>
    <div class="code-block">{escaped_summary}</div>
  </details>
"""

    opt_section = ""
    if ctx["optimized_files"]:
        opt_section = f"""  <div class="card-grid" style="margin-bottom:12px;">
    <div class="stat-card"><div class="stat-label">Files Optimized</div><div class="stat-value">{len(ctx["optimized_files"])}</div></div>
    <div class="stat-card"><div class="stat-label">Source SQL Files</div><div class="stat-value">{len(ctx["sql_files"])}</div></div>
    <div class="stat-card"><div class="stat-label">Output Location</div><div class="stat-value" style="font-size:13px">DQ/</div><div class="stat-sub">*_optimized.sql</div></div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>SQL File</th><th>Optimized File</th><th>Platform</th><th># Opts</th></tr></thead>
      <tbody>
{opt_rows}      </tbody>
    </table>
  </div>
{opt_details}"""
    else:
        opt_section = '  <div class="alert alert-info">SQL optimization has not been run for this job. Run the <code>cmpgn-sql-optimization</code> skill to generate optimized SQL files in the DQ/ folder.</div>'

    # SQL file details (collapsible)
    sql_details = ""
    for fname, content in ctx["sql_files"]:
        escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        line_count = content.count("\n") + 1
        sql_details += f"""  <details>
    <summary>{fname} ({line_count} lines)</summary>
    <div class="code-block">{escaped}</div>
  </details>
"""

    # ── Section 7: Recommendations ──
    recommendations = []
    if not ctx["optimized_files"]:
        recommendations.append(("High", "SQL", f"Run SQL optimization skill on {ctx['job_name']} to identify performance improvements across {len(ctx['sql_files'])} SQL files.", "sql_opt"))
    if ctx["target_tables"]:
        for tbl in ctx["target_tables"]:
            recommendations.append(("High", "Monte Carlo", f"Verify monitor coverage on <strong>{tbl}</strong>. Add row count, freshness, and field health monitors if missing.", "montecarlo"))
    recommendations.append(("Medium", "Dagster", f"Verify if <code>{ctx['job_name']}</code> is registered in Dagster for schedule observability and run history tracking.", "dagster"))
    if any("SELECT *" in content.upper() for _, content in ctx["sql_files"]):
        recommendations.append(("Medium", "SQL &middot; Snowflake", "One or more SQL files use <code>SELECT *</code>. Replace with explicit column lists to prevent micro-partition over-scan and schema-change breakage.", "sql_opt"))

    rec_rows = ""
    for priority, area, desc, skill in recommendations:
        if priority == "Critical":
            pri_class = "pri-critical"
            badge = '<span class="status s-err">&#x1F534; Critical</span>'
        elif priority == "High":
            pri_class = "pri-high"
            badge = '<span class="status s-warn">&#x1F7E1; High</span>'
        else:
            pri_class = "pri-medium"
            badge = '<span class="status s-info">&#x1F7E2; Medium</span>'
        rec_rows += f'        <tr class="{pri_class}"><td>{badge}</td><td>{area}</td><td>{desc}</td><td>{skill}</td></tr>\n'

    # ── Section 8: Appendix ──
    artifacts_rows = ""
    if ctx["optimized_files"]:
        for fname, _ in ctx["optimized_files"]:
            artifacts_rows += f'        <tr><td>{fname}</td><td>Optimized SQL</td><td>{ctx["job_name"]}\\DQ\\</td></tr>\n'
    artifacts_rows += f'        <tr><td>{ctx["job_name"]}_report.html</td><td>Consolidated Report</td><td>reports/</td></tr>\n'

    raw_context = f"""JOB CONTEXT
&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;
job_name          : {ctx["job_name"]}
job_source        : {ctx["job_source"]}
json_config_path  : {ctx["job_name"]}.json
sql_files         : {", ".join(f for f, _ in ctx["sql_files"])}
target_tables     : {", ".join(ctx["target_tables"]) or "None detected"}
source_systems    : {", ".join(f"{n} ({h})" for n, h, _ in ctx["source_systems"])}
startat_task      : {ctx["start_at"]}
snowflake_db      : {ctx["sf_database"]}
snowflake_schema  : {ctx["sf_schema"]}
warehouse         : {ctx["sf_warehouse"]}
role              : {ctx["sf_role"]}
&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;&#x2550;"""

    # Count skills success
    skills_ok = sum(1 for _, s, _ in ctx["skills_run"] if s == "SUCCESS")
    skills_total = len(ctx["skills_run"])

    # ── ASSEMBLE FULL HTML ──
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCP Report: {ctx["job_name"]}</title>
<style>
{MCP_CSS}
</style>
</head>
<body>

<div class="top-header">
  <h1>&#x1F9E0; MCP Intelligence Report: {ctx["job_name"]}</h1>
  <p>ETL lineage &middot; SQL optimization &middot; Dagster ops &middot; Monte Carlo DQ &mdash; single consolidated view</p>
  <div class="top-meta">
    <span class="chip chip-blue">Generated: {ctx["generated_at"]}</span>
    <span class="chip chip-green">Job: {ctx["job_name"]}</span>
    <span class="chip chip-yellow">Input: {"job_name=" + ctx["job_name"] if not ctx["table_name"] else "table_name=" + ctx["table_name"]}</span>
    <span class="chip chip-purple">Skills: resolver &middot; lineage &middot; sql_opt &middot; dagster &middot; montecarlo</span>
    <span class="chip chip-red">&#x26A0; {len(recommendations)} Findings</span>
  </div>
</div>

<div class="layout">
<nav class="sidebar">
  <div class="nav-label">Sections</div>
  <a href="#s1">1 &middot; Execution Summary</a>
  <a href="#s2">2 &middot; Job Resolution</a>
  <a href="#s3">3 &middot; ETL Lineage</a>
  <a href="#s4">4 &middot; SQL Optimization</a>
  <a href="#s5">5 &middot; Dagster Ops</a>
  <a href="#s6">6 &middot; Monte Carlo DQ</a>
  <a href="#s7">7 &middot; Recommendations</a>
  <a href="#s8">8 &middot; Appendix</a>
</nav>

<main class="main">

<!-- === SECTION 1: Execution Summary === -->
<section class="section" id="s1">
  <div class="section-header">
    <div class="sn sn-blue">1</div>
    <h2>Execution Summary</h2>
  </div>
  <div class="card-grid">
    <div class="stat-card"><div class="stat-label">Job Name</div><div class="stat-value" style="font-size:15px">{ctx["job_name"]}</div></div>
    <div class="stat-card"><div class="stat-label">Input Mode</div><div class="stat-value" style="font-size:15px">{"table_name" if ctx["table_name"] else "job_name"}</div><div class="stat-sub">{ctx["table_name"] or ctx["job_name"]}</div></div>
    <div class="stat-card"><div class="stat-label">Skills Run</div><div class="stat-value" style="font-size:15px">{skills_ok} / {skills_total}</div><div class="stat-sub">resolver &middot; lineage &middot; sql_opt &middot; dagster &middot; montecarlo</div></div>
    <div class="stat-card"><div class="stat-label">Generated</div><div class="stat-value" style="font-size:14px">{ctx["generated_at"]}</div></div>
  </div>
  <div class="card" style="margin-top:12px;">
    <table>
      <thead><tr><th>Step</th><th>Skill</th><th>Status</th><th>Notes</th></tr></thead>
      <tbody>
{skills_rows}      </tbody>
    </table>
  </div>
</section>

<!-- === SECTION 2: Job Resolution === -->
<section class="section" id="s2">
  <div class="section-header">
    <div class="sn sn-blue">2</div>
    <h2>Job Resolution &amp; Metadata</h2>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Job Name</td><td><strong>{ctx["job_name"]}</strong></td></tr>
        <tr><td>Source</td><td><code style="font-size:11px;color:#7dd3fc">{ctx["job_source"]}</code></td></tr>
        <tr><td>JSON Config</td><td><code style="font-size:11px;color:#7dd3fc">{ctx["job_name"]}.json</code></td></tr>
        <tr><td>App ID / Source ID</td><td>{ctx["app_id"]} / {ctx["src_id"]}</td></tr>
        <tr><td>Config Version</td><td>{ctx["version"]}</td></tr>
        <tr><td>Entry Task</td><td><strong>{ctx["start_at"]}</strong></td></tr>
        <tr><td>Snowflake Role</td><td>{ctx["sf_role"]}</td></tr>
        <tr><td>Warehouse</td><td>{ctx["sf_warehouse"]}</td></tr>
        <tr><td>Snowflake DB / Schema</td><td>{ctx["sf_database"]} / {ctx["sf_schema"]}</td></tr>
        <tr><td>Source Systems</td><td>{source_pills}</td></tr>
        <tr><td>SQL Files</td><td>{sql_pills or "None"}</td></tr>
        <tr><td>Target Tables</td><td>{target_pills_html}</td></tr>
        {incr_rows}
      </tbody>
    </table>
  </div>
</section>

<!-- === SECTION 3: ETL Lineage === -->
<section class="section" id="s3">
  <div class="section-header">
    <div class="sn sn-green">3</div>
    <h2>ETL Lineage &amp; Task Flow</h2>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Task</th><th>Type</th><th>Next &rarr;</th><th>SQL File(s)</th><th>Targets / Views</th></tr></thead>
      <tbody>
{tasks_rows}      </tbody>
    </table>
  </div>
{src_tgt_section}
</section>

<!-- === SECTION 4: SQL Optimization === -->
<section class="section" id="s4">
  <div class="section-header">
    <div class="sn sn-yellow">4</div>
    <h2>SQL {"Optimization Results" if ctx["optimized_files"] else "Files"}</h2>
  </div>
{opt_section}
  <h3 style="font-size:13px;color:var(--muted);margin-top:18px;">Source SQL Files ({len(ctx["sql_files"])})</h3>
{sql_details}
</section>

<!-- === SECTION 5: Dagster Ops === -->
<section class="section" id="s5">
  <div class="section-header">
    <div class="sn sn-purple">5</div>
    <h2>Dagster Operational Intelligence</h2>
  </div>
{_build_dagster_section(ctx.get("dagster_data", {}))}
</section>

<!-- === SECTION 6: Monte Carlo DQ === -->
<section class="section" id="s6">
  <div class="section-header">
    <div class="sn sn-cyan">6</div>
    <h2>Monte Carlo Data Quality Intelligence</h2>
  </div>
{_build_mc_section(ctx.get("mc_data", {}), ctx["target_tables"])}
</section>

<!-- === SECTION 7: Recommendations === -->
<section class="section" id="s7">
  <div class="section-header">
    <div class="sn sn-red">7</div>
    <h2>Consolidated Recommendations</h2>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Priority</th><th>Area</th><th>Recommendation</th><th>Skill</th></tr></thead>
      <tbody>
{rec_rows}      </tbody>
    </table>
  </div>
</section>

<!-- === SECTION 8: Appendix === -->
<section class="section" id="s8">
  <div class="section-header">
    <div class="sn sn-gray">8</div>
    <h2>Appendix</h2>
  </div>
  <div class="card" style="margin-bottom:10px;">
    <strong style="font-size:12px;color:#94a3b8">ARTIFACTS GENERATED</strong>
    <table style="margin-top:8px;">
      <thead><tr><th>File</th><th>Type</th><th>Path</th></tr></thead>
      <tbody>
{artifacts_rows}      </tbody>
    </table>
  </div>
  <details>
    <summary>Raw Job Context Block</summary>
    <div class="code-block">{raw_context}</div>
  </details>
</section>

</main>
</div>
</body>
</html>"""
