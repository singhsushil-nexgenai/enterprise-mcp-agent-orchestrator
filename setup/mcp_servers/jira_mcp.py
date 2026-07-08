#!/usr/bin/env python
"""
Lightweight Jira MCP server — stdio JSON-RPC 2.0.

Credential resolution order (first wins):
  1. ATLASSIAN_EMAIL + ATLASSIAN_TOKEN environment variables  (set via VS Code mcp.json ${input:...})
  2. ~/.atlassian/credentials.json file                       (legacy / fallback)

SSL certificate:
  DTV_CA_CERT env var  →  path to corporate_root_ca.pem
  (set automatically by mcp.json to %USERPROFILE%\\corporate_root_ca.pem)

Provides: jira_search, jira_get_issue, jira_list_projects, jira_get_issue_comments, jira_get_sprint_issues
"""
import sys
import json
import os
import re

import requests

# ── Credentials ────────────────────────────────────────────────────────────────
JIRA_URL = "https://[Company]-it.atlassian.net"

# Env vars first, then file fallback
_email = os.environ.get("ATLASSIAN_EMAIL", "").strip()
_token = os.environ.get("ATLASSIAN_TOKEN", "").strip()

if not (_email and _token):
    _creds_file = os.path.join(os.path.expanduser("~"), ".atlassian", "credentials.json")
    try:
        with open(_creds_file, encoding="utf-8-sig") as f:
            _creds = json.load(f)
        _email = _creds.get("email", "")
        _token = _creds.get("token", "")
    except FileNotFoundError:
        sys.stderr.write(
            f"[jira-mcp] No credentials found.\n"
            f"  Set ATLASSIAN_EMAIL + ATLASSIAN_TOKEN env vars in mcp.json, or create {_creds_file}\n"
        )
        sys.exit(1)

_AUTH = (_email, _token)

# ── HTTP session ───────────────────────────────────────────────────────────────
DTV_CA = os.environ.get("DTV_CA_CERT") or os.path.join(os.path.expanduser("~"), "corporate_root_ca.pem")

_session = requests.Session()
_session.auth   = _AUTH
_session.verify = DTV_CA
_session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

def _get(path: str, params: dict = None) -> dict:
    r = _session.get(JIRA_URL + path, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

# ── Tools ──────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "jira_search",
        "description": "Search Jira issues using JQL (Jira Query Language). Examples: 'project=CMPGN AND status=\"In Progress\"', 'assignee=currentUser() AND sprint in openSprints()'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql":    {"type": "string", "description": "JQL query string"},
                "limit":  {"type": "integer", "description": "Max results (default 20, max 50)", "default": 20},
                "fields": {"type": "string", "description": "Comma-separated fields to return (default: summary,status,assignee,priority,issuetype,created,updated,labels,components)"}
            },
            "required": ["jql"]
        }
    },
    {
        "name": "jira_get_issue",
        "description": "Get full details of a Jira issue by key (e.g. CMPGN-123)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Jira issue key (e.g. PROJ-123)"}
            },
            "required": ["issue_key"]
        }
    },
    {
        "name": "jira_list_projects",
        "description": "List all Jira projects the user has access to",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search string to filter projects by name or key"},
                "limit": {"type": "integer", "description": "Max results (default 50)", "default": 50}
            }
        }
    },
    {
        "name": "jira_get_issue_comments",
        "description": "Get comments on a Jira issue",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {"type": "string", "description": "Jira issue key"},
                "limit":     {"type": "integer", "description": "Max comments to return (default 10)", "default": 10}
            },
            "required": ["issue_key"]
        }
    },
    {
        "name": "jira_get_sprint_issues",
        "description": "Get issues in the active sprint for a given board/project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Jira project key (e.g. CMPGN)"},
                "limit":   {"type": "integer", "description": "Max issues (default 50)", "default": 50}
            },
            "required": ["project"]
        }
    }
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _strip_adf(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        t = node.get("type", "")
        text = node.get("text", "")
        content = node.get("content", [])
        parts = [text] + [_strip_adf(c) for c in content]
        sep = "\n" if t in ("paragraph", "heading", "bulletList", "orderedList", "listItem", "rule") else " "
        return sep.join(p for p in parts if p)
    if isinstance(node, list):
        return " ".join(_strip_adf(c) for c in node)
    return ""

def _fmt_issue(issue: dict) -> dict:
    f = issue.get("fields", {})
    desc_raw = f.get("description")
    if isinstance(desc_raw, dict):
        description = _strip_adf(desc_raw)[:3000]
    else:
        description = str(desc_raw or "")[:3000]
    return {
        "key":         issue["key"],
        "summary":     f.get("summary", ""),
        "status":      f.get("status", {}).get("name", ""),
        "type":        f.get("issuetype", {}).get("name", ""),
        "priority":    (f.get("priority") or {}).get("name", ""),
        "assignee":    (f.get("assignee") or {}).get("displayName", "Unassigned"),
        "reporter":    (f.get("reporter") or {}).get("displayName", ""),
        "created":     f.get("created", ""),
        "updated":     f.get("updated", ""),
        "labels":      f.get("labels", []),
        "components":  [c["name"] for c in f.get("components", [])],
        "description": description,
        "url":         f"{JIRA_URL}/browse/{issue['key']}"
    }

# ── Tool handlers ──────────────────────────────────────────────────────────────
def _search(jql: str, limit: int, fields: str) -> dict:
    params = {"jql": jql, "maxResults": limit, "fields": fields}
    try:
        return _get("/rest/api/3/search/jql", params)
    except Exception:
        return _get("/rest/api/3/search", params)


def jira_search(args: dict) -> dict:
    jql    = args["jql"]
    limit  = min(int(args.get("limit", 20)), 50)
    fields = args.get("fields", "summary,status,assignee,priority,issuetype,created,updated,labels,components")
    data   = _search(jql, limit, fields)
    issues = [_fmt_issue(i) for i in data.get("issues", [])]
    return {"total": data.get("total", len(issues)), "returned": len(issues), "issues": issues}


def jira_get_issue(args: dict) -> dict:
    key  = args["issue_key"].upper()
    data = _get(f"/rest/api/3/issue/{key}")
    return _fmt_issue(data)


def jira_list_projects(args: dict) -> dict:
    query = args.get("query", "")
    limit = min(int(args.get("limit", 50)), 100)
    params = {"maxResults": limit, "orderBy": "name"}
    if query:
        params["query"] = query
    data = _get("/rest/api/3/project/search", params)
    projects = [{"key": p["key"], "name": p["name"], "type": p.get("projectTypeKey", ""),
                 "lead": (p.get("lead") or {}).get("displayName", "")}
                for p in data.get("values", [])]
    return {"total": data.get("total", len(projects)), "projects": projects}


def jira_get_issue_comments(args: dict) -> dict:
    key   = args["issue_key"].upper()
    limit = min(int(args.get("limit", 10)), 50)
    data  = _get(f"/rest/api/3/issue/{key}/comment", {"maxResults": limit, "orderBy": "-created"})
    comments = []
    for c in data.get("comments", []):
        body_raw = c.get("body")
        body = _strip_adf(body_raw)[:1000] if isinstance(body_raw, dict) else str(body_raw or "")[:1000]
        comments.append({
            "author":  (c.get("author") or {}).get("displayName", ""),
            "created": c.get("created", ""),
            "body":    body
        })
    return {"total": data.get("total", len(comments)), "comments": comments}


def jira_get_sprint_issues(args: dict) -> dict:
    project = args["project"].upper()
    limit   = min(int(args.get("limit", 50)), 100)
    fields  = "summary,status,assignee,priority,issuetype,updated"
    try:
        jql  = f"project={project} AND sprint in openSprints() ORDER BY updated DESC"
        data = _search(jql, limit, fields)
    except Exception:
        jql  = f"project={project} AND statusCategory != Done ORDER BY updated DESC"
        data = _search(jql, limit, fields)
    issues = [_fmt_issue(i) for i in data.get("issues", [])]
    return {"total": data.get("total", len(issues)), "returned": len(issues), "issues": issues}


HANDLERS = {
    "jira_search":             jira_search,
    "jira_get_issue":          jira_get_issue,
    "jira_list_projects":      jira_list_projects,
    "jira_get_issue_comments": jira_get_issue_comments,
    "jira_get_sprint_issues":  jira_get_sprint_issues,
}

# ── JSON-RPC 2.0 stdio loop ────────────────────────────────────────────────────
def send(obj: dict):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def handle(line: str):
    try:
        req = json.loads(line)
    except json.JSONDecodeError:
        return
    rid    = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "jira-mcp", "version": "1.0.0"}
        }})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        fn   = HANDLERS.get(name)
        if not fn:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown tool: {name}"}})
            return
        try:
            result = fn(args)
            send({"jsonrpc": "2.0", "id": rid,
                  "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}})
        except Exception as e:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}})
    else:
        if rid is not None:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}})

def main():
    for line in sys.stdin:
        line = line.strip()
        if line:
            handle(line)

if __name__ == "__main__":
    main()
