"""
GitHub REST API client — reads job configs and SQL files from YOUR-ORG repos.
Falls back to local workspace if GitHub API is unavailable or returns 403.
"""
import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app import config

logger = logging.getLogger(__name__)

# Repo alias → (org/repo, branch)
REPO_MAP = {
    "cmpgn": ("YOUR-ORG/etl-campaign-analytics", "prod"),
    "uma": ("YOUR-ORG/etl-unified-marketing", "prod"),
    "rvnu": ("YOUR-ORG/etl-revenue-analytics", "prod"),
}

# Local workspace root — the repo clone that contains job folders
_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]  # backend/app/services → app → backend → enterprise-orchestrator-ui → repo root


def _headers() -> dict:
    token = config.GITHUB_TOKEN
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def _get(path: str, timeout: float = 30) -> dict | list | None:
    """GET from GitHub API. Returns parsed JSON or None on error."""
    url = f"{config.GITHUB_API_URL}{path}"
    try:
        r = httpx.get(url, headers=_headers(), timeout=timeout, verify=False)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("GitHub API error for %s: %s", path, e)
        return None


def is_configured() -> bool:
    return bool(config.GITHUB_TOKEN)


def resolve_repo(job_name: str, repo_hint: str | None = None) -> tuple[str, str, str] | None:
    """
    Find which repo contains a job folder.
    Returns (repo_alias, org/repo, branch) or None.
    """
    if repo_hint and repo_hint in REPO_MAP:
        org_repo, branch = REPO_MAP[repo_hint]
        # Verify the folder exists
        data = _get(f"/repos/{org_repo}/contents/{job_name}?ref={branch}")
        if data:
            return repo_hint, org_repo, branch

    # Search across all repos
    for alias, (org_repo, branch) in REPO_MAP.items():
        data = _get(f"/repos/{org_repo}/contents/{job_name}?ref={branch}")
        if data:
            return alias, org_repo, branch
    return None


def get_file_content(org_repo: str, file_path: str, branch: str = "prod") -> str | None:
    """Download a single file's content from GitHub."""
    data = _get(f"/repos/{org_repo}/contents/{file_path}?ref={branch}")
    if not data or not isinstance(data, dict):
        return None
    content_b64 = data.get("content", "")
    try:
        return base64.b64decode(content_b64).decode("utf-8")
    except Exception:
        return None


def get_job_config(job_name: str, repo_hint: str | None = None) -> dict[str, Any]:
    """Read job JSON config from GitHub."""
    resolved = resolve_repo(job_name, repo_hint)
    if not resolved:
        return {}
    alias, org_repo, branch = resolved
    content = get_file_content(org_repo, f"{job_name}/{job_name}.json", branch)
    if not content:
        return {}
    import json
    try:
        return json.loads(content)
    except Exception:
        return {}


def list_sql_files(job_name: str, repo_hint: str | None = None) -> list[tuple[str, str]]:
    """Return list of (filename, content) for all SQL files in a job folder."""
    resolved = resolve_repo(job_name, repo_hint)
    if not resolved:
        return []
    alias, org_repo, branch = resolved
    data = _get(f"/repos/{org_repo}/contents/{job_name}?ref={branch}")
    if not data or not isinstance(data, list):
        return []

    sql_files = []
    for item in data:
        name = item.get("name", "")
        if name.endswith(".sql"):
            content = get_file_content(org_repo, f"{job_name}/{name}", branch)
            if content:
                sql_files.append((name, content))
    return sorted(sql_files, key=lambda x: x[0])


def get_job_context(job_name: str, repo_hint: str | None = None) -> dict[str, Any]:
    """
    Full job context: config + SQL files + metadata.
    Tries GitHub API first, falls back to local workspace.
    Returns a dict consumed by report generator.
    """
    # Try GitHub API if token is configured
    if is_configured():
        resolved = resolve_repo(job_name, repo_hint)
        if resolved:
            alias, org_repo, branch = resolved
            job_config = get_job_config(job_name, alias)
            sql_files = list_sql_files(job_name, alias)
            if job_config:  # GitHub succeeded
                return {
                    "source": "github",
                    "repo_alias": alias,
                    "org_repo": org_repo,
                    "branch": branch,
                    "config": job_config,
                    "sql_files": sql_files,
                    "sql_count": len(sql_files),
                }
        logger.info("GitHub API failed for '%s', trying local fallback", job_name)

    # Fallback: read from local workspace
    return _get_job_context_local(job_name, repo_hint)


def _get_job_context_local(job_name: str, repo_hint: str | None = None) -> dict[str, Any]:
    """Read job config and SQL files from the local workspace clone."""
    job_folder = _WORKSPACE_ROOT / job_name
    json_file = job_folder / f"{job_name}.json"

    if not json_file.exists():
        # Search for partial match
        for d in _WORKSPACE_ROOT.iterdir():
            if d.is_dir() and job_name in d.name:
                candidate = d / f"{d.name}.json"
                if candidate.exists():
                    job_folder = d
                    json_file = candidate
                    job_name = d.name
                    break
        else:
            return {"source": "local", "error": f"Job '{job_name}' not found in workspace"}

    # Read config
    try:
        job_config = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"source": "local", "error": f"Error reading config: {e}"}

    # Read SQL files
    sql_files = []
    for f in sorted(job_folder.glob("*.sql")):
        try:
            content = f.read_text(encoding="utf-8")
            sql_files.append((f.name, content))
        except Exception:
            sql_files.append((f.name, f"-- Error reading file"))

    # Determine repo alias
    alias = repo_hint or "cmpgn"
    org_repo = REPO_MAP.get(alias, REPO_MAP["cmpgn"])[0]

    logger.info("Local fallback: loaded %s — %d SQL files", job_name, len(sql_files))
    return {
        "source": "local",
        "repo_alias": alias,
        "org_repo": org_repo,
        "branch": "prod",
        "config": job_config,
        "sql_files": sql_files,
        "sql_count": len(sql_files),
    }
