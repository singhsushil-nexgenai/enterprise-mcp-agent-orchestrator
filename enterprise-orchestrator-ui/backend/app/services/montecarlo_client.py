"""
Monte Carlo GraphQL client — queries monitors, incidents, table health.
Auth: MCD_API_KEY + MCD_API_SECRET env vars, or fallback to ~/.mcd/profiles.ini via pycarlo.
"""
import logging
from typing import Any

from app import config

logger = logging.getLogger(__name__)


def _get_client():
    """Create a pycarlo Client, or return None if not configured."""
    try:
        from pycarlo.core import Client, Session
        key = config.MC_API_KEY or None
        secret = config.MC_API_SECRET or None
        # If auto-detected from profiles.ini, pass them explicitly;
        # otherwise pycarlo falls back to ~/.mcd/profiles.ini [default]
        return Client(session=Session(mcd_id=key, mcd_token=secret))
    except Exception as e:
        logger.warning("Monte Carlo client init failed: %s", e)
        return None


def _gql(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL query against Monte Carlo."""
    client = _get_client()
    if not client:
        return {}
    try:
        resp = client(query, variables or {})
        return resp
    except Exception as e:
        logger.warning("Monte Carlo GraphQL error: %s", e)
        return {}


def is_configured() -> bool:
    """Check if MC credentials are available (env vars, config auto-detect, or profiles.ini)."""
    if config.MC_API_KEY and config.MC_API_SECRET:
        return True
    import os
    profiles = os.path.join(os.path.expanduser("~"), ".mcd", "profiles.ini")
    return os.path.exists(profiles)


# ── Public API ──

def search_table(table_name: str) -> dict[str, Any] | None:
    """Find a table in Monte Carlo by keyword search. Returns first match with MCON."""
    q = """
    query GetTables($search: String) {
      getTables(search: $search, first: 10) {
        edges {
          node {
            fullTableId
            friendlyName
            projectName
            dataset
            tableId
            tableType
            lastModified
            status
            mcon
          }
        }
      }
    }
    """
    # Extract just the table name part for search
    search_term = table_name.split(".")[-1] if "." in table_name else table_name
    data = _gql(q, {"search": search_term})
    edges = (data.get("get_tables") or data.get("getTables") or {}).get("edges", [])
    for e in edges:
        n = e.get("node", {})
        return {
            "full_table_id": n.get("fullTableId") or n.get("full_table_id"),
            "mcon": n.get("mcon"),
            "friendly_name": n.get("friendlyName") or n.get("friendly_name"),
            "dataset": n.get("dataset"),
            "table_type": n.get("tableType") or n.get("table_type"),
            "status": n.get("status"),
            "last_modified": str(n.get("lastModified") or n.get("last_modified") or ""),
        }
    return None


def get_incidents(full_table_id: str, limit: int = 20) -> list[dict]:
    """Get recent data quality events/alerts for a table."""
    q = """
    query GetEvents($fullTableId: String, $first: Int) {
      getEvents(fullTableId: $fullTableId, first: $first, descOrder: true) {
        edges {
          node {
            id
            uuid
            eventType
            eventState
            createdTime
            eventGeneratedTime
            table { fullTableId }
          }
        }
      }
    }
    """
    data = _gql(q, {"fullTableId": full_table_id, "first": limit})
    edges = (data.get("get_events") or data.get("getEvents") or {}).get("edges", [])
    rows = []
    for e in edges:
        n = e.get("node", {})
        rows.append({
            "id": n.get("uuid") or n.get("id"),
            "type": n.get("eventType") or n.get("event_type"),
            "state": n.get("eventState") or n.get("event_state"),
            "created_at": str(n.get("createdTime") or n.get("created_time") or ""),
            "event_time": str(n.get("eventGeneratedTime") or n.get("event_generated_time") or ""),
        })
    return rows


def get_monitors(mcon: str) -> list[dict]:
    """Get all monitors configured for a table by MCON."""
    q = """
    query GetMonitors($mcons: [String]) {
      getMonitors(mcons: $mcons, limit: 100) {
        uuid
        name
        monitorType
        isPaused
        isDraft
        description
        createdTime
        lastUpdateTime
        consolidatedMonitorStatus
        thirtyDaysIncidentCount
        sevenDaysIncidentCount
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
            "id": n.get("uuid"),
            "type": n.get("monitorType") or n.get("monitor_type"),
            "status": status,
            "name": n.get("name"),
            "description": n.get("description"),
            "incidents_30d": n.get("thirtyDaysIncidentCount") or n.get("thirty_days_incident_count") or 0,
            "incidents_7d": n.get("sevenDaysIncidentCount") or n.get("seven_days_incident_count") or 0,
        })
    return rows


def get_table_health(full_table_id: str | None = None, mcon: str | None = None) -> dict[str, Any]:
    """Get health/SLA status for a specific table."""
    # Resolve MCON if only full_table_id provided
    if not mcon and full_table_id:
        table_info = search_table(full_table_id)
        if table_info:
            mcon = table_info.get("mcon")
    if not mcon:
        return {"error": "Could not resolve MCON for table"}

    q = """
    query GetTableHealth($mcon: String!) {
      getTable(mcon: $mcon) {
        fullTableId
        mcon
        status
        lastModified
        lastObserved
        lastRead
        lastWrite
        isMonitored
        tableMonitorCount
      }
    }
    """
    data = _gql(q, {"mcon": mcon})
    t = data.get("get_table") or data.get("getTable") or {}
    return {
        "full_table_id": t.get("fullTableId") or t.get("full_table_id"),
        "mcon": t.get("mcon"),
        "status": t.get("status"),
        "last_modified": str(t.get("lastModified") or ""),
        "last_observed": str(t.get("lastObserved") or ""),
        "last_read": str(t.get("lastRead") or ""),
        "last_write": str(t.get("lastWrite") or ""),
        "is_monitored": t.get("isMonitored") or t.get("is_monitored"),
        "monitor_count": t.get("tableMonitorCount") or t.get("table_monitor_count") or 0,
    }


def get_full_table_intelligence(target_tables: list[str]) -> dict[str, dict]:
    """
    Get full MC intelligence for a list of target tables.
    Returns {table_name: {health, monitors, incidents}} dict.
    """
    if not is_configured():
        return {}

    results = {}
    for table in target_tables:
        table_info = search_table(table)
        if not table_info:
            results[table] = {"found": False, "error": "Table not found in Monte Carlo"}
            continue

        mcon = table_info.get("mcon")
        full_id = table_info.get("full_table_id")

        health = get_table_health(mcon=mcon)
        monitors = get_monitors(mcon) if mcon else []
        incidents = get_incidents(full_id, limit=10) if full_id else []

        results[table] = {
            "found": True,
            "table_info": table_info,
            "health": health,
            "monitors": monitors,
            "monitor_count": len(monitors),
            "incidents": incidents,
            "incident_count": len(incidents),
            "active_incidents": sum(1 for i in incidents if i.get("state") == "active"),
        }
    return results
