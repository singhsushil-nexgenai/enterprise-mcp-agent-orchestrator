# Architecture (Phase 1 to Phase 2)

## Phase 1 (MVP)
- Web/API receives job request.
- Job is persisted with status `submitted`.
- Worker executes orchestration stages asynchronously.
- Results and logs are persisted.
- SharePoint publisher uploads final artifact and stores URL.

## Phase 2 (Enterprise)
- Add approval workflow before execution.
- Add SSO and role-based access.
- Add Confluence publisher.
- Add full audit dashboards and alerting.

## Core Components
- API service: FastAPI
- Queue and worker: initial in-process scaffold, replace with Redis queue (Celery/RQ)
- Database: PostgreSQL (jobs, attempts, events, artifacts)
- Publishers: SharePoint adapter first, Confluence adapter second
- Frontend: React/Next.js (submit, status, logs, artifacts)

## Non-Negotiable Boundary
This app must not edit any existing mcp-orchestrator implementation files.
