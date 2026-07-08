#!/usr/bin/env python
"""
Lightweight Dagster Cloud MCP server — stdio JSON-RPC 2.0.

Credential resolution order (first wins):
  1. DAGSTER_TOKEN environment variable  (set via VS Code mcp.json ${input:dagsterToken})
  2. ~/.dagster/token file               (legacy / fallback)

SSL certificate:
  DTV_CA_CERT env var  →  path to corporate_root_ca.pem
  (set automatically by mcp.json to %USERPROFILE%\\corporate_root_ca.pem)

Provides: dagster_list_jobs, dagster_get_job_assets, dagster_get_asset_deps, dagster_run_graphql
"""
import sys
import json
import os
import traceback
import requests

# ── Config ─────────────────────────────────────────────────────────────────────

DAGSTER_URL = "https://[Company].dagster.cloud/prod/graphql"

# Cert — prefer env var so it works on any machine
DTV_CA = os.environ.get("DTV_CA_CERT") or os.path.join(os.path.expanduser("~"), "corporate_root_ca.pem")

# Token — env var first, then file
TOKEN = os.environ.get("DAGSTER_TOKEN", "").strip()
if not TOKEN:
    _token_file = os.path.join(os.path.expanduser("~"), ".dagster", "token")
    try:
        TOKEN = open(_token_file).read().strip()
    except FileNotFoundError:
        sys.stderr.write(
            f"[dagster-mcp] No token found.\n"
            f"  Set DAGSTER_TOKEN env var in mcp.json, or create {_token_file}\n"
        )
        sys.exit(1)

_session = requests.Session()
_session.verify = DTV_CA
_session.headers.update({
    "Dagster-Cloud-Api-Token": TOKEN,
    "Content-Type": "application/json"
})

# ── GraphQL helper ─────────────────────────────────────────────────────────────
def gql(query: str, variables: dict = None) -> dict:
    r = _session.post(DAGSTER_URL, json={"query": query, "variables": variables or {}}, timeout=60)
    r.raise_for_status()
    d = r.json()
    if d.get("errors"):
        raise Exception(str(d["errors"]))
    return d.get("data", {})

# ── Repo cache ─────────────────────────────────────────────────────────────────
_REPOS = None

def _get_repos():
    global _REPOS
    if _REPOS is not None:
        return _REPOS
    q = """
    { workspaceOrError { ... on Workspace { locationEntries {
      name
      locationOrLoadError { __typename
        ... on RepositoryLocation { repositories { name pipelines { name } } }
      }
    } } } }
    """
    data = gql(q)
    _REPOS = []
    for entry in (data.get("workspaceOrError") or {}).get("locationEntries", []):
        loc_name = entry["name"]
        loc = entry.get("locationOrLoadError") or {}
        for repo in loc.get("repositories") or []:
            jobs = [p["name"] for p in repo.get("pipelines") or []]
            _REPOS.append({"location": loc_name, "repo": repo["name"], "jobs": jobs})
    return _REPOS

def _find_repo_for_job(job_name: str):
    for entry in _get_repos():
        if job_name in entry["jobs"]:
            return entry["location"], entry["repo"], job_name
    prefixed = f"cmpgn_dp_{job_name}"
    for entry in _get_repos():
        if prefixed in entry["jobs"]:
            return entry["location"], entry["repo"], prefixed
    return None, None, None

def _key_str(key_obj) -> str:
    path = key_obj.get("path") if isinstance(key_obj, dict) else key_obj
    if isinstance(path, list):
        return "/".join(path)
    return str(path)

# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "dagster_list_jobs",
        "description": "List all Dagster jobs/pipelines across all code locations. Optionally filter by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Optional keyword to filter job names"}
            }
        }
    },
    {
        "name": "dagster_get_job_assets",
        "description": "Get all software-defined assets in a Dagster job, including their upstream and downstream lineage.",
        "inputSchema": {
            "type": "object",
            "required": ["job_name"],
            "properties": {
                "job_name": {"type": "string", "description": "Dagster job/pipeline name, e.g. cmpgn_api_dtl_stg_ddly"}
            }
        }
    },
    {
        "name": "dagster_get_asset_deps",
        "description": "Get upstream dependencies and downstream consumers for a specific asset key across the entire asset graph.",
        "inputSchema": {
            "type": "object",
            "required": ["asset_key"],
            "properties": {
                "asset_key": {"type": "string", "description": "Asset key path, slash-separated if multi-part"},
                "depth": {"type": "integer", "description": "How many hops upstream/downstream to traverse (default 3)", "default": 3}
            }
        }
    },
    {
        "name": "dagster_run_graphql",
        "description": "Run a raw GraphQL query against the Dagster Cloud API.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "GraphQL query string"},
                "variables": {"type": "object", "description": "Optional variables dict"}
            }
        }
    }
]

# ── Tool handlers ──────────────────────────────────────────────────────────────
def dagster_list_jobs(args: dict) -> dict:
    search = (args.get("search") or "").lower()
    repos = _get_repos()
    results = []
    for entry in repos:
        for job in entry["jobs"]:
            if not search or search in job.lower():
                results.append({"job": job, "location": entry["location"], "repo": entry["repo"]})
    return {"total": len(results), "jobs": results[:200]}


def dagster_get_job_assets(args: dict) -> dict:
    job_name = args["job_name"]
    location, repo, resolved_name = _find_repo_for_job(job_name)
    if not location:
        return {"error": f"Job '{job_name}' not found in any code location", "assets": []}
    q = """
    query JobAssets($pipeline: PipelineSelector!) {
      assetNodes(pipeline: $pipeline) {
        id assetKey { path } opNames groupName computeKind description
        dependencyKeys { path } dependedByKeys { path }
      }
    }
    """
    variables = {"pipeline": {"pipelineName": resolved_name, "repositoryName": repo, "repositoryLocationName": location}}
    data = gql(q, variables)
    nodes = data.get("assetNodes") or []
    assets = []
    for n in nodes:
        assets.append({
            "key":          _key_str(n["assetKey"]),
            "op_names":     n.get("opNames") or [],
            "group":        n.get("groupName"),
            "compute_kind": n.get("computeKind"),
            "description":  n.get("description"),
            "upstream":     [_key_str(d) for d in (n.get("dependencyKeys") or [])],
            "downstream":   [_key_str(d) for d in (n.get("dependedByKeys") or [])],
        })
    return {"job": resolved_name, "location": location, "repo": repo, "asset_count": len(assets), "assets": assets}


def dagster_get_asset_deps(args: dict) -> dict:
    key_str = args["asset_key"]
    depth = int(args.get("depth", 3))
    key_path = key_str.split("/")
    q = """
    query AssetDeps($assetKey: AssetKeyInput!) {
      assetNodeOrError(assetKey: $assetKey) {
        __typename
        ... on AssetNode {
          id assetKey { path } groupName computeKind description
          dependencyKeys { path } dependedByKeys { path }
        }
      }
    }
    """
    visited = set()
    graph = {}

    def fetch(path_list, remaining_depth):
        k = "/".join(path_list)
        if k in visited or remaining_depth <= 0:
            return
        visited.add(k)
        try:
            data = gql(q, {"assetKey": {"path": path_list}})
            node = (data.get("assetNodeOrError") or {})
            if node.get("__typename") != "AssetNode":
                return
            upstream   = [_key_str(d) for d in (node.get("dependencyKeys") or [])]
            downstream = [_key_str(d) for d in (node.get("dependedByKeys") or [])]
            graph[k] = {"key": k, "group": node.get("groupName"), "compute_kind": node.get("computeKind"),
                        "upstream": upstream, "downstream": downstream}
            for u in upstream:
                fetch(u.split("/"), remaining_depth - 1)
            for d in downstream:
                fetch(d.split("/"), remaining_depth - 1)
        except Exception:
            pass

    fetch(key_path, depth)
    return {"root": key_str, "depth": depth, "node_count": len(graph), "nodes": list(graph.values())}


def dagster_run_graphql(args: dict) -> dict:
    data = gql(args["query"], args.get("variables") or {})
    return {"result": data}


HANDLERS = {
    "dagster_list_jobs":      dagster_list_jobs,
    "dagster_get_job_assets": dagster_get_job_assets,
    "dagster_get_asset_deps": dagster_get_asset_deps,
    "dagster_run_graphql":    dagster_run_graphql,
}

# ── JSON-RPC helpers ───────────────────────────────────────────────────────────
def _write(obj):
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()

def _ok(id_, result):
    _write({"jsonrpc": "2.0", "id": id_, "result": result})

def _err(id_, code, msg):
    _write({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}})

# ── MCP protocol loop ──────────────────────────────────────────────────────────
def handle(req):
    method = req.get("method", "")
    id_    = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        _ok(id_, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "dagster-mcp", "version": "1.0.0"}})
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
