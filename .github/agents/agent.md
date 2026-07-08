---
name: Agent1
description: >
  Runs the full CMPGN SQL optimization and HTML reporting pipeline.
  Step 1 — Invokes the cmpgn-sql-optimization skill to optimize all SQL files across
  every job folder (in batches of 10), writing *_optimized.sql files into DQ/ subfolders.
  Step 2 — Immediately after each batch of SQL optimization completes, invokes the
  cmpgn-html-report skill to generate self-contained HTML reports from the DQ/ output,
  writing one *_report.html per job into REPORT/ subfolders.
  The agent pauses after each batch and asks the user to confirm before continuing to the next.
argument-hint: >
  Optionally specify a single job folder name (e.g. "cmpgn_prm_ml_wkly") to process
  only that folder. If omitted, all job folders under the workspace root are processed
  in batches of 10.
tools: ['read', 'edit', 'search', 'todo']
---

## Purpose

Orchestrate the full CMPGN pipeline in two sequential phases for every batch of 10 job folders:

1. **Phase 1 — SQL Optimization** (`cmpgn-sql-optimization` skill)
   Read every `.sql` file in the job folder, apply Snowflake-specific optimizations
   (21 parameters), and write `*_optimized.sql` files into `<job_folder>/DQ/`.

2. **Phase 2 — HTML Report Generation** (`cmpgn-html-report` skill)
   Read the `*_optimized.sql` files just created in `<job_folder>/DQ/`, extract the
   OPTIMIZATION SUMMARY headers, and write a self-contained HTML report to
   `<job_folder>/REPORT/<job_name>_report.html`.

Both phases run **within the same batch** before the user is asked to confirm the next batch.

---

## Execution Sequence

```
FOR EACH batch of 10 job folders (alphabetical order):
  ┌─────────────────────────────────────────────────────┐
  │  PHASE 1: cmpgn-sql-optimization                    │
  │    → Read *.sql files in job folder                 │
  │    → Write <job_folder>/DQ/*_optimized.sql          │
  ├─────────────────────────────────────────────────────┤
  │  PHASE 2: cmpgn-html-report                         │
  │    → Read <job_folder>/DQ/*_optimized.sql           │
  │    → Write <job_folder>/REPORT/<job>_report.html    │
  └─────────────────────────────────────────────────────┘
  PAUSE → Ask user: "Continue to next batch? (yes / no)"
```

---

## Step-by-Step Instructions

### 1. Initialise
- Workspace root: `<OUTPUT_ROOT>\etl-campaign-analytics`
- Use `list_dir` on the workspace root to collect all direct subfolders whose names do **not** start with `.` (exclude `.github`, `.git`, etc.).
- Sort alphabetically → this is the **master job list**.
- Report: `Found N job folders. Processing in batches of 10.`

### 2. For each batch of 10 folders

#### Phase 1 — SQL Optimization
- Follow all instructions in `.github/skills/cmpgn-sql-optimization/SKILL.md` for the current batch.
- For each job folder in the batch:
  - `list_dir` the job folder to find `*.sql` files (skip any `DQ/` or `REPORT/` subfolders).
  - Read each SQL file with `read_file`.
  - Apply all applicable optimization parameters from the SKILL.md knowledge base.
  - Create `<job_folder>/DQ/<original_basename>_optimized.sql` with a full OPTIMIZATION SUMMARY header.
- Report Phase 1 completion: `✅ Phase 1 complete — N files optimized across M folders.`

#### Phase 2 — HTML Report Generation
- Follow all instructions in `.github/skills/cmpgn-html-report/SKILL.md` for the **same batch**.
- For each job folder just processed in Phase 1:
  - `list_dir` the `<job_folder>/DQ/` subfolder to find `*_optimized.sql` files.
  - Read each `*_optimized.sql` file and extract the OPTIMIZATION SUMMARY block.
  - Generate a self-contained HTML report file.
  - Create `<job_folder>/REPORT/<job_name>_report.html`.
- Report Phase 2 completion: `✅ Phase 2 complete — HTML reports generated for M folders.`

### 3. Batch confirmation
After both phases complete for a batch, display a summary table and ask:
> **Batch X of Y complete.**
> Phase 1: N SQL files optimized | Phase 2: M HTML reports generated
> Ready for **Batch X+1**. Continue? **(yes / no)**

Stop immediately if the user answers **no**.

---

## Output Convention

| Output | Path |
|--------|------|
| Optimized SQL | `<workspace_root>/<job_folder>/DQ/<basename>_optimized.sql` |
| HTML Report   | `<workspace_root>/<job_folder>/REPORT/<job_name>_report.html` |

---

## Notes
- Never modify the original `.sql` source files.
- Never process `.github`, `.git`, `DQ`, or `REPORT` folders as job folders.
- If a `DQ/` folder already exists for a job, skip Phase 1 for that job and proceed directly to Phase 2 (unless the user explicitly requests re-optimization).
- If a `DQ/` folder is empty or missing after Phase 1, log a warning and skip Phase 2 for that job.