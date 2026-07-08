# MCP Orchestrator — Team Setup Guide

Share the entire `setup/` folder with teammates. Everything they need is here.

---

## What Is mcp-orchestrator?

A GitHub Copilot agent that, given a single job name (or Snowflake table name), automatically:
1. Resolves the job across three YOUR-ORG repos (CMPGN / UMA / RVNU)
2. Composes a full ETL lineage HTML document
3. Optimizes every SQL file against 20 Snowflake best-practice parameters
4. Pulls Dagster schedule, run history, and SLA stats
5. Pulls Monte Carlo monitor and incident data
6. Merges everything into one self-contained HTML report

**No tokens are stored in any file.** VS Code prompts for each token the first time you use the agent in a new session.

---

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| Windows 10/11 | — | Scripts are PowerShell-based |
| [Python](https://python.org) | 3.10+ | Must be in `PATH` |
| [Node.js + npm](https://nodejs.org) | Node 18+ | Required for Snowflake MCP |
| [VS Code](https://code.visualstudio.com) | 1.90+ | |
| [GitHub Copilot extension](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot-chat) | Latest | Chat + Agent mode required |
| GitHub access | — | Must be a member of the **YOUR-ORG** GitHub org |
| Corporate SSL cert | — | `corporate_root_ca.pem` — get from a colleague or IT |

---

## Step 1 — Clone the Repository

```powershell
git clone https://github.com/YOUR-ORG/etl-campaign-analytics.git
cd etl-campaign-analytics
```

> The `.github/agents/` and `.github/skills/` folders that power the orchestrator
> are already inside this repo — no extra cloning needed.

---

## Step 2 — Run the Install Script

Open PowerShell **in the repo root** and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup\install.ps1
```

The script will:
- Verify Python and Node/npm
- Install Python packages (`pycarlo`, `requests`)
- Install `snowflake-mcp` globally via npm
- Copy the four Python MCP server scripts to your `%USERPROFILE%` home directory
- **Deploy all 7 skills and 2 agent files** from `setup/.github/` → `.github/` at the repo root, and patch the hardcoded paths to match your machine
- Copy `.vscode/mcp.json` template (only if it doesn't already exist)
- Copy `.vscode/settings.json` so VS Code Copilot discovers agents and skills
- Create output folders: `<parent-of-repo>\CMPGN\`, `UMA\`, `RVNU\`

---

## Step 3 — Place the DTV SSL Certificate

Copy `corporate_root_ca.pem` to your home directory:

```
%USERPROFILE%\corporate_root_ca.pem
```

Get this file from a colleague or your IT/security team.

---

## Step 4 — Fill In the Snowflake Connection Details

Open `.vscode\mcp.json` and replace the five `<YOUR_...>` placeholders:

| Placeholder | What to put |
|---|---|
| `<YOUR_SNOWFLAKE_ACCOUNT>` | e.g. `<YOUR-SNOWFLAKE-ACCOUNT>` |
| `<YOUR_SNOWFLAKE_USERNAME>` | e.g. `JOHN.DOE` |
| `<YOUR_SNOWFLAKE_ROLE>` | e.g. `ANALYST` or `ACCOUNTADMIN` |
| `<YOUR_SNOWFLAKE_WAREHOUSE>` | e.g. `COMPUTE_WH` |
| `<YOUR_SNOWFLAKE_DATABASE>` | e.g. `UMA` or `CMPGN` |

> Everything else (passwords, tokens, API keys) is handled via VS Code prompts — never stored in any file.

---

## Step 5 — Open in VS Code & Test

```powershell
code .
```

1. Press `Ctrl+Alt+I` to open **GitHub Copilot Chat**
2. Switch to **Agent mode**
3. Select the **mcp-orchestrator** agent from the dropdown
4. Type a prompt:
   ```
   job_name=cmpgn_api_dtl_stg_ddly repo=cmpgn
   ```

VS Code will prompt you for each credential the first time:

| Prompt | Where to get it |
|---|---|
| Snowflake password | Your Snowflake account password |
| Dagster Cloud API token | [[Company].dagster.cloud](https://[Company].dagster.cloud) → Settings → User tokens → Create |
| Atlassian email | Your [Company] email address |
| Atlassian API token | [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) → Create API token |
| Monte Carlo API Key ID | Monte Carlo → Settings → API → Generate key |
| Monte Carlo API Secret | (same Generate key dialog as above) |
| Databricks PAT | Databricks → User Settings → Access Tokens → Generate (optional) |

> Credentials are held in VS Code's secure session memory only and are never written to disk.

---

## File Reference

```
setup/                              ← Share this entire folder with teammates
├── README.md                       ← This file
├── install.ps1                     ← One-shot setup script (run this first)
├── mcp_servers/
│   ├── requirements.txt            ← Python dependencies (requests, pycarlo)
│   ├── monte_carlo_mcp.py          ← Monte Carlo MCP server
│   ├── dagster_mcp.py              ← Dagster Cloud MCP server
│   ├── jira_mcp.py                 ← Jira MCP server
│   └── confluence_mcp.py           ← Confluence MCP server
├── vscode/
│   ├── mcp.json                    ← Template for .vscode/mcp.json (fill in Snowflake details)
│   └── settings.json               ← Copilot agent/skill discovery settings
└── .github/                        ← Agents + Skills payload (deployed by install.ps1)
    ├── agents/
    │   ├── mcp-orchestrator.md     ← Master orchestrator agent
    │   └── agent.md                ← Agent1 (batch SQL optimization)
    └── skills/
        ├── job-resolver/SKILL.md
        ├── etl-lineage-composer/SKILL.md
        ├── cmpgn-sql-optimization/SKILL.md
        ├── dagster-ops-intelligence/SKILL.md
        ├── mc-table-alerts/SKILL.md
        ├── cmpgn-html-report/SKILL.md
        └── dagster-job-lineage/SKILL.md
```

---

## How Token Prompting Works

Each Python MCP server script checks **environment variables first**, then falls back to local credential files:

| Server | Env vars (set by VS Code `${input:...}`) | File fallback |
|---|---|---|
| Snowflake | `SNOWFLAKE_PASSWORD` | — |
| Dagster | `DAGSTER_TOKEN` | `~/.dagster/token` |
| Jira | `ATLASSIAN_EMAIL` + `ATLASSIAN_TOKEN` | `~/.atlassian/credentials.json` |
| Confluence | `ATLASSIAN_EMAIL` + `ATLASSIAN_TOKEN` | `~/.atlassian/credentials.json` |
| Monte Carlo | `MCD_API_KEY` + `MCD_API_SECRET` | `~/.mcd/profiles.ini` |
| GitHub | VS Code built-in OAuth | — |

If you already have the credential files from a previous setup, the servers will continue to work without prompts.
