#!/usr/bin/env python
"""
Lightweight Confluence MCP server — stdio JSON-RPC 2.0.

Credential resolution order (first wins):
  1. ATLASSIAN_EMAIL + ATLASSIAN_TOKEN environment variables  (set via VS Code mcp.json ${input:...})
  2. ~/.atlassian/credentials.json file                       (legacy / fallback)

SSL certificate:
  DTV_CA_CERT env var  →  path to corporate_root_ca.pem
  (set automatically by mcp.json to %USERPROFILE%\\corporate_root_ca.pem)

Provides: confluence_search, confluence_get_page, confluence_get_spaces, confluence_get_page_children
"""
import sys
import json
import os
import re

import requests

# ── Credentials ────────────────────────────────────────────────────────────────
CONFLUENCE_URL = "https://[Company]-it.atlassian.net/wiki"

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
            f"[confluence-mcp] No credentials found.\n"
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
    url = CONFLUENCE_URL + path
    r = _session.get(url, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

# ── Tools ──────────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "confluence_search",
        "description": "Search Confluence pages using CQL (Confluence Query Language). Examples: 'text~\"cmpgn_lylt_offr_fct\"', 'space=CMPGN AND title~\"pipeline\"'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cql":   {"type": "string", "description": "CQL query string"},
                "limit": {"type": "integer", "description": "Max results (default 10, max 50)", "default": 10}
            },
            "required": ["cql"]
        }
    },
    {
        "name": "confluence_get_page",
        "description": "Get the full content of a Confluence page by its page ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Confluence page ID (numeric string)"}
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "confluence_get_spaces",
        "description": "List all Confluence spaces the user has access to",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max spaces to return (default 25)", "default": 25}
            }
        }
    },
    {
        "name": "confluence_get_page_children",
        "description": "List child pages of a given Confluence page",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Parent page ID"},
                "limit":   {"type": "integer", "description": "Max results (default 20)", "default": 20}
            },
            "required": ["page_id"]
        }
    }
]

# ── Tool handlers ──────────────────────────────────────────────────────────────
def confluence_search(args: dict) -> dict:
    cql   = args["cql"]
    limit = min(int(args.get("limit", 10)), 50)
    data  = _get("/rest/api/content/search", {"cql": cql, "limit": limit,
                                               "expand": "space,version,metadata.labels"})
    results = []
    for r in data.get("results", []):
        results.append({
            "id":            r["id"],
            "title":         r["title"],
            "type":          r["type"],
            "space":         r.get("space", {}).get("key", ""),
            "url":           f"{CONFLUENCE_URL}{r['_links'].get('webui', '')}",
            "last_modified": r.get("version", {}).get("when", ""),
            "excerpt":       r.get("excerpt", "")
        })
    return {"total": data.get("totalSize", len(results)), "results": results}


def confluence_get_page(args: dict) -> dict:
    page_id = args["page_id"]
    data = _get(f"/rest/api/content/{page_id}",
                {"expand": "body.storage,version,space,ancestors"})
    body_html = data.get("body", {}).get("storage", {}).get("value", "")
    body_text = re.sub(r"<[^>]+>", " ", body_html)
    body_text = re.sub(r"\s{2,}", " ", body_text).strip()
    return {
        "id":       data["id"],
        "title":    data["title"],
        "space":    data.get("space", {}).get("key", ""),
        "url":      f"{CONFLUENCE_URL}{data['_links'].get('webui', '')}",
        "version":  data.get("version", {}).get("number", ""),
        "modified": data.get("version", {}).get("when", ""),
        "body":     body_text[:8000]
    }


def confluence_get_spaces(args: dict) -> dict:
    limit = min(int(args.get("limit", 25)), 50)
    data  = _get("/rest/api/space", {"limit": limit, "type": "global"})
    spaces = [{"key": s["key"], "name": s["name"],
               "url": f"{CONFLUENCE_URL}{s['_links'].get('webui', '')}"}
              for s in data.get("results", [])]
    return {"total": data.get("size", len(spaces)), "spaces": spaces}


def confluence_get_page_children(args: dict) -> dict:
    page_id = args["page_id"]
    limit   = min(int(args.get("limit", 20)), 50)
    data    = _get(f"/rest/api/content/{page_id}/child/page", {"limit": limit})
    children = [{"id": p["id"], "title": p["title"],
                 "url": f"{CONFLUENCE_URL}{p['_links'].get('webui', '')}"}
                for p in data.get("results", [])]
    return {"total": data.get("size", len(children)), "children": children}


HANDLERS = {
    "confluence_search":           confluence_search,
    "confluence_get_page":         confluence_get_page,
    "confluence_get_spaces":       confluence_get_spaces,
    "confluence_get_page_children":confluence_get_page_children,
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
            "serverInfo": {"name": "confluence-mcp", "version": "1.0.0"}
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
