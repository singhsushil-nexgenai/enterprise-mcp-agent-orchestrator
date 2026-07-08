# Infrastructure (Planned)

Start simple and isolated:
- One application host for backend API
- One managed database for job state
- Optional Redis for queue when worker volume grows

Environment tiers:
- dev
- test
- prod

Operational baseline:
- Structured logs with correlation ID per job
- Health endpoint checks
- Daily backup for job state database
- Secret storage via managed secret vault
