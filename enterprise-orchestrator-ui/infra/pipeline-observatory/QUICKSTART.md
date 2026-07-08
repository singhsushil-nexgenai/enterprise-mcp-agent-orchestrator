# Quick Start: YOUR-ORG Pipeline Observatory

## 5-Minute Setup

### Step 1: Create Schema in Databricks
1. Open Databricks SQL Editor
2. Copy and paste all SQL from: `sql/01_create_observatory_schema.sql`
3. Replace `__CATALOG__` with your target (e.g., `dev_analytics`)
4. Replace `__SCHEMA__` with `pipeline_observatory`
5. **Execute** all statements

### Step 2: Populate Sample Data
```powershell
# Open PowerShell and run:
cd enterprise-orchestrator-ui/infra/pipeline-observatory/scripts
.\populate_observatory_data.ps1 -Catalog dev_analytics -Schema pipeline_observatory
```

This outputs SQL INSERT statements. Copy and paste them into Databricks SQL Editor and execute.

### Step 3: Build Dashboard in Databricks Genie
1. In Databricks, click **Create → Dashboard**
2. Name it: **"YOUR-ORG Pipeline Observatory"**
3. Click the **Genie** icon (AI wand)
4. Copy the entire text from: `docs/genie_prompt_observatory.txt`
5. Paste into the Genie prompt box
6. Click **Generate**
7. Wait for Genie to auto-create all 4 pages with tiles

### Step 4: Review & Publish
1. Click through each page (Pipeline Health, DQ Status, SQL Optimization, Trends)
2. Test the global filters (Repository, Date Range)
3. Click **Publish** → **Published**
4. Copy the dashboard URL and share with your team

---

## What You Get

✅ **4-page executive dashboard**
✅ **12+ KPI cards and charts**
✅ **Real-time data from mcp-orchestrator**
✅ **Global filters for multi-repo analysis**
✅ **Data quality + performance tracking**
✅ **SQL optimization recommendations**

---

## Troubleshooting

**Q: Tables are empty after inserting data**
- A: Run `SELECT COUNT(*) FROM tbl_job_runs;` in Databricks SQL Editor to verify data
- If 0, re-run the populate script and copy/paste SQL again

**Q: Genie didn't create all tiles**
- A: Click **Edit** on the dashboard, then re-submit the full prompt to Genie
- Make sure `@` object references are pointing to correct tables

**Q: I want to filter by date**
- A: The global date range filter is automatically added; use it on any page

---

## Next: Schedule Daily Data Refresh

To keep the dashboard fresh, schedule the PowerShell script to run daily:

**Option A: Databricks Job**
1. Go to Compute → Jobs
2. Create new job
3. Type: Python notebook
4. Paste Python equivalent of populate script
5. Schedule: Daily 6 AM
6. Cluster: Shared compute

**Option B: Windows Task Scheduler**
```powershell
# Create a scheduled task:
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\path\to\populate_observatory_data.ps1"
Register-ScheduledTask -TaskName "Observatory-Daily-Refresh" -Trigger $trigger -Action $action
```

---

## Questions?

Refer to the detailed README.md in the same folder for architecture and customization details.
