# AGENTS.md

## Purpose
This workspace is an MCP orchestration repo for CMPGN/UMA/RVNU ETL analysis and reporting, not a traditional build/test application.

Use these docs first:
- Setup and environment: [setup/README.md](setup/README.md)
- MCP server configuration: [.vscode/mcp.json](.vscode/mcp.json)
- Master orchestrator behavior: [.github/agents/mcp-orchestrator.md](.github/agents/mcp-orchestrator.md)
- Batch optimizer/report agent: [.github/agents/agent.md](.github/agents/agent.md)

## Working Model
- Treat GitHub MCP as source-of-truth for job configs and SQL in YOUR-ORG repos.
- Treat local job folders as working/output artifacts unless the task explicitly targets local files.
- Prefer repo alias mapping when relevant:
  - `cmpgn` -> `YOUR-ORG/etl-campaign-analytics` (`prod`)
  - `uma` -> `YOUR-ORG/etl-unified-marketing` (`prod`)
  - `rvnu` -> `YOUR-ORG/etl-revenue-analytics` (`prod`)

## Critical Conventions
- Never use generated `.html` outputs as input evidence for analysis; regenerate from source when needed.
- For merged MCP reports, include full optimized SQL content (collapsible blocks) and use JS `textContent` to avoid HTML escaping issues.
- Preserve fixed batch semantics where documented (batch size 10 for SQL optimization/report workflows).
- Keep report/output path derivation deterministic from `job_name` and repo alias.

## Common Tasks
- Full orchestration report: use `mcp-orchestrator` agent with `job_name=...` or `table_name=...`.
- Batch SQL optimization + HTML reporting: use `Agent1`.
- Single capability skills (invoke directly when needed):
  - Resolver: [.github/skills/job-resolver/SKILL.md](.github/skills/job-resolver/SKILL.md)
  - ETL lineage: [.github/skills/etl-lineage-composer/SKILL.md](.github/skills/etl-lineage-composer/SKILL.md)
  - SQL optimization: [.github/skills/cmpgn-sql-optimization/SKILL.md](.github/skills/cmpgn-sql-optimization/SKILL.md)
  - Dagster ops: [.github/skills/dagster-ops-intelligence/SKILL.md](.github/skills/dagster-ops-intelligence/SKILL.md)
  - Monte Carlo alerts: [.github/skills/mc-table-alerts/SKILL.md](.github/skills/mc-table-alerts/SKILL.md)
  - HTML report composer: [.github/skills/cmpgn-html-report/SKILL.md](.github/skills/cmpgn-html-report/SKILL.md)
  - Dagster lineage: [.github/skills/dagster-job-lineage/SKILL.md](.github/skills/dagster-job-lineage/SKILL.md)

## Safety and Secrets
- Never hardcode tokens/passwords in files or commits.
- Prefer environment/input prompts configured in MCP settings.
- If you detect secrets in tracked files, stop and ask for direction before modifying security-sensitive configuration.
