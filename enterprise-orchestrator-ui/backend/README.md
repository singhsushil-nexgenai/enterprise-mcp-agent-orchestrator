# Backend Service

FastAPI backend for enterprise orchestration.

## Responsibilities
- Receive and validate job requests.
- Persist jobs and state transitions.
- Trigger async execution workers.
- Store run logs and artifact references.
- Publish final artifacts to SharePoint (Phase 1) and Confluence (Phase 2).

## Current State
- Minimal API scaffold created.
- In-memory job store for local validation.
- Background task simulates worker execution.

## Next Steps
1. Replace in-memory store with PostgreSQL.
2. Replace background task with queue worker (Redis + Celery/RQ).
3. Add SharePoint publisher adapter.
4. Add retry policy and dead-letter handling.
5. Add approval workflow and audit endpoints.
