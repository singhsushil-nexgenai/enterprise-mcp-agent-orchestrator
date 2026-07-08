# YOUR-ORG Pipeline Observatory Dashboard

This scaffold defines the infrastructure for monitoring and observing all YOUR-ORG ETL pipelines across CMPGN, UMA, and RVNU repositories.

## Objective

Create a **single pane of glass** for:
- Dagster job execution health (last 30 days)
- Monte Carlo data quality incidents
- SQL optimization recommendations
- Pipeline performance trends

## Architecture

### Input Sources (from mcp-orchestrator)
1. **Dagster API** → Job runs, schedules, SLAs
2. **Monte Carlo API** → DQ incidents, monitors, alerts
3. **SQL Optimization Engine** → Optimization recommendations

### Storage Layer
Three Databricks Delta tables:
- `tbl_job_runs` — Dagster job execution history
- `tbl_dq_incidents` — Monte Carlo incidents
- `tbl_sql_optimization` — SQL optimization recommendations

### Dashboard (Databricks Lakeview)
Four pages with KPIs, trends, and recommendation tables

## Build Flow

### Step 1: Create Schema

```powershell
# In Databricks SQL editor, run:
-- Replace __CATALOG__ with your target (dev_analytics, uat_analytics, prod_analytics)
-- Replace __SCHEMA__ with pipeline_observatory or similar
sql/01_create_observatory_schema.sql
```

### Step 2: Populate Tables (via PowerShell or Databricks Jobs)

Use `scripts/populate_observatory_data.ps1` to:
- Query mcp-orchestrator outputs
- Transform Dagster/Monte Carlo API responses
- Insert into Databricks tables
- Schedule to run daily or weekly

```powershell
.\scripts\populate_observatory_data.ps1 -Catalog dev_analytics -Schema pipeline_observatory -Repo CMPGN
```

### Step 3: Build Dashboard (Genie)

In Databricks, create a new dashboard and paste the prompt from `docs/genie_prompt_observatory.txt`.

Genie will auto-generate tiles from the queries in `sql/02_dashboard_queries.sql`.

### Step 4: Publish & Share

Once dashboard renders:
1. **Publish** to Draft mode for testing
2. **Validate** data accuracy (cross-check vs live Dagster runs)
3. **Publish** to Published mode
4. **Share** link with team

## Configuration

Update these in your environment:
- Databricks workspace URL
- Catalog name (dev/uat/prod)
- Schema name (pipeline_observatory)
- Repository selector (CMPGN, UMA, RVNU, or ALL)
- Data retention (default: 30 days for incidents, 7 days for job runs)

## Dashboard Pages (4)

**Page 1 — Pipeline Health Overview**
- KPI cards: Total jobs, Success rate, Failed jobs, Avg duration
- Bar chart: Job count by status
- Table: Last 10 failed jobs

**Page 2 — Data Quality Status**
- KPI cards: Tables with incidents, Critical alerts, Active incidents
- Bar chart: Incident count by type
- Table: Top 20 tables with incidents

**Page 3 — SQL Optimization**
- Bar chart: Top 10 jobs needing optimization
- Table: Optimization recommendations by priority
- KPI: Estimated savings (cost)

**Page 4 — Performance Trends**
- Line chart: Daily run volume (success vs failed, 30 days)
- Line chart: Avg execution time per job (top 5)
- Heatmap: Failure rate by hour of day (when ready)

**Global Filters:**
- Repository (CMPGN, UMA, RVNU, ALL)
- Date range

## Data Freshness

| Table | Update Frequency | Retention |
|---|---|---|
| tbl_job_runs | Daily (after Dagster runs) | 90 days |
| tbl_dq_incidents | Daily (sync from Monte Carlo) | 90 days |
| tbl_sql_optimization | Weekly (run optimizer) | No limit |

## Next Steps

1. Run `01_create_observatory_schema.sql` in Databricks SQL
2. Customize `populate_observatory_data.ps1` with your API credentials
3. Schedule the PowerShell script as a Databricks job or Windows Task Scheduler
4. Build the dashboard with Genie using the prompt file
5. Set up alerts/subscriptions in Databricks for critical tiles
