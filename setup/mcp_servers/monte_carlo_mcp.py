#!/usr/bin/env python3
"""
Monte Carlo MCP Server — stdio JSON-RPC 2.0.

Credential resolution order (first wins):
  1. MCD_API_KEY + MCD_API_SECRET environment variables  (set via VS Code mcp.json ${input:...})
  2. ~/.mcd/profiles.ini [default] section               (legacy / fallback via pycarlo)

SSL certificate:
  DTV_CA_CERT env var  →  path to corporate_root_ca.pem
  (set automatically by mcp.json to %USERPROFILE%\\corporate_root_ca.pem)

Provides: mc_list_tables, mc_get_incidents, mc_get_table_monitors,
          mc_get_table_lineage, mc_get_table_health, mc_run_graphql
"""
import sys
import json
import os
import traceback

# ── helpers ────────────────────────────────────────────────────────────────────
def _write(obj):
    line = json.dumps(obj, default=str) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()

def _ok(id_, result):
    _write({"jsonrpc": "2.0", "id": id_, "result": result})

def _err(id_, code, msg):
    _write({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}})

# ── SSL cert ───────────────────────────────────────────────────────────────────
# pycarlo uses requests under the hood; patch it to use the corporate cert
_DTV_CA = os.environ.get("DTV_CA_CERT") or os.path.join(os.path.expanduser("~"), "corporate_root_ca.pem")
if os.path.exists(_DTV_CA):
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _DTV_CA)

# ── Monte Carlo client ─────────────────────────────────────────────────────────
def _client():
    from pycarlo.core import Client, Session
    key      = os.environ.get("MCD_API_KEY") or None
    token    = os.environ.get("MCD_API_SECRET") or None
    base_url = os.environ.get("MCD_BASE_URL", "https://api.getmontecarlo.com/graphql")
    # If env vars not set, pycarlo falls back to ~/.mcd/profiles.ini [default]
    return Client(session=Session(mcd_id=key, mcd_token=token, endpoint=base_url))

def _gql(query, variables=None):
    client = _client()
    resp = client(query, variables or {})
    return resp

# ── tool definitions ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "mc_list_tables",
        "description": "List tables/assets monitored by Monte Carlo. Optionally filter by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Optional keyword to filter table names"}
            }
        }
    },
    {
        "name": "mc_get_incidents",
        "description": "Get recent data quality events/alerts from Monte Carlo. Optionally filter by table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit":         {"type": "integer", "description": "Max number of events to return (default 20)"},
                "full_table_id": {"type": "string",  "description": "Filter events to a specific table, e.g. cmpgn:tgt.app_dvc_typ_dim"},
                "event_states":  {"type": "array", "items": {"type": "string"}, "description": "Filter by event state(s), e.g. ['active', 'no_action_required']"}
            }
        }
    },
    {
        "name": "mc_get_table_monitors",
        "description": "Get all monitors (rules) configured for a specific table in Monte Carlo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "full_table_id": {"type": "string", "description": "Full table ID e.g. cmpgn:tgt.app_dvc_typ_dim"},
                "mcon":          {"type": "string", "description": "Monte Carlo object name (MCON) — preferred over full_table_id"}
            }
        }
    },
    {
        "name": "mc_get_table_lineage",
        "description": "Get upstream and downstream lineage for a table in Monte Carlo.",
        "inputSchema": {
            "type": "object",
            "required": ["mcon"],
            "properties": {
                "mcon": {"type": "string", "description": "Monte Carlo object name (MCON) for the table"}
            }
        }
    },
    {
        "name": "mc_get_table_health",
        "description": "Get health / SLA status summary for a specific table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "full_table_id": {"type": "string", "description": "Full table ID e.g. cmpgn:tgt.app_dvc_typ_dim"},
                "mcon":          {"type": "string", "description": "Monte Carlo object name (MCON) — preferred over full_table_id"}
            }
        }
    },
    {
        "name": "mc_run_graphql",
        "description": "Run a raw GraphQL query against the Monte Carlo API.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query":     {"type": "string", "description": "GraphQL query string"},
                "variables": {"type": "object", "description": "Optional variables dict"}
            }
        }
    }
]

# ── tool handlers ──────────────────────────────────────────────────────────────
def mc_list_tables(args):
    search = args.get("search", "")
    q = """
    query GetTables($search: String) {
      getTables(search: $search, first: 50) {
        edges { node { fullTableId friendlyName projectName dataset tableId tableType lastModified status mcon } }
      }
    }
    """
    data = _gql(q, {"search": search} if search else {})
    edges = (data.get("get_tables") or data.get("getTables") or {}).get("edges", [])
    rows = []
    for e in edges:
        n = e.get("node", {})
        rows.append({
            "full_table_id": n.get("fullTableId") or n.get("full_table_id"),
            "mcon":          n.get("mcon"),
            "friendly_name": n.get("friendlyName") or n.get("friendly_name"),
            "dataset":       n.get("dataset"),
            "table_id":      n.get("tableId") or n.get("table_id"),
            "table_type":    n.get("tableType") or n.get("table_type"),
            "status":        n.get("status"),
            "last_modified": str(n.get("lastModified") or n.get("last_modified") or ""),
        })
    return {"tables": rows, "count": len(rows)}


def mc_get_incidents(args):
    limit         = args.get("limit", 20)
    full_table_id = args.get("full_table_id")
    event_states  = args.get("event_states")
    q = """
    query GetEvents($fullTableId: String, $first: Int, $eventStates: [String]) {
      getEvents(fullTableId: $fullTableId, first: $first, eventStates: $eventStates, descOrder: true) {
        edges { node { id uuid eventType eventState createdTime eventGeneratedTime table { fullTableId } } }
      }
    }
    """
    variables = {"first": limit}
    if full_table_id:
        variables["fullTableId"] = full_table_id
    if event_states:
        variables["eventStates"] = event_states
    data = _gql(q, variables)
    edges = (data.get("get_events") or data.get("getEvents") or {}).get("edges", [])
    rows = []
    for e in edges:
        n = e.get("node", {})
        tbl = n.get("table") or {}
        rows.append({
            "id":         n.get("uuid") or n.get("id"),
            "type":       n.get("eventType") or n.get("event_type"),
            "state":      n.get("eventState") or n.get("event_state"),
            "created_at": str(n.get("createdTime") or n.get("created_time") or ""),
            "event_time": str(n.get("eventGeneratedTime") or n.get("event_generated_time") or ""),
            "table":      tbl.get("fullTableId") or tbl.get("full_table_id"),
        })
    return {"incidents": rows, "count": len(rows)}


def mc_get_table_monitors(args):
    mcon          = args.get("mcon")
    full_table_id = args.get("full_table_id")
    if not mcon and full_table_id:
        search_term = full_table_id.split(".")[-1]
        tables_data = mc_list_tables({"search": search_term})
        for t in tables_data.get("tables", []):
            if (t.get("full_table_id") or "").lower() == full_table_id.lower():
                mcon = t.get("mcon")
                break
    if not mcon:
        return {"monitors": [], "count": 0, "table": full_table_id, "mcon": None,
                "error": "Could not resolve MCON — pass mcon directly or verify full_table_id"}
    q = """
    query GetMonitors($mcons: [String]) {
      getMonitors(mcons: $mcons, limit: 100) {
        uuid name monitorType isPaused isDraft description createdTime lastUpdateTime
        consolidatedMonitorStatus thirtyDaysIncidentCount sevenDaysIncidentCount
      }
    }
    """
    data = _gql(q, {"mcons": [mcon]})
    monitors_raw = data.get("get_monitors") or data.get("getMonitors") or []
    rows = []
    for n in monitors_raw:
        is_paused = n.get("isPaused") or n.get("is_paused") or False
        status = "PAUSED" if is_paused else (n.get("consolidatedMonitorStatus") or n.get("consolidated_monitor_status") or "ACTIVE")
        rows.append({
            "id":            n.get("uuid"),
            "type":          n.get("monitorType") or n.get("monitor_type"),
            "status":        status,
            "name":          n.get("name"),
            "description":   n.get("description"),
            "created_at":    str(n.get("createdTime") or n.get("created_time") or ""),
            "incidents_30d": n.get("thirtyDaysIncidentCount") or n.get("thirty_days_incident_count") or 0,
            "incidents_7d":  n.get("sevenDaysIncidentCount") or n.get("seven_days_incident_count") or 0,
        })
    return {"monitors": rows, "count": len(rows), "table": full_table_id, "mcon": mcon}


def mc_get_table_lineage(args):
    mcon = args["mcon"]
    q = """
    query GetLineage($mcon: String!) {
      getTableLineage(mcon: $mcon) {
        upstreamTables { mcon fullTableId }
        downstreamTables { mcon fullTableId }
      }
    }
    """
    data = _gql(q, {"mcon": mcon})
    lin = data.get("get_table_lineage") or data.get("getTableLineage") or {}
    return {
        "upstream":   [t.get("fullTableId") or t.get("full_table_id") for t in (lin.get("upstreamTables") or lin.get("upstream_tables") or [])],
        "downstream": [t.get("fullTableId") or t.get("full_table_id") for t in (lin.get("downstreamTables") or lin.get("downstream_tables") or [])],
    }


def mc_get_table_health(args):
    mcon          = args.get("mcon")
    full_table_id = args.get("full_table_id")
    if not mcon and full_table_id:
        search_term = full_table_id.split(".")[-1]
        tables_data = mc_list_tables({"search": search_term})
        for t in tables_data.get("tables", []):
            if (t.get("full_table_id") or "").lower() == full_table_id.lower():
                mcon = t.get("mcon")
                break
    if not mcon:
        return {"error": "Could not resolve MCON — pass mcon directly or verify full_table_id"}
    q = """
    query GetTableHealth($mcon: String!) {
      getTable(mcon: $mcon) {
        fullTableId mcon status lastModified lastObserved lastRead lastWrite isMonitored tableMonitorCount
      }
    }
    """
    data = _gql(q, {"mcon": mcon})
    tbl = data.get("get_table") or data.get("getTable") or {}
    return {
        "full_table_id": tbl.get("fullTableId") or tbl.get("full_table_id"),
        "mcon":          tbl.get("mcon") or mcon,
        "status":        tbl.get("status"),
        "last_modified": str(tbl.get("lastModified") or tbl.get("last_modified") or ""),
        "last_observed": str(tbl.get("lastObserved") or tbl.get("last_observed") or ""),
        "last_read":     str(tbl.get("lastRead") or tbl.get("last_read") or ""),
        "last_write":    str(tbl.get("lastWrite") or tbl.get("last_write") or ""),
        "is_monitored":  tbl.get("isMonitored") or tbl.get("is_monitored"),
        "monitor_count": tbl.get("tableMonitorCount") or tbl.get("table_monitor_count"),
    }


def mc_run_graphql(args):
    data = _gql(args["query"], args.get("variables") or {})
    return {"result": data}


HANDLERS = {
    "mc_list_tables":        mc_list_tables,
    "mc_get_incidents":      mc_get_incidents,
    "mc_get_table_monitors": mc_get_table_monitors,
    "mc_get_table_lineage":  mc_get_table_lineage,
    "mc_get_table_health":   mc_get_table_health,
    "mc_run_graphql":        mc_run_graphql,
}

# ── MCP protocol loop ──────────────────────────────────────────────────────────
def handle(req):
    method = req.get("method", "")
    id_    = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        _ok(id_, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "monte-carlo-mcp", "version": "1.0.0"}})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        _ok(id_, {"tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if not fn:
            _err(id_, -32601, f"Unknown tool: {name}")
            return
        try:
            result = fn(args)
            _ok(id_, {"content": [{"type": "text", "text": json.dumps(result, default=str, indent=2)}]})
        except Exception as exc:
            _err(id_, -32000, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
    elif method == "ping":
        _ok(id_, {})
    else:
        if id_ is not None:
            _err(id_, -32601, f"Method not found: {method}")


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            _err(None, -32700, f"Parse error: {exc}")
            continue
        try:
            handle(req)
        except Exception as exc:
            _err(req.get("id"), -32603, f"Internal error: {exc}")


if __name__ == "__main__":
    main()
