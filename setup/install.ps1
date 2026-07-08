#Requires -Version 5.1
<#
.SYNOPSIS
    MCP Orchestrator — one-shot setup script for Windows.

.DESCRIPTION
    Installs all prerequisites, copies MCP server scripts, and creates the
    .vscode/mcp.json template and settings.json so VS Code can discover the
    mcp-orchestrator agent and its skills.

    Credentials are NOT stored here. VS Code will prompt you to enter each
    token/password the first time you use the agent in a session.

.USAGE
    Open PowerShell in the repo root and run:
        Set-ExecutionPolicy -Scope Process Bypass
        .\setup\install.ps1
#>

$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ScriptDir
$HomeDir    = $env:USERPROFILE

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MCP Orchestrator — Setup Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ───────────────────────────────────────────────────────
Write-Host "[1/9] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Python not found in PATH." -ForegroundColor Red
    Write-Host "      Install Python 3.10+ from https://python.org and ensure it is in PATH." -ForegroundColor Red
    exit 1
}

# ── Step 2: Check Node.js / npm ────────────────────────────────────────────────
Write-Host "[2/9] Checking Node.js / npm..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    $npmVersion  = npm  --version 2>&1
    Write-Host "      Found Node: $nodeVersion   npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "      ERROR: Node.js not found in PATH." -ForegroundColor Red
    Write-Host "      Install Node.js 18+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# ── Step 3: Install Python packages ───────────────────────────────────────────
Write-Host "[3/9] Installing Python packages from requirements.txt..." -ForegroundColor Yellow
$reqFile = Join-Path $ScriptDir "mcp_servers\requirements.txt"
python -m pip install --quiet -r $reqFile
Write-Host "      Done." -ForegroundColor Green

# ── Step 4: Install Snowflake MCP npm package ──────────────────────────────────
Write-Host "[4/9] Installing Snowflake MCP npm package (snowflake-mcp)..." -ForegroundColor Yellow
$existing = npm list -g --depth=0 2>$null | Select-String "snowflake-mcp"
if ($existing) {
    Write-Host "      Already installed: $($existing.ToString().Trim())" -ForegroundColor Green
} else {
    npm install -g snowflake-mcp
    Write-Host "      Done." -ForegroundColor Green
}

# ── Step 5: Copy Python MCP server scripts to home directory ───────────────────
Write-Host "[5/9] Copying MCP server scripts to $HomeDir ..." -ForegroundColor Yellow
$scripts = @(
    "monte_carlo_mcp.py",
    "dagster_mcp.py",
    "jira_mcp.py",
    "confluence_mcp.py"
)
foreach ($script in $scripts) {
    $src  = Join-Path $ScriptDir "mcp_servers\$script"
    $dest = Join-Path $HomeDir $script
    Copy-Item $src $dest -Force
    Write-Host "      Copied: $script" -ForegroundColor Green
}

# ── Step 6: Install MCP Launcher VS Code extension ────────────────────────────
Write-Host "[6/9] Installing MCP Launcher VS Code extension..." -ForegroundColor Yellow
$extSrc  = Join-Path $ScriptDir "vscode-extension"
$extDest = Join-Path $env:USERPROFILE ".vscode\extensions\local.mcp-launcher-1.0.0"
if (-not (Test-Path $extDest)) {
    New-Item -ItemType Directory -Path $extDest | Out-Null
}
Copy-Item (Join-Path $extSrc "extension.js") (Join-Path $extDest "extension.js") -Force
Copy-Item (Join-Path $extSrc "package.json")  (Join-Path $extDest "package.json")  -Force
Copy-Item (Join-Path $extSrc "icon.svg")      (Join-Path $extDest "icon.svg")      -Force
Write-Host "      Installed to: $extDest" -ForegroundColor Green
Write-Host "      Restart VS Code to activate the MCP Launcher sidebar panel." -ForegroundColor DarkYellow

# ── Step 7: Deploy .github agents and skills ──────────────────────────────────
Write-Host "[7/9] Deploying agents and skills to .github ..." -ForegroundColor Yellow
$srcGithub  = Join-Path $ScriptDir ".github"
$destGithub = Join-Path $RepoRoot  ".github"

$agentFiles = @(
    "agents\agent.md",
    "agents\mcp-orchestrator.md"
)
$skillFolders = @(
    "skills\cmpgn-html-report",
    "skills\cmpgn-sql-optimization",
    "skills\dagster-job-lineage",
    "skills\dagster-ops-intelligence",
    "skills\etl-lineage-composer",
    "skills\job-resolver",
    "skills\mc-table-alerts"
)

# Agents
foreach ($rel in $agentFiles) {
    $src  = Join-Path $srcGithub  $rel
    $dest = Join-Path $destGithub $rel
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }
    Copy-Item $src $dest -Force
    Write-Host "      Agent: $rel" -ForegroundColor Green
}

# Skills
foreach ($folder in $skillFolders) {
    $srcFolder  = Join-Path $srcGithub  $folder
    $destFolder = Join-Path $destGithub $folder
    if (-not (Test-Path $destFolder)) { New-Item -ItemType Directory -Path $destFolder | Out-Null }
    Copy-Item (Join-Path $srcFolder "SKILL.md") (Join-Path $destFolder "SKILL.md") -Force
    Write-Host "      Skill: $folder" -ForegroundColor Green
}

# Patch hardcoded paths in the deployed files to match this machine
Write-Host "      Patching paths in agent/skill files..." -ForegroundColor Yellow
$OriginalUserHome = "C:\Users\<username>"
$ActualUserHome   = $env:USERPROFILE

$FilesToPatch = @(
    ".github\agents\mcp-orchestrator.md",
    ".github\agents\agent.md",
    ".github\skills\cmpgn-sql-optimization\SKILL.md",
    ".github\skills\cmpgn-html-report\SKILL.md",
    ".github\skills\dagster-job-lineage\SKILL.md",
    ".github\skills\dagster-ops-intelligence\SKILL.md",
    ".github\skills\etl-lineage-composer\SKILL.md",
    ".github\skills\job-resolver\SKILL.md",
    ".github\skills\mc-table-alerts\SKILL.md"
)
$patchCount = 0
foreach ($rel in $FilesToPatch) {
    $fullPath = Join-Path $RepoRoot $rel
    if (-not (Test-Path $fullPath)) { continue }
    $content  = Get-Content $fullPath -Raw -Encoding UTF8
    $patched  = $content.Replace($OriginalUserHome, $ActualUserHome)
    if ($patched -ne $content) {
        Set-Content $fullPath $patched -Encoding UTF8 -NoNewline
        Write-Host "      Patched: $rel" -ForegroundColor Green
        $patchCount++
    }
}
Write-Host "      $patchCount file(s) had paths updated." -ForegroundColor Green

# ── Step 7: Setup .vscode config files ────────────────────────────────────────
Write-Host "[8/9] Setting up .vscode config files..." -ForegroundColor Yellow
$vscodeDir = Join-Path $RepoRoot ".vscode"
if (-not (Test-Path $vscodeDir)) {
    New-Item -ItemType Directory -Path $vscodeDir | Out-Null
}

# mcp.json — only create if not already present; never overwrite customised file
$mcpDest = Join-Path $vscodeDir "mcp.json"
$mcpSrc  = Join-Path $ScriptDir "vscode\mcp.json"
if (Test-Path $mcpDest) {
    Write-Host "      SKIP: .vscode\mcp.json already exists. Not overwriting." -ForegroundColor DarkGray
    Write-Host "      → Open it and fill in the <YOUR_...> placeholders manually." -ForegroundColor DarkYellow
} else {
    Copy-Item $mcpSrc $mcpDest
    Write-Host "      Created .vscode\mcp.json  — fill in the <YOUR_...> placeholders." -ForegroundColor Green
}

# settings.json
$settingsDest = Join-Path $vscodeDir "settings.json"
$settingsSrc  = Join-Path $ScriptDir "vscode\settings.json"
if (Test-Path $settingsDest) {
    Write-Host "      SKIP: .vscode\settings.json already exists. Not overwriting." -ForegroundColor DarkGray
} else {
    Copy-Item $settingsSrc $settingsDest
    Write-Host "      Created .vscode\settings.json (Copilot agent/skill discovery)" -ForegroundColor Green
}

# ── Step 7: Create output folders (CMPGN / UMA / RVNU) ───────────────────────
Write-Host "[9/9] Creating output folders..." -ForegroundColor Yellow
$OutputRoot = Split-Path -Parent $RepoRoot
foreach ($folder in @("CMPGN", "UMA", "RVNU")) {
    $outPath = Join-Path $OutputRoot $folder
    if (-not (Test-Path $outPath)) {
        New-Item -ItemType Directory -Path $outPath | Out-Null
        Write-Host "      Created: $outPath" -ForegroundColor Green
    } else {
        Write-Host "      Already exists: $outPath" -ForegroundColor DarkGray
    }
}

# ── Summary ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!  Two manual steps still required:" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Place corporate_root_ca.pem in your home directory:" -ForegroundColor White
Write-Host "       $HomeDir\corporate_root_ca.pem" -ForegroundColor DarkYellow
Write-Host "     (Get this file from a colleague or your IT/security team)" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Open .vscode\mcp.json and fill in the <YOUR_...> placeholders:" -ForegroundColor White
Write-Host "       SNOWFLAKE_ACCOUNT   — e.g. <YOUR-SNOWFLAKE-ACCOUNT>" -ForegroundColor DarkYellow
Write-Host "       SNOWFLAKE_USERNAME  — your Snowflake user (e.g. JOHN.DOE)" -ForegroundColor DarkYellow
Write-Host "       SNOWFLAKE_ROLE      — your default role (e.g. ANALYST)" -ForegroundColor DarkYellow
Write-Host "       SNOWFLAKE_WAREHOUSE — e.g. COMPUTE_WH" -ForegroundColor DarkYellow
Write-Host "       SNOWFLAKE_DATABASE  — e.g. UMA or CMPGN" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  Tokens / passwords are NOT stored anywhere." -ForegroundColor Green
Write-Host "  VS Code will prompt you to enter each one the first time you" -ForegroundColor Green
Write-Host "  use the mcp-orchestrator agent in a new session:" -ForegroundColor Green
Write-Host ""
Write-Host "     Server          What VS Code asks for" -ForegroundColor White
Write-Host "     ─────────────── ──────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "     Snowflake       Password for <YOUR_SNOWFLAKE_USERNAME>" -ForegroundColor Gray
Write-Host "     Dagster         Dagster Cloud API token" -ForegroundColor Gray
Write-Host "     Jira            Atlassian email address" -ForegroundColor Gray
Write-Host "     Confluence      Atlassian API token (shared with Jira)" -ForegroundColor Gray
Write-Host "     Monte Carlo     Monte Carlo API Key ID" -ForegroundColor Gray
Write-Host "     Monte Carlo     Monte Carlo API Secret" -ForegroundColor Gray
Write-Host "     Databricks      Databricks Personal Access Token (optional)" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Open VS Code in the repo root:" -ForegroundColor White
Write-Host "       code $RepoRoot" -ForegroundColor DarkYellow
Write-Host "     Open Copilot Chat (Ctrl+Alt+I), switch to Agent mode, select" -ForegroundColor Gray
Write-Host "     mcp-orchestrator, and run:  job_name=cmpgn_api_dtl_stg_ddly" -ForegroundColor Gray
Write-Host ""
Write-Host "  See setup\README.md for full details." -ForegroundColor Cyan
Write-Host ""
