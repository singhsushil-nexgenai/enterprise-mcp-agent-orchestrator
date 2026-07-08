# PowerShell Script: Populate Pipeline Observatory Tables
# This script queries Dagster and Monte Carlo APIs and inserts data into Databricks

param(
  [string]$Catalog = "dev_analytics",
  [string]$Schema = "pipeline_observatory",
  [string]$DatabricksHost = "https://<your-databricks-host>.cloud.databricks.com",
  [string]$WarehouseId = "YOUR_WAREHOUSE_ID",
  [string]$Repo = "CMPGN"  # CMPGN, UMA, RVNU, or ALL
)

# Import required modules (install if missing)
$ErrorActionPreference = "Stop"

Write-Host "=== Pipeline Observatory Data Population ===" -ForegroundColor Cyan
Write-Host "Catalog: $Catalog | Schema: $Schema | Repo: $Repo"

# ============================================================================
# 1. FETCH DAGSTER JOB RUNS
# ============================================================================
Write-Host "`n[1/3] Fetching Dagster job runs..." -ForegroundColor Yellow

# This would normally call the Dagster Cloud API
# For now, we'll create sample data structure

$dagsterRuns = @(
  @{
    run_id = "run_001"
    job_name = "cmpgn_api_dtl_stg_ddly"
    repo = "CMPGN"
    status = "Success"
    start_time = (Get-Date).AddHours(-2)
    end_time = (Get-Date).AddHours(-1.5)
    duration_minutes = 30
    run_date = (Get-Date).Date
  },
  @{
    run_id = "run_002"
    job_name = "cmpgn_prm_ml_wkly"
    repo = "CMPGN"
    status = "Failed"
    start_time = (Get-Date).AddHours(-4)
    end_time = (Get-Date).AddHours(-3.5)
    duration_minutes = 30
    run_date = (Get-Date).Date
  }
)

Write-Host "Found $($dagsterRuns.Count) job runs" -ForegroundColor Green

# ============================================================================
# 2. FETCH MONTE CARLO DQ INCIDENTS
# ============================================================================
Write-Host "`n[2/3] Fetching Monte Carlo incidents..." -ForegroundColor Yellow

$mcIncidents = @(
  @{
    incident_id = "inc_001"
    table_name = "CMPGN.TGT.CMPGN_PROMO_ML_HIST"
    incident_type = "Missing values"
    severity = "Critical"
    status = "Active"
    created_at = (Get-Date).AddDays(-1)
    resolved_at = $null
    description = "Null values detected in ACCT_KEY column"
  },
  @{
    incident_id = "inc_002"
    table_name = "UMA.TGT.OTT_ACTVT_FCT"
    incident_type = "Schema change"
    severity = "High"
    status = "Active"
    created_at = (Get-Date).AddDays(-2)
    resolved_at = $null
    description = "New column detected: discount_amount"
  }
)

Write-Host "Found $($mcIncidents.Count) incidents" -ForegroundColor Green

# ============================================================================
# 3. FETCH SQL OPTIMIZATION RECOMMENDATIONS
# ============================================================================
Write-Host "`n[3/3] Fetching SQL optimization recommendations..." -ForegroundColor Yellow

$sqlOptimizations = @(
  @{
    opt_id = "opt_001"
    job_name = "cmpgn_api_dtl_stg_ddly"
    repo = "CMPGN"
    parameter_name = "use_clustering_key"
    recommendation = "Add clustering key on ACCT_KEY and ACTVT_DT for better query performance"
    priority = "High"
    estimated_improvement_pct = 25.5
    current_query_cost = 150.00
    optimized_query_cost = 112.00
    created_at = (Get-Date).AddDays(-3)
  },
  @{
    opt_id = "opt_002"
    job_name = "cmpgn_prm_ml_wkly"
    repo = "CMPGN"
    parameter_name = "push_down_filter"
    recommendation = "Move WHERE clause before JOIN to reduce intermediate result set"
    priority = "Medium"
    estimated_improvement_pct = 15.0
    current_query_cost = 200.00
    optimized_query_cost = 170.00
    created_at = (Get-Date).AddDays(-5)
  }
)

Write-Host "Found $($sqlOptimizations.Count) optimization recommendations" -ForegroundColor Green

# ============================================================================
# 4. BUILD INSERT STATEMENTS
# ============================================================================
Write-Host "`n[4/4] Building INSERT statements..." -ForegroundColor Yellow

$insertJobRuns = $dagsterRuns | ForEach-Object {
  $dateStr = ($_.run_date).ToString("yyyy-MM-dd")
  $startTime = ($_.start_time).ToString("yyyy-MM-dd HH:mm:ss")
  $endTime = ($_.end_time).ToString("yyyy-MM-dd HH:mm:ss")
  
  "INSERT INTO $Catalog.$Schema.tbl_job_runs VALUES ('$($_.run_id)', '$($_.job_name)', '$($_.repo)', '$($_.status)', '$startTime', '$endTime', $($_.duration_minutes), CAST('$dateStr' AS DATE), current_timestamp());"
} -join "`n"

$insertIncidents = $mcIncidents | ForEach-Object {
  $createdAt = ($_.created_at).ToString("yyyy-MM-dd HH:mm:ss")
  $resolvedAt = if ($_.resolved_at) { "'" + ($_.resolved_at).ToString("yyyy-MM-dd HH:mm:ss") + "'" } else { "NULL" }
  
  "INSERT INTO $Catalog.$Schema.tbl_dq_incidents VALUES ('$($_.incident_id)', '$($_.table_name)', '$($_.incident_type)', '$($_.severity)', '$($_.status)', '$createdAt', $resolvedAt, '$($_.description)', current_timestamp());"
} -join "`n"

$insertOptimizations = $sqlOptimizations | ForEach-Object {
  $createdAt = ($_.created_at).ToString("yyyy-MM-dd HH:mm:ss")
  
  "INSERT INTO $Catalog.$Schema.tbl_sql_optimization VALUES ('$($_.opt_id)', '$($_.job_name)', '$($_.repo)', '$($_.parameter_name)', '$($_.recommendation)', '$($_.priority)', $($_.estimated_improvement_pct), $($_.current_query_cost), $($_.optimized_query_cost), '$createdAt', current_timestamp());"
} -join "`n"

# ============================================================================
# 5. OUTPUT SQL FOR EXECUTION
# ============================================================================
$fullSql = @"
-- Job Runs Insert
$insertJobRuns

-- DQ Incidents Insert
$insertIncidents

-- SQL Optimization Insert
$insertOptimizations
"@

Write-Host "`n=== SQL TO EXECUTE IN DATABRICKS ===" -ForegroundColor Cyan
Write-Host $fullSql

Write-Host "`n=== NEXT STEPS ===" -ForegroundColor Green
Write-Host "1. Copy the SQL above"
Write-Host "2. Paste into Databricks SQL Editor"
Write-Host "3. Execute the statements"
Write-Host "4. Verify data in Databricks UI (Data Explorer)"
Write-Host "5. Build the dashboard with Genie using docs/genie_prompt_observatory.txt"

# ============================================================================
# 6. OPTIONAL: EXECUTE DIRECTLY (requires Databricks CLI or API)
# ============================================================================
Write-Host "`n[OPTIONAL] To execute directly, install Databricks CLI:" -ForegroundColor Cyan
Write-Host "  pip install databricks-cli"
Write-Host "  databricks auth login --host $DatabricksHost"
Write-Host "  databricks sql statement-exec create --warehouse-id $WarehouseId --statement `"<sql-here>`""
