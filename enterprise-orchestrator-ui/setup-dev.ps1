<#
.SYNOPSIS
    Local development quick-start (no Docker required).
    Requires: Python 3.10+, Node 18+, Redis running on localhost:6379, PostgreSQL on localhost:5432.
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Enterprise Orchestrator — Local Dev Setup ===" -ForegroundColor Cyan

# 1. Backend venv + deps
Write-Host "[1/4] Setting up Python backend..." -ForegroundColor Yellow
$backendDir = Join-Path $Root "backend"
Push-Location $backendDir
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".venv\Scripts\Activate.ps1"
pip install --quiet -r requirements.txt
Pop-Location
Write-Host "      Done." -ForegroundColor Green

# 2. Frontend deps
Write-Host "[2/4] Installing frontend dependencies..." -ForegroundColor Yellow
$frontendDir = Join-Path $Root "frontend"
Push-Location $frontendDir
npm install --silent
Pop-Location
Write-Host "      Done." -ForegroundColor Green

# 3. .env
Write-Host "[3/4] Checking .env file..." -ForegroundColor Yellow
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root ".env.example") $envFile
    Write-Host "      Created .env from template — fill in secrets before running." -ForegroundColor DarkYellow
} else {
    Write-Host "      .env already exists." -ForegroundColor Green
}

# 4. Instructions
Write-Host "[4/4] Ready!" -ForegroundColor Green
Write-Host ""
Write-Host "  Start services in 3 terminals:" -ForegroundColor White
Write-Host "    Terminal 1 (API):     cd backend; .venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8080" -ForegroundColor Gray
Write-Host "    Terminal 2 (Worker):  cd backend; .venv\Scripts\Activate.ps1; python -m app.worker" -ForegroundColor Gray
Write-Host "    Terminal 3 (UI):      cd frontend; npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  Or use Docker:  docker compose up --build" -ForegroundColor Gray
Write-Host ""
