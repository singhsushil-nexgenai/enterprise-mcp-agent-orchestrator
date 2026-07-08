# Enterprise Orchestrator UI

This is a separate application for URL-based orchestration and publishing.

Scope boundary:
- Do not modify existing mcp-orchestrator assets.
- Existing agent and skill files are reference-only.
- All new implementation lives under this folder.

## Goals
- Submit orchestration jobs via web UI/API.
- Run jobs asynchronously with queue and retries.
- Track status, logs, and audit events.
- Publish output to SharePoint first, Confluence next.

## Quick Start (Backend scaffold)
1. Open a terminal in `enterprise-orchestrator-ui/backend`.
2. Create and activate a Python virtual environment.
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Run API:
   - `uvicorn app.main:app --reload --port 8080`
5. Open API docs:
   - `http://localhost:8080/docs`

## Folder Layout
- `docs/` architecture and design notes
- `backend/` API, orchestration runtime, worker code
- `frontend/` web UI app (to be added)
- `infra/` deployment and environment templates
