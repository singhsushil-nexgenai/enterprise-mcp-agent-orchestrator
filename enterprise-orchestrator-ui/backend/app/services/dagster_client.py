"""
Dagster Cloud GraphQL client — queries job runs, schedules, assets.
Auth: reads token from ~/.dagster/token (same as the Dagster MCP server).
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app import config

logger = logging.getLogger(__name__)


def _get_token() -> str:
    """Resolve Dagster token: env var first, then file."""
    if config.DAGSTER_TOKEN:
        return config.DAGSTER_TOKEN
    token_file = config.DAGSTER_TOKEN_FILE
    if os.path.exists(token_file):
        return open(token_file).read().strip()
    return ""


def _headers() -> dict:
    return {
        "Dagster-Cloud-Api-Token": _get_token(),
        "Content-Type": "application/json",
    }


def _ca_cert() -> str | bool:
    """Return CA cert path if it exists, else False (disable verify for corporate proxy)."""
    ca = config.DTV_CA_CERT
    if os.path.exists(ca):
        return ca
    return False


def _gql(query: str, variables: dict | None = None, timeout: float = 60) -> dict:
    """Execute GraphQL against Dagster Cloud."""
    try:
        r = httpx.post(
            config.DAGSTER_URL,
            json={"query": query, "variables": variables or {}},
            headers=_headers(),
            timeout=timeout,
            verify=_ca_cert(),
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            logger.warning("Dagster GraphQL errors: %s", data["errors"])
            return {}
        return data.get("data", {})
    except Exception as e:
        logger.warning("Dagster API error: %s", e)
        return {}


def is_configured() -> bool:
    return bool(_get_token())


# ── Workspace / Repo resolution ──

_REPOS_CACHE: list[dict] | None = None


def _get_repos() -> list[dict]:
    global _REPOS_CACHE
    if _REPOS_CACHE is not None:
        return _REPOS_CACHE
    q = """
    { workspaceOrError { ... on Workspace { locationEntries {
      name
      locationOrLoadError { __typename
        ... on RepositoryLocation { repositories { name pipelines { name } } }
      }
    } } } }
    """
    data = _gql(q)
    repos = []
    for entry in (data.get("workspaceOrError") or {}).get("locationEntries", []):
        loc_name = entry["name"]
        loc = entry.get("locationOrLoadError") or {}
        for repo in loc.get("repositories") or []:
            jobs = [p["name"] for p in repo.get("pipelines") or []]
            repos.append({"location": loc_name, "repo": repo["name"], "jobs": jobs})
    _REPOS_CACHE = repos
    return repos


def _find_repo_for_job(job_name: str) -> tuple[str | None, str | None, str | None]:
    """Return (location, repo_name, actual_job_name) or (None, None, None)."""
    for entry in _get_repos():
        if job_name in entry["jobs"]:
            return entry["location"], entry["repo"], job_name
    # Try cmpgn_dp_ prefix variant
    prefixed = f"cmpgn_dp_{job_name}"
    for entry in _get_repos():
        if prefixed in entry["jobs"]:
            return entry["location"], entry["repo"], prefixed
    return None, None, None


def _key_str(key_obj) -> str:
    path = key_obj.get("path") if isinstance(key_obj, dict) else key_obj
    return "/".join(path) if isinstance(path, list) else str(path)


# ── Public API ──

def get_job_assets(job_name: str) -> dict[str, Any]:
    """Get all software-defined assets in a Dagster job."""
    location, repo, resolved = _find_repo_for_job(job_name)
    if not location:
        return {"found": False, "error": f"Job '{job_name}' not found in Dagster", "assets": []}

    q = """
    query JobAssets($pipeline: PipelineSelector!) {
      assetNodes(pipeline: $pipeline) {
        id
        assetKey { path }
        opNames
        groupName
        computeKind
        description
        dependencyKeys { path }
        dependedByKeys { path }
      }
    }
    """
    variables = {
        "pipeline": {
            "pipelineName": resolved,
            "repositoryName": repo,
            "repositoryLocationName": location,
        }
    }
    data = _gql(q, variables)
    nodes = data.get("assetNodes") or []
    assets = []
    for n in nodes:
        assets.append({
            "key": _key_str(n["assetKey"]),
            "op_names": n.get("opNames") or [],
            "group": n.get("groupName"),
            "compute_kind": n.get("computeKind"),
            "description": n.get("description"),
            "upstream": [_key_str(d) for d in (n.get("dependencyKeys") or [])],
            "downstream": [_key_str(d) for d in (n.get("dependedByKeys") or [])],
        })
    return {
        "found": True,
        "job": resolved,
        "location": location,
        "repo": repo,
        "asset_count": len(assets),
        "assets": assets,
    }


def get_run_history(job_name: str, limit: int = 20) -> dict[str, Any]:
    """Get recent runs for a job, with timing and status."""
    location, repo, resolved = _find_repo_for_job(job_name)
    if not location:
        return {"found": False, "runs": []}

    q = """
    query RunHistory($filter: RunsFilter!, $limit: Int!) {
      runsOrError(filter: $filter, limit: $limit) {
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
    """
    variables = {
        "filter": {"pipelineName": resolved},
        "limit": limit,
    }
    data = _gql(q, variables)
    runs_data = (data.get("runsOrError") or {}).get("results") or []

    runs = []
    durations = []
    statuses = {"SUCCESS": 0, "FAILURE": 0, "CANCELED": 0, "STARTED": 0}
    for r in runs_data:
        start = r.get("startTime")
        end = r.get("endTime")
        duration_s = (end - start) if (start and end) else None
        if duration_s and duration_s > 0:
            durations.append(duration_s)
        status = r.get("status", "UNKNOWN")
        statuses[status] = statuses.get(status, 0) + 1
        runs.append({
            "run_id": r.get("runId"),
            "status": status,
            "start_time": datetime.fromtimestamp(start, tz=timezone.utc).isoformat() if start else None,
            "end_time": datetime.fromtimestamp(end, tz=timezone.utc).isoformat() if end else None,
            "duration_s": round(duration_s, 1) if duration_s else None,
        })

    stats = {}
    if durations:
        stats = {
            "avg_duration_s": round(sum(durations) / len(durations), 1),
            "min_duration_s": round(min(durations), 1),
            "max_duration_s": round(max(durations), 1),
        }

    total = sum(statuses.values())
    success_rate = round(statuses.get("SUCCESS", 0) / total * 100, 1) if total > 0 else 0

    return {
        "found": True,
        "job": resolved,
        "run_count": len(runs),
        "runs": runs,
        "stats": stats,
        "success_rate": success_rate,
        "status_counts": statuses,
    }


def get_schedule(job_name: str) -> dict[str, Any]:
    """Get schedule config for a job."""
    location, repo, resolved = _find_repo_for_job(job_name)
    if not location:
        return {"found": False}

    q = """
    query Schedules($repositorySelector: RepositorySelector!) {
      schedulesOrError(repositorySelector: $repositorySelector) {
        ... on Schedules {
          results {
            name
            cronSchedule
            pipelineName
            scheduleState { status }
          }
        }
      }
    }
    """
    variables = {
        "repositorySelector": {
            "repositoryName": repo,
            "repositoryLocationName": location,
        }
    }
    data = _gql(q, variables)
    schedules_raw = (data.get("schedulesOrError") or {}).get("results") or []
    for s in schedules_raw:
        if s.get("pipelineName") == resolved:
            state = (s.get("scheduleState") or {}).get("status", "UNKNOWN")
            return {
                "found": True,
                "name": s.get("name"),
                "cron": s.get("cronSchedule"),
                "status": state,
                "job": resolved,
            }
    return {"found": False, "job": resolved, "note": "No schedule found for this job"}


def get_full_ops_intelligence(job_name: str) -> dict[str, Any]:
    """
    Combined ops intelligence: schedule + run history + assets.
    Single call for the report generator.
    """
    if not is_configured():
        return {"available": False, "error": "Dagster token not configured"}

    schedule = get_schedule(job_name)
    runs = get_run_history(job_name)
    assets = get_job_assets(job_name)

    return {
        "available": True,
        "job_found": runs.get("found", False) or assets.get("found", False),
        "schedule": schedule,
        "runs": runs,
        "assets": assets,
    }
