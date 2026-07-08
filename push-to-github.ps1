#!/usr/bin/env pwsh
# ============================================================
# push-to-github.ps1
# Run this ONCE from inside enterprise-mcp-agent-orchestrator\
# to create the GitHub repo and push all files.
#
# Prerequisites:
#   - git installed and in PATH
#   - GitHub CLI (gh) installed: winget install --id GitHub.cli
#     OR use HTTPS with a Personal Access Token
# ============================================================

$repoName  = "enterprise-mcp-agent-orchestrator"
$githubUser = "singhsushil-nexgenai"
$repoDir   = $PSScriptRoot   # the folder this script lives in

Set-Location $repoDir

# 1. Init git
git init
git checkout -b main

# 2. Stage everything
git add .

# 3. Commit
git commit -m "feat: initial commit - Enterprise MCP Agent Orchestrator

Multi-agent AI system for ETL pipeline intelligence reporting.
Built with GitHub Copilot Agent Mode + Model Context Protocol (MCP).
7 MCP servers | 6 skill agents | 1 master orchestrator"

# 4. Create GitHub repo via CLI (requires `gh auth login` first)
gh repo create "$githubUser/$repoName" `
    --public `
    --description "Production multi-agent AI orchestrator: GitHub Copilot Agent Mode + 7 MCP servers (Snowflake, Dagster, Monte Carlo, Confluence, Jira, Databricks). Automates ETL pipeline intelligence reporting." `
    --source . `
    --remote origin `
    --push

Write-Host ""
Write-Host "Done! Repo live at: https://github.com/$githubUser/$repoName"
