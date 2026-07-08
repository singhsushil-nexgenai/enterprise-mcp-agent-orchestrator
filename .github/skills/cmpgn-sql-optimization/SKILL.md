---
name: cmpgn-sql-optimization
description: >
  Optimize SQL files for a given job from any of the three YOUR-ORG repositories
  (CMPGN, UMA, RVNU). Reads SQL files directly from GitHub via the GitHub MCP
  server — no local clone needed. Applies 20 Snowflake-specific optimization
  parameters. Writes optimized files with a 9-section OPTIMIZATION SUMMARY header
  into a local DQ subfolder under WORKSPACE_ROOT\<OUTPUT_FOLDER>\<job_name>\DQ\.
  When invoked by the MCP orchestrator, processes a single job. When invoked
  standalone, can process all jobs in a repo in batches of 10.
---

## Purpose

Read `.sql` files from a GitHub repository (directly via GitHub MCP), apply SQL
optimization best practices, and write the resulting files into a local `DQ\`
subfolder. In **single-job mode** (invoked by orchestrator), processes one job only.
In **all-jobs mode** (standalone use), processes all job folders in the specified
repo in batches of 10.

---

## Inputs

| Parameter      | Description |
|----------------|-------------|
| `job_context`  | *(Single-job mode)* Full job context from `job-resolver`. Must include `job_name`, `github_org`, `github_repo`, `github_branch`, `job_folder_path`, `sql_files`, `output_folder`, `local_output_root`. |
| `repo`         | *(All-jobs mode only)* Repo alias: `cmpgn`, `uma`, or `rvnu`. Required when `job_context` is not provided. |
| `job_folder`   | *(All-jobs mode only)* Single folder name to process within `repo`. If omitted, all folders are processed in batches of 10. |
| `batch_size`   | Fixed at **10** job folders per batch. Not configurable. |

---

## Repository Registry

| Alias  | GitHub Org | GitHub Repo                                    | Branch | Output Folder |
|--------|------------|------------------------------------------------|--------|---------------|
| `cmpgn`| `YOUR-ORG` | `etl-campaign-analytics`                   | `prod` | `CMPGN`       |
| `uma`  | `YOUR-ORG` | `etl-unified-marketing`     | `prod` | `UMA`         |
| `rvnu` | `YOUR-ORG` | `etl-revenue-analytics`         | `prod` | `RVNU`        |

**Local output root** (`OUTPUT_ROOT` — **outside** the source repo): `<OUTPUT_ROOT>\<OUTPUT_FOLDER>\<job_name>\DQ\`

---

## Step-by-Step Instructions

### 1. Build the full job folder list

**Single-job mode** (job_context provided by orchestrator):
- The job folder and SQL file list come directly from `job_context`.
  - `github_org`, `github_repo`, `github_branch`, `job_folder_path`, `sql_files` are all pre-populated.
  - `local_dq_dir = job_context.local_output_root + "\DQ"`
- Skip directly to Step 3.

**All-jobs mode** (standalone, no job_context):
- Identify the repo entry from the Registry using the `repo` alias.
- Call `list_directory_contents(owner="YOUR-ORG", repo=<github_repo>, path="", ref="prod")`.
- Filter to directories only; exclude names starting with `.` or equal to `deploy_list`.
  This is the **master job list** for this repo.
- If `job_folder` is specified: keep only that one folder. Confirm it exists in the listing.
- Sort alphabetically. Report: `Found <N> job folders. Processing in batches of 10.`

### 2. Divide into batches of 10 (all-jobs mode only)
- Split the master job list into consecutive batches of 10.
- Track current batch number and total batches.

### 3. Process one batch at a time
Repeat for each batch:

#### 3a. Announce the batch
```
─────────────────────────────────────────────────────────────────
Batch <N> of <TOTAL>  —  Jobs <start>–<end>
Repo    : YOUR-ORG/<github_repo> (branch: prod)
Output  : WORKSPACE_ROOT\<OUTPUT_FOLDER>\
Folders : <folder1>, <folder2>, … <folder10>
─────────────────────────────────────────────────────────────────
```

#### 3b. For each job folder in the batch:

**i. Discover SQL files from GitHub**

*Single-job mode*: use `job_context.sql_files` — no GitHub API call needed.

*All-jobs mode*: call `list_directory_contents` on the job folder:
```
list_directory_contents(
  owner = "YOUR-ORG",
  repo  = <github_repo>,
  path  = "<job_folder>",
  ref   = "prod"
)
```
Filter to files with names ending in `.sql`.
Skip the folder silently if no `.sql` files are found (note in batch summary).

**ii. Determine the local DQ output folder**

```
local_dq_dir = <OUTPUT_ROOT>\<OUTPUT_FOLDER>\<job_folder>\DQ
```
(OUTPUT_ROOT = `<OUTPUT_ROOT>` — parent of the source repo)

Create with `create_directory` if it does not exist.
**Do not delete or overwrite existing files in `DQ\`** without user confirmation.

**iii. Read from GitHub, optimize, and write each SQL file**

Read each SQL file directly from GitHub:
```
get_file_contents(
  owner = "YOUR-ORG",
  repo  = <github_repo>,
  path  = "<job_folder>/<sql_filename>",
  ref   = "prod"
)
```
Decode the base64 content.

Apply all applicable rules from the **SQL Optimization Rules** section below.
Preserve the original SQL intent and semantics.

Output file naming: `<original_basename>_optimized.sql`
- Example: `cmpgn_prm_ml_extract.sql` → `DQ\cmpgn_prm_ml_extract_optimized.sql`

Add a header comment block at the top of every output file:
```sql
-- =============================================================
-- Optimized version of: <original_filename>.sql
-- Source repo         : YOUR-ORG/<github_repo> (branch: prod)
-- Source job folder   : <job_folder>
-- GitHub path         : <job_folder>/<original_filename>.sql
-- Generated by        : sql-optimization skill
-- Optimization date   : <today's date>
-- =============================================================
```

Write using `create_file` to:
`<OUTPUT_ROOT>\<OUTPUT_FOLDER>\<job_folder>\DQ\<original_basename>_optimized.sql`

#### 3c. Batch summary

| Job Folder | File | Optimizations Applied |
|------------|------|-----------------------|
| `folder1` | `file1_optimized.sql` | CTE refactor, removed SELECT *, added column aliases |
| `folder1` | `file2_optimized.sql` | Removed UPPER() on join key |
| `folder2` | *(no SQL files)* | Skipped |

#### 3d. Ask the user whether to continue (all-jobs mode only)
After the batch summary, if there are more batches, **pause and ask the user**:

> **Batch `<N>` of `<TOTAL>` complete.**
> `<count>` files optimized across `<count>` folders.
>
> Ready to process **Batch `<N+1>`** (folders: `<folder11>`, `<folder12>`, …).
> **Continue? (yes / no)**

- `yes` / affirmatives: proceed to next batch.
- `no` / negatives or no response: stop and print final summary (Step 4).

### 4. Final overall summary
```
═══════════════════════════════════════════════════════════════
SQL Optimization Complete
═══════════════════════════════════════════════════════════════
Repository    : YOUR-ORG/<github_repo> (branch: prod)
Output folder : <OUTPUT_ROOT>\<OUTPUT_FOLDER>\ (outside source repo)
Batches done  : <N> of <TOTAL>
Job folders   : <count>
SQL files     : <count>
Skipped       : <count> (no SQL files)
═══════════════════════════════════════════════════════════════
```

---

## SQL Optimization Rules

Apply all rules that are relevant to the SQL in the file. Rules are ordered from highest to lowest impact.

### R1 — Replace correlated subqueries and nested subqueries with CTEs
- Convert deeply nested `SELECT` subqueries or repeated subquery references into named `WITH` (CTE) blocks at the top of the statement.
- Each CTE should be clearly named after its logical purpose.

**Before:**
```sql
SELECT *
FROM orders
WHERE customer_id IN (
    SELECT customer_id FROM customers WHERE region = 'WEST'
);
```
**After:**
```sql
WITH west_customers AS (
    SELECT customer_id
    FROM customers
    WHERE region = 'WEST'
)
SELECT *
FROM orders
WHERE customer_id IN (SELECT customer_id FROM west_customers);
```

---

### R2 — Eliminate SELECT *
- Replace `SELECT *` with an explicit column list.
- If the full column list is not knowable from the file alone, add a comment `-- TODO: replace * with explicit column list` and leave `*` in place rather than guessing column names.
- Exception: `SELECT *` inside a CTE that is immediately fully consumed by an outer query with explicit columns may be left as-is.

---

### R3 — Remove function calls on JOIN / WHERE keys that prevent predicate push-down
- Avoid wrapping join or filter keys in functions such as `UPPER()`, `LOWER()`, `COALESCE()`, `CAST()`, or `TO_DATE()` on the **driving/left** side when the right side value can be normalized instead.
- If the intent is a case-insensitive comparison, prefer collation or consistent data normalization at load time, and add a `-- NOTE:` comment explaining the change.

**Before:**
```sql
ON UPPER(tgt.CONTCT_STS_CD) = UPPER(src.CONTCT_STS_CD)
AND COALESCE(tgt.contct_sts_id, '') = COALESCE(src.contct_sts_id, '')
```
**After (preferred when data is already normalized):**
```sql
ON tgt.CONTCT_STS_CD = src.CONTCT_STS_CD
AND tgt.contct_sts_id = src.contct_sts_id  -- NOTE: assumes NULLs are handled upstream
```
If normalization cannot be verified, keep the original and add a `-- REVIEW:` comment.

---

### R4 — Replace CASE WHEN with equivalent simpler expressions
- `CASE WHEN x IS NULL OR x = '' THEN 'UNKNOWN' ELSE x END` → use `NULLIF` + `COALESCE`:
  ```sql
  COALESCE(NULLIF(TRIM(x), ''), 'UNKNOWN')
  ```
- `CASE WHEN col LIKE '%Y%' THEN TRUE ELSE FALSE END` → use `col ILIKE '%Y%'` or `CONTAINS(col, 'Y')` depending on dialect; for Snowflake:
  ```sql
  (col ILIKE '%Y%')
  ```

---

### R5 — Normalize SQL keyword casing to UPPERCASE
- All SQL reserved keywords (`SELECT`, `FROM`, `WHERE`, `JOIN`, `ON`, `AND`, `OR`, `INSERT`, `MERGE`, `WHEN`, `THEN`, `ELSE`, `END`, `WITH`, `AS`, `INTO`, `VALUES`, `DISTINCT`, `GROUP BY`, `ORDER BY`, `HAVING`, `UNION`, `EXCEPT`, `INTERSECT`, `LEFT`, `RIGHT`, `INNER`, `OUTER`, `FULL`, `CROSS`, `NOT`, `IN`, `EXISTS`, `BETWEEN`, `LIKE`, `NULL`, `TRUE`, `FALSE`) must be UPPERCASE.
- User-defined identifiers (table names, column names, aliases, CTE names) keep their original casing.

---

### R6 — Add explicit table aliases and qualify all column references
- Every table or subquery/CTE reference must have a short, meaningful alias.
- All column references in multi-table queries must be prefixed with the table alias.
- This avoids ambiguous column errors and makes execution plans clearer.

---

### R7 — Avoid SELECT DISTINCT when GROUP BY or deduplication CTE is cleaner
- Replace `SELECT DISTINCT col1, col2, …` with a `GROUP BY col1, col2, …` when there are no aggregate functions — GROUP BY is more explicit about intent and can use different execution paths.
- Exception: keep `DISTINCT` when the query has only one table and no joins, where it is equally efficient.

---

### R8 — Use ROW_NUMBER() deduplication pattern consistently
- When a subquery already uses `ROW_NUMBER() OVER (PARTITION BY … ORDER BY …)` for deduplication, extract it as a CTE and filter `WHERE rn = 1` (or `record_rank = 1`) in the outer query — do not inline it.

---

### R9 — Replace `add_months(current_date(), -N)` with `DATEADD`
- For Snowflake SQL, prefer:
  ```sql
  DATEADD(MONTH, -N, CURRENT_DATE())
  ```
  over `add_months(current_date(), -N)` for clarity and consistency with Snowflake's native functions.

---

### R10 — Remove redundant TRUNCATE before INSERT/MERGE when the pattern is already safe
- If a `TRUNCATE TABLE` is immediately followed by an `INSERT INTO` that fully repopulates the table (a full-refresh pattern), add a comment confirming this is intentional rather than removing it.
- Do not remove `TRUNCATE` statements — only annotate them.

---

### R11 — Consistent indentation and formatting
- Use 4-space indentation for nested clauses.
- Each selected column on its own line.
- `JOIN` conditions each on their own line, indented under `ON`.
- Opening `(` for subqueries/CTEs at end of the line; closing `)` on its own line, aligned with the keyword that opened the block.
- No trailing whitespace.

---

## Important Constraints

- **Do not change query semantics.** If an optimization changes behavior (e.g., NULL handling), add a `-- REVIEW:` comment and leave the original logic intact.
- **Do not modify the original `.sql` files.** Only write to the `DQ/` subfolder.
- **Do not process files outside the specified job folder** (no recursion into subdirectories, no cross-job changes).
- **Preserve all comments** present in the original SQL files.
- If a file is already optimized (trivially short, e.g. a single `TRUNCATE` statement), write it to `DQ/` with the name `<basename>_optimized.sql`, include only the header comment and the original content unchanged, and note "No optimizations required" in the batch summary.
- **Never start a new batch without explicit user confirmation.** If the user says anything other than an affirmative, or provides no response, treat it as a stop.

---

## Example Invocation

> "Optimize all SQL jobs."

The skill will:
1. List all job folders under the workspace root (e.g. 52 folders). Report: `Found 52 job folders. Processing in batches of 10.`
2. **Batch 1** (folders 1–10): For each folder, create `DQ/`, read each `.sql` file, optimize it, and write `<basename>_optimized.sql` to `DQ/`.
3. Print a batch summary table, then ask: **"Batch 1 of 6 complete. Continue to Batch 2? (yes / no)"**
4. On **yes** → process Batch 2 (folders 11–20), repeat.
5. On **no** or no response → print the final overall summary and stop.

**Single-folder example:**
> "Optimize the SQL in the `cmpgn_prm_ml_wkly` job folder."

The skill will:
1. Scan `<OUTPUT_ROOT>\etl-campaign-analytics\cmpgn_prm_ml_wkly\` for `.sql` files.
2. Create `DQ\` if it does not exist.
3. Read, optimize, and write each file with the `_optimized.sql` suffix:
   - `cmpgn_prm_ml_extract.sql` → `DQ\cmpgn_prm_ml_extract_optimized.sql`
   - `cmpgn_prm_ml_insert.sql` → `DQ\cmpgn_prm_ml_insert_optimized.sql`
   - `cmpgn_prm_ml_read_dim.sql` → `DQ\cmpgn_prm_ml_read_dim_optimized.sql`
   - `cmpgn_prm_ml_read_fct.sql` → `DQ\cmpgn_prm_ml_read_fct_optimized.sql`
   - `cmpgn_prm_ml_truncate_stg.sql` → `DQ\cmpgn_prm_ml_truncate_stg_optimized.sql`
   - `cmpgn_prm_ml_truncate_stg_dim.sql` → `DQ\cmpgn_prm_ml_truncate_stg_dim_optimized.sql`
   - `contct_sts_dim_extract.sql` → `DQ\contct_sts_dim_extract_optimized.sql`
4. Output a summary of changes made per file. (No batch confirmation needed for a single-folder run.)

---

## Additional Domain-Specific Optimization Parameters (CMPGN)

Apply these parameters in addition to R1–R11 for every SQL file touching CMPGN tables.
All domain rules, real data, and check SQLs are in the **CMPGN Knowledge Base** section below.

### PARAM 1 — JOINS
Verify equality joins, correct join order (large fact on driving/left side, small dim on right),
no NULL-key joins on high-risk columns. Use Fact→Dim join maps in KB Section 3.
Check: no OR in ON clause, no CAST/function in ON clause, no VARIANT columns in ON clause.

### PARAM 2 — FILTERS
Every table with >100M rows MUST have a selective WHERE clause applied before any join.
Use recommended date filter columns from KB Section 3 Param 2.
Flag: MISSING_DATE_FILTER

### PARAM 3 — AGGREGATIONS
Prefer pre-aggregated tables (CMPGN_RSPNS_AGG, USR_RCMNDTN_SUMRY_FCT) when available.
Flag unbounded GROUP BY on large tables. Flag expensive COUNT(DISTINCT) on 1B+ rows.
Flag: UNBOUNDED_AGGREGATION_RISK | EXPENSIVE_COUNT_DISTINCT

### PARAM 4 — REDUCE SCANS
Apply mandatory date-range filters on all CRITICAL tables (USR_RCMNDTN_CNTNT_FCT 7.4B,
CMPGN_CNVS_APP_CONTCT_FCT 7.4B, CMPGN_CNVS_APP_RSPNS_FCT 2.3B, CMPGN_CONTCT_FCT 2.8B).
Flag: FULL_SCAN_CRITICAL

### PARAM 5 — IMPROVE JOINS
Pre-filter both sides of large-to-large joins in CTEs before joining.
Note: CMPGN_SBSCRBR_DIM (93M rows) and CUST_APP_DVC_DIM (146M rows) are NOT small dims.
Prefer NUMBER surrogate _KEY joins over TEXT column joins.

### PARAM 6 — PREDICATE PUSHDOWN
Push all filters into CTEs before any join. Large table must be pre-filtered in a CTE,
not filtered in a WHERE after a full join.
Flag: MISSING_PREDICATE_PUSHDOWN

### PARAM 7 — AVOID SELECT *
Replace SELECT * with explicit column list. Critical on VARIANT/ARRAY tables.
Wide tables: CMPGN_DIM (53 cols), USR_RCMNDTN_CNTNT_FCT (50 cols + 6 VARIANT/ARRAY),
CMPGN_CONTCT_FCT (36 cols + 1 ARRAY), CMPGN_RSPNS_FCT (31 cols), USR_RCMNDTN_FCT (26 cols).
Flag: SELECT_STAR_WITH_VARIANT_RISK

### PARAM 8 — CLUSTERING ALIGNMENT
ALL CMPGN.TGT tables have ZERO clustering keys — every query does a full scan.
Note 'Clustering key missing — predicate pruning NOT active' in OPTIMIZATION SUMMARY.
Recommend cluster keys from KB Section 3 Param 8.

### PARAM 9 — CLUSTERING CANDIDATES
Flag all large tables as clustering candidates. Priority order in KB Section 3 Param 9.
Top 7: USR_RCMNDTN_CNTNT_FCT → CMPGN_CNVS_APP_CONTCT_FCT → CMPGN_CNVS_APP_RSPNS_FCT →
CMPGN_CONTCT_FCT → USR_RCMNDTN_FCT → CMPGN_RSPNS_AGG → CMPGN_RSPNS_FCT

### PARAM 10 — EXPLODING JOIN DETECTION
Flag joins where output rows ≥ 10x input rows or CartesianJoin operator is present.
High-risk pairs from KB Section 3 Param 10. Two large facts joined without date filter = flag immediately.
Flag: EXPLODING_JOIN_RISK | CRITICAL_CARTESIAN_JOIN

### PARAM 11 — JOIN CONDITION QUALITY
Flag OR in JOIN, CAST/function in ON clause, VARIANT columns in ON clause, TEXT key where
NUMBER surrogate exists. SCD2 range joins on CMPGN_DIM, CMPGN_SBSCRBR_DIM, CUST_APP_DVC_DIM
are expected but expensive — add SCD2_RANGE_JOIN_NOTE comment.
Flag: OR_JOIN_CONDITION_DETECTED | FUNCTION_IN_JOIN_DETECTED | VARIANT_JOIN_DETECTED_CRITICAL | SUBOPTIMAL_JOIN_KEY_TYPE

### PARAM 12 — MANY-TO-MANY JOIN RISK
Flag SCD2 dim joins without IS_CURR_FLG filter. See KB Section 3 Param 12 for dim status.
CMPGN_DIM: PK = CMPGN_KEY + IS_CURR_FLG='Y'. CMPGN_SBSCRBR_DIM: + IS_CURR_FLG=TRUE.
Flag: SCD2_FILTER_MISSING

### PARAM 13 — JOIN KEY DATA QUALITY
Check for NULL join keys and orphan fact keys. High NULL-risk columns and check SQLs
are in KB Section 3 Param 13.

### PARAM 14 — JOIN COLUMN PRUNING
Currently 0% pruning on all CMPGN.TGT tables. Note SO candidates post-clustering.
Flag post-clustering SO candidates from KB Section 3 Param 14.

### PARAM 15 — SPILL DETECTION
Flag large intermediate result sets likely to spill (large-to-large joins without date filter,
LATERAL FLATTEN on 7.4B rows, unbounded GROUP BY). See KB Section 3 Param 15.
Flag: HIGH_SPILL_RISK_NO_DATE_FILTER

### PARAM 16 — SQL ANTI-PATTERN DETECTION
Scan and flag 10 anti-patterns: SELECT *, CROSS JOIN, OR in JOIN, CAST in JOIN,
VARIANT in JOIN, DISTINCT-after-join, LIKE/ILIKE on large table, TEXT key join,
SCD2 join without IS_CURR_FLG, unbounded GROUP BY on 1B+ rows.
Full table with CMPGN-specific examples in KB Section 3 Param 16.

### PARAM 17 — QUERY HASH GROUPING
Use QUERY_PARAMETERIZED_HASH for workload pattern grouping.
Prefer ACCESS_HISTORY.BASE_OBJECTS_ACCESSED over LIKE '%tablename%' matching.
See KB Section 3 Param 17 for example query.

### PARAM 18 — SEARCH OPTIMIZATION ROI
No CMPGN.TGT tables have search optimization enabled.
Note candidates and unsupported column types from KB Section 3 Param 18.

### PARAM 19 — MATERIALIZATION STRATEGY
Flag repeated multi-table join patterns as dynamic table candidates.
Standard Snowflake materialized views do NOT support joins.
Dynamic table DDL template and known repeat patterns in KB Section 3 Param 19.

### PARAM 20 — CONSTRAINTS FOR JOIN ELIMINATION
Recommend PK/FK RELY after uniqueness validation.
Validation SQL and ALTER TABLE examples in KB Section 3 Param 20.

### PARAM 21 — SKEWNESS ANALYSIS
Assess three types of skew for every SQL touching large CMPGN.TGT tables:
- Type 1: Micro-partition skew (via SYSTEM$CLUSTERING_INFORMATION after clustering added)
- Type 2: Join key skew — top join key value distribution (flag if top value > 20%)
- Type 3: Column value skew — dominant filter/GROUP BY column values (flag if top > 30%)
Real Snowflake data, thresholds, check SQLs, and confirmed high-risk columns in KB Section 3 Param 21.
Flag: HIGH_PARTITION_SKEW | HIGH_JOIN_KEY_SKEW | HIGH_VALUE_SKEW

---

## Extended OPTIMIZATION SUMMARY Template

In addition to the existing header block, append these sections at the top of every `_optimized.sql`:

```sql
-- =============================================================
-- OPTIMIZATION SUMMARY (CMPGN DOMAIN — 21 PARAMETERS)
-- KB Reference: SKILL_EXT v2.0 (2026-05-20)
-- =============================================================
-- 1. GENERAL OPTIMIZATIONS:
--    - <list each rewrite, why applied, and performance impact>
--
-- 2. CLUSTERING ANALYSIS:
--    - Tables with clustering keys: NONE (all CMPGN.TGT unclustered as of 2026-05-20)
--    - Predicates aligned with clustering keys: N/A — no clustering exists
--    - Clustering candidates found in this SQL:
--      * <table_name> — recommended key: <column> — reason: <filter pattern>
--
-- 3. JOIN PATTERN ANALYSIS:
--    - Exploding join risk:           YES/NO — <table pair + row multiplier>
--    - Cartesian join detected:       YES/NO
--    - OR / CAST in join condition:   YES/NO — <list>
--    - Many-to-many join risk:        YES/NO — <join key + dim table>
--    - SCD2 join without IS_CURR_FLG: YES/NO — <table>
--    - Join key NULL risk:            YES/NO — <nullable column list>
--    - Orphan key risk:               YES/NO — <fact → dim relationship>
--
-- 4. SPILL RISK ANALYSIS:
--    - High spill risk operators: <list CTEs / join steps>
--    - Recommended fix: <filter pushdown / warehouse upsize / batch>
--
-- 5. SQL ANTI-PATTERNS DETECTED:
--    - <pattern_type> at line ~<N>: <description> → <fix applied>
--
-- 6. SEARCH OPTIMIZATION ROI:
--    - Currently enabled: NO (no CMPGN.TGT tables have SO)
--    - Candidates from this SQL: <table.column + ALTER TABLE SQL>
--
-- 7. MATERIALIZATION CANDIDATES:
--    - Repeated join patterns: YES/NO — <dynamic table recommendation>
--
-- 8. CONSTRAINTS RECOMMENDATION:
--    - PK/FK RELY candidates: <table relationships>
--    - Pre-condition: run uniqueness validation before applying RELY
--
-- 9. SNAPSHOT / BACKUP TABLE ALERT:
--    - <list any snapshot/backup tables referenced — flag for retention review>
--
-- 10. SKEWNESS ANALYSIS:
--    - Micro-partition skew:  NOT MEASURABLE — no clustering key on <table_name>
--                             Once clustering added, run SYSTEM$CLUSTERING_INFORMATION
--                             and flag if average_depth > 5
--    - Join key skew:         <YES/NO> — <column + top value % if checked>
--    - Column value skew:     <YES/NO> — <column + top value % if checked>
--    - Skew risk tables:      <table + column + flag label>
-- =============================================================
```

---

# ============================================================
# CMPGN KNOWLEDGE BASE
# Version: 2.0 | Last Updated: 2026-05-20
# Scope: CMPGN.TGT + UNIFD_MKTG_ANLTCS.STG
#
# SCHEMA NOTES:
# - CMPGN database has NO STG schema. Schemas available: TGT, UMT.
# - Campaign staging tables are in UNIFD_MKTG_ANLTCS.STG.
# - "STG" in this KB = UNIFD_MKTG_ANLTCS.STG
# - "TGT" in this KB = CMPGN.TGT
#
# DATA FRESHNESS: Row counts/sizes are snapshots from 2026-05-20.
# If user provides updated stats, use those instead.
#
# CRITICAL FINDING:
# ZERO tables in CMPGN.TGT have clustering keys.
# All large fact tables (100GB+) are unclustered — highest-priority optimization.
# ============================================================

## CRITICAL FACTS TO LOAD BEFORE ANALYSIS

- ALL CMPGN.TGT tables have ZERO clustering keys (as of 2026-05-20)
- Largest tables: USR_RCMNDTN_CNTNT_FCT (925 GB / 7.4B rows), CMPGN_CNVS_APP_CONTCT_FCT (485 GB / 7.4B rows)
- All major join keys (ACCT_KEY, CMPGN_KEY, etc.) are NULLABLE
- CMPGN database has NO STG schema — staging tables are in UNIFD_MKTG_ANLTCS.STG
- SCD2 dims (CMPGN_DIM, CMPGN_SBSCRBR_DIM, CUST_APP_DVC_DIM) require IS_CURR_FLG filter on joins
- VARIANT/ARRAY columns exist in USR_RCMNDTN_CNTNT_FCT and USR_RCMNDTN_FCT — NEVER join on these

---

## KB SECTION 1: TABLE INVENTORY

### 1A. CMPGN.TGT — Target Tables (Production)

| Table Name                          | Rows           | Size (GB) | Clustering Key | Type      | Status Note                      |
|-------------------------------------|---------------|-----------|----------------|-----------|----------------------------------|
| USR_RCMNDTN_CNTNT_FCT               | 7,485,724,908 | 925.79    | NONE           | FACT      | LARGEST — date filter mandatory  |
| CMPGN_CNVS_APP_CONTCT_FCT           | 7,473,946,985 | 485.41    | NONE           | FACT      | date filter mandatory            |
| CMPGN_CNVS_APP_RSPNS_FCT            | 2,300,433,021 | 106.39    | NONE           | FACT      | date filter mandatory            |
| CMPGN_CONTCT_FCT                    | 2,890,625,207 |  93.69    | NONE           | FACT      | date filter mandatory            |
| CMPGN_CONTCT_FCT_12122025           | 2,687,222,279 |  88.30    | NONE           | FACT SNAP | Backup — review retention        |
| USR_RCMNDTN_FCT                     |   689,635,861 |  41.61    | NONE           | FACT      | Medium priority                  |
| CMPGN_CNVS_APP_POST_EVNT_TRAK_FCT  |   787,359,855 |  28.81    | NONE           | FACT      | Medium priority                  |
| CMPGN_STB_VLDTN_FCT                 |   853,517,019 |  21.41    | NONE           | FACT      | Medium priority                  |
| CMPGN_RSPNS_AGG                     |   741,918,852 |  20.48    | NONE           | AGG FACT  | Pre-aggregated — use directly    |
| CMPGN_RSPNS_FCT                     |   747,751,409 |  19.91    | NONE           | FACT      | Medium priority                  |
| CMPGN_RSPNS_FCT_12122025            |   647,569,799 |  17.31    | NONE           | FACT SNAP | Backup — review retention        |
| USR_RCMNDTN_SUMRY_FCT               |    68,815,853 |  15.03    | NONE           | FACT      | Summary — prefer over base fact  |
| CMPGN_RSPNS_FCT_02282025            |   431,792,986 |  11.19    | NONE           | FACT SNAP | Backup — review retention        |
| CMPGN_CALL_TRAKNG_FCT               |    19,704,109 |   9.16    | NONE           | FACT      | Lower priority                   |
| CUST_APP_DVC_DIM                    |   146,483,497 |   6.57    | NONE           | DIM       | Large dim — NOT a small lookup   |
| CMPGN_CALL_TRAKNG_FCT_BKUP07072025 |    14,177,934 |   6.24    | NONE           | FACT SNAP | Backup — review retention        |
| CMPGN_SBSCRBR_DIM                   |    93,285,368 |   5.54    | NONE           | DIM       | Large dim — check key uniqueness |
| CMPGN_SBSCRBR_FCT                   |   232,181,853 |   5.33    | NONE           | FACT      | Lower priority                   |
| USR_RCMNDTN_FCT_20241111            |    73,266,790 |   3.44    | NONE           | FACT SNAP | Snapshot — review retention      |
| CMPGN_SBSCRBR_DIM_12122025          |    49,441,294 |   2.72    | NONE           | DIM SNAP  | Snapshot — review retention      |
| CUST_APP_CONSNT_FCT                 |    50,732,424 |   1.48    | NONE           | FACT      | Lower priority                   |
| CMPGN_LYLT_OFFR_FCT                 |    31,763,474 |   1.29    | NONE           | FACT      | Lower priority                   |
| CUST_APP_PROFL_ATTR_DIM             |    37,478,906 |   0.90    | NONE           | DIM       | Lower priority                   |
| CUST_PROFL_DIM                      |    28,609,547 |   0.82    | NONE           | DIM       | Lower priority                   |
| CUST_CTRL_GRP_RNDM_DIM              |    23,505,326 |   0.31    | NONE           | DIM       | Lower priority                   |
| TRCKRL_SUMRY_FCT                    |    21,798,672 |   0.20    | NONE           | FACT      | Lower priority                   |
| CMPGN_DIM                           |     1,098,434 |   0.04    | NONE           | DIM       | SCD2 — always filter IS_CURR_FLG |
| TRCKRL_FNNL_FCT                     |     1,052,419 |   0.02    | NONE           | FACT      | Small                            |
| RCMNDTN_CNTNT_DIM                   |        22,864 |   0.01    | NONE           | DIM       | Very small                       |
| CMPGN_MSG_DIM                       |         3,466 |   0.00    | NONE           | DIM       | Very small                       |
| CMPGN_PLCMNT_STB_DIM               |           138 |   0.00    | NONE           | DIM       | Lookup                           |
| RCMNDTN_RUL_DIM                     |           139 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_LYLT_OFFR_DIM                 |           234 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_CELL_DIM                      |         2,949 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_VNDR_DIM                      |            57 |   0.00    | NONE           | DIM       | Lookup                           |
| CONTCT_STS_DIM                      |        22,547 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_CHNL_DIM                      |            15 |   0.00    | NONE           | DIM       | Lookup                           |
| RSPNS_TYP_DIM                       |           330 |   0.00    | NONE           | DIM       | Lookup                           |
| APP_DVC_TYP_DIM                     |            21 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_CNVS_APP_DIM                  |        10,927 |   0.00    | NONE           | DIM       | Small                            |
| CMPGN_CNVS_APP_VRTN_DIM             |        22,603 |   0.00    | NONE           | DIM       | Small                            |
| CNVS_APP_STP_SPLT_DIM               |         5,028 |   0.00    | NONE           | DIM       | Small                            |
| APP_SRVY_CHC_DIM                    |           111 |   0.00    | NONE           | DIM       | Lookup                           |
| CMPGN_AUX_DIM                       |         4,923 |   0.00    | NONE           | DIM       | Small                            |
| CMPGN_EML_DIM                       |        11,543 |   0.00    | NONE           | DIM       | Small                            |
| CMPGN_DIM_12122025                  |     1,054,607 |   0.03    | NONE           | DIM SNAP  | Snapshot — review retention      |
| RCMNDTN_RUL_DIM_BKP                 |            19 |   0.00    | NONE           | DIM BKP   | Backup — review retention        |

### 1B. UNIFD_MKTG_ANLTCS.STG — Campaign Staging Tables

| Table Name                  | Rows          | Size (GB) | Clustering Key | Type      |
|-----------------------------|--------------|-----------|----------------|-----------|
| CMPGN_TVC_STG               | 388,671,358  | 4.17      | NONE           | STAGING   |
| SCRNG_MVR_FEE_CMPGN_DIM     | 2,622,747    | 0.06      | NONE           | DIM STAGE |
| CMPGN_SCRNG_TAG_FCT         | 1,910,623    | 0.04      | NONE           | FCT STAGE |
| OFFR_CMPGN_DIM_STG          | 57,025       | 0.00      | NONE           | DIM STAGE |
| OFFR_CMPGN_DIM_CHG0297720   | 391          | 0.00      | NONE           | DIM STAGE |
| CMPGN_TVC_EXCEP_STG         | 0            | 0.00      | NONE           | STAGING   |

### 1C. Snapshot / Backup Tables — Flag in Every OPTIMIZATION SUMMARY

- CMPGN.TGT.CMPGN_CONTCT_FCT_12122025           (88 GB)
- CMPGN.TGT.CMPGN_RSPNS_FCT_12122025            (17 GB)
- CMPGN.TGT.CMPGN_RSPNS_FCT_02282025            (11 GB)
- CMPGN.TGT.CMPGN_CALL_TRAKNG_FCT_BKUP07072025  (6 GB)
- CMPGN.TGT.USR_RCMNDTN_FCT_20241111            (3 GB)
- CMPGN.TGT.CMPGN_SBSCRBR_DIM_12122025          (3 GB)
- CMPGN.TGT.CMPGN_DIM_12122025
- CMPGN.TGT.RCMNDTN_RUL_DIM_BKP

---

## KB SECTION 2: KEY COLUMNS & JOIN MAP

### 2A. Common Join Keys

| Join Key              | Type   | Tables (Fact → Dim)                                                                  | Nullable? |
|-----------------------|--------|--------------------------------------------------------------------------------------|-----------|
| ACCT_KEY              | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT, CMPGN_RSPNS_AGG, USR_RCMNDTN_FCT, USR_RCMNDTN_CNTNT_FCT, CMPGN_CNVS_APP_CONTCT_FCT, CMPGN_CNVS_APP_RSPNS_FCT, CMPGN_SBSCRBR_DIM | YES |
| CMPGN_KEY             | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT, CMPGN_RSPNS_AGG → CMPGN_DIM                    | YES       |
| CMPGN_CHNL_KEY        | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT, CMPGN_CNVS_APP_CONTCT_FCT → CMPGN_CHNL_DIM    | YES       |
| CONTCT_STS_KEY        | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT, CMPGN_CNVS_APP_CONTCT_FCT → CONTCT_STS_DIM    | YES       |
| CMPGN_SUBSCRBR_KEY    | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT → CMPGN_SBSCRBR_DIM                             | YES       |
| CUST_PROFL_KEY        | NUMBER | CMPGN_CNVS_APP_CONTCT_FCT, CMPGN_CNVS_APP_RSPNS_FCT → CUST_PROFL_DIM             | YES       |
| CUST_APP_DVC_KEY      | NUMBER | CMPGN_CNVS_APP_CONTCT_FCT, CMPGN_CNVS_APP_RSPNS_FCT → CUST_APP_DVC_DIM           | YES       |
| RCMNDTN_RUL_KEY       | NUMBER | USR_RCMNDTN_FCT, USR_RCMNDTN_CNTNT_FCT → RCMNDTN_RUL_DIM                          | NO        |
| RSPNS_TYP_KEY         | NUMBER | CMPGN_RSPNS_FCT, CMPGN_RSPNS_AGG, CMPGN_CNVS_APP_RSPNS_FCT → RSPNS_TYP_DIM      | YES       |
| CMPGN_VNDR_KEY        | NUMBER | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT → CMPGN_VNDR_DIM                               | YES       |
| CMPGN_MSG_KEY         | NUMBER | CMPGN_CONTCT_FCT → CMPGN_MSG_DIM                                                   | YES       |
| CMPGN_CELL_KEY        | NUMBER | CMPGN_CONTCT_FCT → CMPGN_CELL_DIM                                                  | YES       |
| APP_DVC_TYP_KEY       | NUMBER | CMPGN_CNVS_APP_CONTCT_FCT → APP_DVC_TYP_DIM                                       | YES       |
| CMPGN_CNVS_APP_KEY    | NUMBER | CMPGN_CNVS_APP_CONTCT_FCT, CMPGN_CNVS_APP_RSPNS_FCT → CMPGN_CNVS_APP_DIM        | YES       |
| CNVS_APP_STP_SPLT_KEY | NUMBER | CMPGN_CNVS_APP_CONTCT_FCT, CMPGN_CNVS_APP_RSPNS_FCT → CNVS_APP_STP_SPLT_DIM     | YES       |

### 2B. Date / Timestamp Columns (Cluster / Filter Columns)

| Table                       | Primary Filter Column    | Secondary Filter Columns                   |
|-----------------------------|--------------------------|--------------------------------------------|
| CMPGN_CONTCT_FCT            | CONTCT_DT_TM (TIMESTAMP) | EXCTN_DT (DATE), EML_SENT_TS, CREA_TS     |
| CMPGN_RSPNS_FCT             | EVNT_RSPNS_DT (DATE)     | EVNT_RSPNS_TS (TIMESTAMP), CREA_TS        |
| CMPGN_RSPNS_AGG             | FRST_RSPNS_DT (DATE)     | LST_RSPNS_DT, FRST_RSPNS_TS, CREA_TS     |
| USR_RCMNDTN_FCT             | RCMNDTN_TS (TIMESTAMP)   | CREA_TS, UPDT_TS                          |
| USR_RCMNDTN_CNTNT_FCT       | RCMNDTN_DT (DATE)        | AIR_TS, EXP_TS, ORIG_AIR_TS, CREA_TS     |
| CMPGN_CNVS_APP_CONTCT_FCT   | CONTCT_TS (TIMESTAMP)    | CREA_TS, UPDT_TS                          |
| CMPGN_CNVS_APP_RSPNS_FCT    | EVNT_RSPNS_DT (DATE)     | EVNT_RSPNS_TS (TIMESTAMP), CREA_TS        |
| CMPGN_SBSCRBR_DIM           | CONTCT_DT (DATE)         | EFF_BGN_DT, EFF_END_DT, CREA_TS          |
| CUST_APP_DVC_DIM            | EFF_BGN_DT (DATE)        | EFF_END_DT, CREA_TS, UPDT_TS             |
| CMPGN_DIM                   | CMPGN_EFF_DT (DATE)      | CMPGN_END_DT, EFF_BGN_DT, EFF_END_DT     |

### 2C. VARIANT / ARRAY Columns — NEVER Join On These

| Table                     | Column                     | Type    | Rule                                |
|---------------------------|----------------------------|---------|-------------------------------------|
| USR_RCMNDTN_CNTNT_FCT     | RCMNDTN_VAR                | VARIANT | NEVER in JOIN — parse field first   |
| USR_RCMNDTN_CNTNT_FCT     | RCMNDTN_TGT_VAR            | VARIANT | Parse explicitly before use         |
| USR_RCMNDTN_CNTNT_FCT     | GENRES_LIST                | ARRAY   | LATERAL FLATTEN; filter rows first  |
| USR_RCMNDTN_CNTNT_FCT     | BDG_NM                     | ARRAY   | LATERAL FLATTEN before use          |
| USR_RCMNDTN_CNTNT_FCT     | TEAMS_LIST                 | ARRAY   | LATERAL FLATTEN before use          |
| USR_RCMNDTN_CNTNT_FCT     | RTGS_LIST                  | ARRAY   | LATERAL FLATTEN before use          |
| USR_RCMNDTN_FCT           | RCMNDTN_CNTNT_VAR          | VARIANT | Parse explicitly before use         |
| USR_RCMNDTN_FCT           | CNTNT_BDG_NM               | ARRAY   | LATERAL FLATTEN before use          |
| CMPGN_CONTCT_FCT          | MSG_CREATV_CMPNT_CMBND_ARR | ARRAY   | LATERAL FLATTEN before use          |

### 2D. Wide Tables — Never Use SELECT *

| Table                 | Column Count | Risk                                                   |
|-----------------------|-------------|--------------------------------------------------------|
| CMPGN_DIM             | 53          | 53 columns — always select explicitly                  |
| USR_RCMNDTN_CNTNT_FCT | 50          | 6 VARIANT/ARRAY — SELECT * pulls semi-structured data  |
| CMPGN_CONTCT_FCT      | 36          | 1 ARRAY column                                         |
| CMPGN_RSPNS_FCT       | 31          | 747M rows — expensive even without VARIANT             |
| USR_RCMNDTN_FCT       | 26          | 2 VARIANT/ARRAY columns                                |

---

## KB SECTION 3: ALL 21 PARAMETERS — CMPGN DOMAIN RULES

### PARAM 1: JOINS
  CMPGN_CONTCT_FCT → CMPGN_DIM (CMPGN_KEY — SCD2 IS_CURR_FLG='Y'), CMPGN_CHNL_DIM (CMPGN_CHNL_KEY — 15 rows),
    CONTCT_STS_DIM (CONTCT_STS_KEY — 22K rows), CMPGN_SBSCRBR_DIM (CMPGN_SUBSCRBR_KEY — 93M rows LARGE),
    CMPGN_VNDR_DIM (CMPGN_VNDR_KEY — 57 rows), CMPGN_MSG_DIM (CMPGN_MSG_KEY — 3.4K), CMPGN_CELL_DIM (2.9K)
  CMPGN_RSPNS_FCT → CMPGN_DIM (SCD2), CMPGN_CHNL_DIM, RSPNS_TYP_DIM (330 rows), CMPGN_SBSCRBR_DIM (93M LARGE),
    CMPGN_VNDR_DIM, CONTCT_STS_DIM
  CMPGN_CNVS_APP_CONTCT_FCT → CMPGN_CNVS_APP_DIM, CMPGN_CNVS_APP_VRTN_DIM, CNVS_APP_STP_SPLT_DIM,
    CMPGN_CHNL_DIM, CONTCT_STS_DIM, CUST_PROFL_DIM, CUST_APP_DVC_DIM (146M LARGE), APP_DVC_TYP_DIM (21 rows)
  USR_RCMNDTN_FCT → RCMNDTN_RUL_DIM (139 rows), RCMNDTN_CNTNT_DIM (22K)
  USR_RCMNDTN_CNTNT_FCT → RCMNDTN_RUL_DIM (139 rows — fan-out risk on 7.4B rows)
  CHECK RULE: Equality join only; no OR; no CAST in ON; no NULL-key on driving side.

### PARAM 2: FILTERS
  CMPGN_CONTCT_FCT (2.8B):         CONTCT_DT_TM — ALWAYS required
  CMPGN_RSPNS_FCT (747M):          EVNT_RSPNS_DT — ALWAYS required
  USR_RCMNDTN_CNTNT_FCT (7.4B):    RCMNDTN_DT — ALWAYS required + ACTV_FLG = true
  CMPGN_CNVS_APP_CONTCT_FCT (7.4B): CONTCT_TS — ALWAYS required
  CMPGN_CNVS_APP_RSPNS_FCT (2.3B): EVNT_RSPNS_DT — ALWAYS required
  CHECK: Large table (>100M rows) without date filter = MISSING_DATE_FILTER

### PARAM 3: AGGREGATIONS
  CMPGN_RSPNS_AGG → pre-aggregated; use directly for response count queries
  USR_RCMNDTN_SUMRY_FCT → summary; prefer over USR_RCMNDTN_FCT for totals
  GROUP BY on full table without date filter → UNBOUNDED_AGGREGATION_RISK
  COUNT(DISTINCT ACCT_KEY) on 1B+ rows → EXPENSIVE_COUNT_DISTINCT

### PARAM 4: REDUCE SCANS
  CRITICAL (date filter non-negotiable): USR_RCMNDTN_CNTNT_FCT (7.4B), CMPGN_CNVS_APP_CONTCT_FCT (7.4B),
    CMPGN_CNVS_APP_RSPNS_FCT (2.3B), CMPGN_CONTCT_FCT (2.8B)
  HIGH: CMPGN_CNVS_APP_POST_EVNT_TRAK_FCT (787M), CMPGN_STB_VLDTN_FCT (853M), CMPGN_RSPNS_AGG (741M), CMPGN_RSPNS_FCT (747M)
  Flag: FULL_SCAN_CRITICAL for CRITICAL table without date filter.

### PARAM 5: IMPROVE JOINS
  Large fact on driving (left) side; small dim on right.
  CMPGN_SBSCRBR_DIM (93M) and CUST_APP_DVC_DIM (146M) are NOT small dims — pre-filter before joining.
  Pre-filter both sides of large-to-large joins in CTEs. Prefer NUMBER _KEY surrogate joins over TEXT.

### PARAM 6: PREDICATE PUSHDOWN
  CORRECT:
    WITH filtered AS (
        SELECT acct_key, cmpgn_key FROM CMPGN.TGT.CMPGN_CONTCT_FCT
        WHERE contct_dt_tm >= '2025-01-01'  -- filter in CTE
    )
    SELECT ... FROM filtered JOIN CMPGN.TGT.CMPGN_DIM ...
  WRONG: filter in WHERE clause AFTER a full JOIN on a large table.
  Flag: MISSING_PREDICATE_PUSHDOWN

### PARAM 7: AVOID SELECT *
  Flag SELECT_STAR_WITH_VARIANT_RISK on all tables in Section 2D.

### PARAM 8: CLUSTERING ALIGNMENT
  CURRENT STATE: ALL CMPGN.TGT TABLES HAVE NO CLUSTERING KEY. Full micro-partition scan on every query.
  RECOMMENDED:
    USR_RCMNDTN_CNTNT_FCT → RCMNDTN_DT (CRITICAL — 925 GB, ~59,251 est. partitions)
    CMPGN_CNVS_APP_CONTCT_FCT → DATE(CONTCT_TS) (CRITICAL — 485 GB, ~31,114 est. partitions)
    CMPGN_CONTCT_FCT → DATE(CONTCT_DT_TM) (CRITICAL — 93 GB, ~6,000 est. partitions)
    CMPGN_CNVS_APP_RSPNS_FCT → EVNT_RSPNS_DT (HIGH — 106 GB, ~6,812 est. partitions)
    CMPGN_RSPNS_FCT → EVNT_RSPNS_DT (HIGH — 19 GB, ~1,275 est. partitions)
    CMPGN_RSPNS_AGG → FRST_RSPNS_DT (HIGH — 20 GB, ~1,317 est. partitions)
    USR_RCMNDTN_FCT → DATE(RCMNDTN_TS) (HIGH — 41 GB, ~2,663 est. partitions)
  DDL: ALTER TABLE CMPGN.TGT.CMPGN_CONTCT_FCT CLUSTER BY (DATE(CONTCT_DT_TM));
       ALTER TABLE CMPGN.TGT.CMPGN_RSPNS_FCT CLUSTER BY (EVNT_RSPNS_DT);
       ALTER TABLE CMPGN.TGT.USR_RCMNDTN_CNTNT_FCT CLUSTER BY (RCMNDTN_DT);
       ALTER TABLE CMPGN.TGT.CMPGN_CNVS_APP_CONTCT_FCT CLUSTER BY (DATE(CONTCT_TS));
  Always note: 'Clustering key missing — predicate pruning NOT active'

### PARAM 9: CLUSTERING CANDIDATES (Priority)
  1. USR_RCMNDTN_CNTNT_FCT (925 GB, 7.4B rows)
  2. CMPGN_CNVS_APP_CONTCT_FCT (485 GB, 7.4B rows)
  3. CMPGN_CNVS_APP_RSPNS_FCT (106 GB, 2.3B rows)
  4. CMPGN_CONTCT_FCT (93 GB, 2.8B rows)
  5. USR_RCMNDTN_FCT (41 GB, 689M rows)
  6. CMPGN_RSPNS_AGG (20 GB, 741M rows)
  7. CMPGN_RSPNS_FCT (19 GB, 747M rows)

### PARAM 10: EXPLODING JOIN DETECTION
  HIGH-RISK PAIRS:
    CMPGN_CONTCT_FCT (2.8B) + CMPGN_RSPNS_FCT (747M) ON ACCT_KEY → nullable both sides → HIGH multiplier risk
    CMPGN_CNVS_APP_CONTCT_FCT (7.4B) + CMPGN_CNVS_APP_RSPNS_FCT (2.3B) → both very large, pre-filter mandatory
    USR_RCMNDTN_CNTNT_FCT (7.4B) + USR_RCMNDTN_FCT (689M) ON RCMNDTN_RUL_KEY → 139-row dim = severe fan-out
  RULES:
    output_rows / input_rows >= 10 → EXPLODING_JOIN_RISK
    CartesianJoin operator → CRITICAL_CARTESIAN_JOIN
    Two large facts joined without date filter on both sides → flag immediately

### PARAM 11: JOIN CONDITION QUALITY
  All _KEY columns are NUMBER — join must be NUMBER = NUMBER.
  CMPGN_SBSCRBR_DIM.SRC_SBSCRBR_KEY is TEXT — do not confuse with CMPGN_SUBSCRBR_KEY (NUMBER).
  NEVER join on VARIANT (RCMNDTN_VAR, RCMNDTN_CNTNT_VAR).
  SCD2 range joins on CMPGN_DIM, CMPGN_SBSCRBR_DIM, CUST_APP_DVC_DIM → flag SCD2_RANGE_JOIN_NOTE.
  FLAGS: OR_JOIN_CONDITION_DETECTED | FUNCTION_IN_JOIN_DETECTED | VARIANT_JOIN_DETECTED_CRITICAL | SUBOPTIMAL_JOIN_KEY_TYPE

### PARAM 12: MANY-TO-MANY JOIN RISK
  CMPGN_DIM: PK = CMPGN_KEY + IS_CURR_FLG='Y'. Missing IS_CURR_FLG → SCD2_FILTER_MISSING
    Check: SELECT CMPGN_KEY, COUNT(*) FROM CMPGN.TGT.CMPGN_DIM WHERE IS_CURR_FLG='Y' GROUP BY CMPGN_KEY HAVING COUNT(*)>1;
  CMPGN_SBSCRBR_DIM: PK = CMPGN_SBSCRBR_KEY + IS_CURR_FLG=TRUE (93M rows)
  CUST_APP_DVC_DIM: PK = CUST_APP_DVC_KEY + CUST_PROFL_KEY (both NOT NULL, 146M rows)

### PARAM 13: JOIN KEY DATA QUALITY
  HIGH NULL RISK: CMPGN_CONTCT_FCT.ACCT_KEY, CMPGN_CONTCT_FCT.CMPGN_KEY, CMPGN_RSPNS_FCT.ACCT_KEY,
    USR_RCMNDTN_FCT.ACCT_KEY, USR_RCMNDTN_CNTNT_FCT.ACCT_KEY, CMPGN_CNVS_APP_CONTCT_FCT.ACCT_KEY
  NULL CHECK:
    SELECT COUNT_IF(ACCT_KEY IS NULL) AS null_acct_key, COUNT_IF(CMPGN_KEY IS NULL) AS null_cmpgn_key
    FROM CMPGN.TGT.CMPGN_CONTCT_FCT WHERE CONTCT_DT_TM >= DATEADD(day, -7, CURRENT_DATE);
  ORPHAN CHECK:
    SELECT COUNT(*) AS orphan_rows FROM CMPGN.TGT.CMPGN_CONTCT_FCT f
    LEFT JOIN CMPGN.TGT.CMPGN_DIM d ON f.cmpgn_key = d.cmpgn_key
    WHERE d.cmpgn_key IS NULL AND f.CONTCT_DT_TM >= DATEADD(day, -7, CURRENT_DATE);

### PARAM 14: JOIN COLUMN PRUNING
  CURRENT: 0% pruning — no clustering. Post-clustering SO candidates:
    CMPGN_CONTCT_FCT.CMPGN_KEY, CMPGN_RSPNS_FCT.CMPGN_KEY, USR_RCMNDTN_FCT.RCMNDTN_RUL_KEY,
    CMPGN_CNVS_APP_CONTCT_FCT.CMPGN_CNVS_APP_KEY
  DDL: ALTER TABLE CMPGN.TGT.CMPGN_CONTCT_FCT ADD SEARCH OPTIMIZATION ON EQUALITY(CMPGN_KEY);
       ALTER TABLE CMPGN.TGT.CMPGN_RSPNS_FCT ADD SEARCH OPTIMIZATION ON EQUALITY(CMPGN_KEY);

### PARAM 15: SPILL DETECTION
  1. CMPGN_CONTCT_FCT (2.8B) + CMPGN_RSPNS_FCT (747M) without date filter → FIX: CTE pre-filter
  2. LATERAL FLATTEN(USR_RCMNDTN_CNTNT_FCT.GENRES_LIST) on 7.4B without pre-filter → FIX: filter ACTV_FLG+date BEFORE
  3. GROUP BY on full CMPGN_CONTCT_FCT (2.8B) → FIX: add date filter before GROUP BY
  FLAG: combined > 1B rows AND no date filter → HIGH_SPILL_RISK_NO_DATE_FILTER

### PARAM 16: SQL ANTI-PATTERN DETECTION

| Anti-Pattern                      | Risk     | Fix                                                     |
|-----------------------------------|----------|---------------------------------------------------------|
| SELECT * on large/VARIANT table   | CRITICAL | Explicit column list; skip VARIANT/ARRAY unless needed  |
| CROSS JOIN                        | CRITICAL | Verify intentional; add join condition if not           |
| OR in JOIN ON clause              | HIGH     | Rewrite as UNION ALL of two separate joins              |
| CAST / function in JOIN ON        | HIGH     | Pre-cast in CTE; join on pre-cast column                |
| VARIANT column in JOIN condition  | CRITICAL | Extract field first; never join on VARIANT              |
| SELECT DISTINCT after multi-join  | HIGH     | Fix join cardinality at source instead                  |
| LIKE / ILIKE on large table       | MEDIUM   | Use equality filter or search optimization              |
| JOIN on TEXT key not surrogate    | MEDIUM   | Use NUMBER _KEY surrogate key join instead              |
| SCD2 dim join without IS_CURR_FLG | HIGH     | Add AND IS_CURR_FLG = TRUE to dim join condition        |
| Unbounded GROUP BY on 1B+ rows    | CRITICAL | Add mandatory date filter before GROUP BY               |

### PARAM 17: QUERY HASH GROUPING
  Use QUERY_PARAMETERIZED_HASH for pattern grouping; QUERY_HASH for exact duplicates.
  Prefer ACCESS_HISTORY.BASE_OBJECTS_ACCESSED over LIKE '%tablename%' matching.
  WORKLOAD QUERY:
    SELECT query_parameterized_hash, COUNT(*) AS executions, AVG(total_elapsed_time)/1000 AS avg_sec,
           ANY_VALUE(LEFT(query_text,500)) AS sample
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    WHERE database_name IN ('CMPGN','UNIFD_MKTG_ANLTCS')
      AND start_time >= DATEADD(day, -30, CURRENT_TIMESTAMP())
    GROUP BY query_parameterized_hash ORDER BY executions DESC;

### PARAM 18: SEARCH OPTIMIZATION ROI
  CURRENT: No CMPGN.TGT tables have SO enabled.
  CANDIDATES (after clustering): CMPGN_CONTCT_FCT.CMPGN_KEY, CMPGN_RSPNS_FCT.CMPGN_KEY,
    USR_RCMNDTN_FCT.ACCT_KEY, USR_RCMNDTN_CNTNT_FCT.ACCT_KEY
  NOT SUPPORTED: VARIANT, ARRAY, OR predicates, LIKE/ILIKE
  ROI VALIDATION:
    SELECT table_name, SUM(partitions_pruned_additional) AS so_benefit, SUM(num_scans) AS scans
    FROM SNOWFLAKE.ACCOUNT_USAGE.SEARCH_OPTIMIZATION_BENEFITS
    WHERE table_name ILIKE '%CMPGN%' AND start_time >= DATEADD(day, -14, CURRENT_TIMESTAMP())
    GROUP BY table_name;

### PARAM 19: MATERIALIZATION STRATEGY
  PATTERN A — CMPGN_CONTCT_FCT + CMPGN_RSPNS_FCT (joined daily across many jobs):
    → CREATE DYNAMIC TABLE CMPGN.TGT.CMPGN_CONTCT_RSPNS_DAILY_DT TARGET_LAG='1 hour'
      WAREHOUSE=CDO_MKTG_ANLTCS_XL_WH AS
      SELECT c.acct_key, c.cmpgn_key, c.contct_dt_tm, r.evnt_rspns_dt, r.rspns_typ_key, c.cmpgn_chnl_key
      FROM CMPGN.TGT.CMPGN_CONTCT_FCT c JOIN CMPGN.TGT.CMPGN_RSPNS_FCT r
        ON c.acct_key=r.acct_key AND c.cmpgn_key=r.cmpgn_key
      WHERE c.contct_dt_tm >= DATEADD(day,-90,CURRENT_DATE);
  PATTERN B — CMPGN_DIM (53 cols, joined everywhere): use slim CTE with 3–5 key columns
  PATTERN C — USR_RCMNDTN_CNTNT_FCT flattened on GENRES_LIST: materialize as staging/dynamic table
  NOTE: Standard Snowflake materialized views do NOT support multi-table JOINs.

### PARAM 20: CONSTRAINTS FOR JOIN ELIMINATION
  VALIDATE BEFORE RELY:
    SELECT cmpgn_key, COUNT(*) FROM CMPGN.TGT.CMPGN_DIM WHERE IS_CURR_FLG='Y' GROUP BY cmpgn_key HAVING COUNT(*)>1;
    SELECT cmpgn_sbscrbr_key, COUNT(*) FROM CMPGN.TGT.CMPGN_SBSCRBR_DIM WHERE IS_CURR_FLG=TRUE GROUP BY cmpgn_sbscrbr_key HAVING COUNT(*)>1;
  ADD RELY (only after validation passes):
    ALTER TABLE CMPGN.TGT.CMPGN_DIM ADD CONSTRAINT PK_CMPGN_DIM PRIMARY KEY (CMPGN_KEY) RELY;
    ALTER TABLE CMPGN.TGT.CMPGN_CONTCT_FCT ADD CONSTRAINT FK_CONTCT_CMPGN FOREIGN KEY (CMPGN_KEY)
      REFERENCES CMPGN.TGT.CMPGN_DIM(CMPGN_KEY) RELY;
  CAUTION: Snowflake does NOT enforce constraints. Only add RELY after Params 12 and 13 pass.

### PARAM 21: SKEWNESS ANALYSIS
Three types of skew — assess for every SQL touching large CMPGN.TGT tables.

TYPE 1 — MICRO-PARTITION SKEW (validated 2026-05-20):
  ALL CMPGN.TGT tables unclustered → SYSTEM$CLUSTERING_INFORMATION returns error.
  Note: 'Partition skew unknown — no clustering key defined'
  ESTIMATED PARTITIONS (table_size / ~16MB per partition):
    USR_RCMNDTN_CNTNT_FCT     → ~59,251 partitions (925 GB) — ALL unordered — full scan every query
    CMPGN_CNVS_APP_CONTCT_FCT → ~31,114 partitions (486 GB) — ALL unordered
    CMPGN_CNVS_APP_RSPNS_FCT  → ~6,812  partitions (106 GB) — ALL unordered
    CMPGN_CONTCT_FCT          → ~6,000  partitions  (93 GB) — ALL unordered
    USR_RCMNDTN_FCT           → ~2,663  partitions  (41 GB) — ALL unordered
    CMPGN_RSPNS_AGG           → ~1,317  partitions  (20 GB) — ALL unordered
    CMPGN_RSPNS_FCT           → ~1,275  partitions  (19 GB) — ALL unordered
  Adding DATE clustering on USR_RCMNDTN_CNTNT_FCT could reduce ~59,251 partitions to ~30–90 per daily query.
  CHECK SQL (run after clustering added):
    SELECT PARSE_JSON(SYSTEM$CLUSTERING_INFORMATION('CMPGN.TGT.CMPGN_CONTCT_FCT')):average_depth::FLOAT AS avg_depth,
           CASE WHEN ... > 10 THEN 'HIGH_PARTITION_SKEW' WHEN ... > 5 THEN 'MEDIUM_PARTITION_SKEW' ELSE 'LOW' END AS skew_level;
  Thresholds: avg_depth > 10 → HIGH_PARTITION_SKEW | > 5 → MEDIUM_PARTITION_SKEW | <= 5 → LOW_PARTITION_SKEW

TYPE 2 — JOIN KEY SKEW (real Snowflake data, last 30 days, 2026-05-20):
  Thresholds: top value > 20% → HIGH_JOIN_KEY_SKEW | 10–20% → MEDIUM | < 10% → LOW
  *** CMPGN_CNVS_APP_CONTCT_FCT.CMPGN_CHNL_KEY → HIGH_JOIN_KEY_SKEW (82.34% in one channel key 265237161133786789)
      ONE channel = 82% of 7.4B rows → severe thread imbalance — pre-filter by CMPGN_CHNL_KEY or UNION ALL split ***
  CMPGN_CONTCT_FCT.CMPGN_KEY     → MEDIUM_JOIN_KEY_SKEW (12.30% top campaign 643658747859710439)
  CMPGN_RSPNS_FCT.CMPGN_KEY      → MEDIUM_JOIN_KEY_SKEW (12.11% top campaign 84404543318097148)
  CMPGN_CONTCT_FCT.ACCT_KEY      → NO_SKEW (0.004% top value — highly distributed)
  CHECK SQL:
    SELECT CMPGN_KEY, COUNT(*) AS row_count, ROUND(COUNT(*)/SUM(COUNT(*)) OVER()*100,4) AS pct
    FROM CMPGN.TGT.CMPGN_CONTCT_FCT WHERE CONTCT_DT_TM >= DATEADD(day,-30,CURRENT_DATE)
    GROUP BY CMPGN_KEY ORDER BY row_count DESC LIMIT 50;

TYPE 3 — COLUMN VALUE SKEW (real Snowflake data, last 30 days, 2026-05-20):
  Thresholds: top value > 30% → HIGH_VALUE_SKEW | 15–30% → MEDIUM | < 15% → ACCEPTABLE
  *** USR_RCMNDTN_CNTNT_FCT.ACTV_FLG → HIGH_VALUE_SKEW: 77.06% = false, 22.94% = true
      ALWAYS filter ACTV_FLG = true before any join or aggregation — reduces scan by 77% ***
  *** CMPGN_RSPNS_FCT.RSPNS_TYP_KEY → HIGH_VALUE_SKEW: 60.10% in top value (459420037874332702)
      ONE response type = 60% of all responses — filter RSPNS_TYP_KEY before aggregating ***
  *** CMPGN_CONTCT_FCT.SRC_SYS_NM → HIGH_VALUE_SKEW: 57.07% SALESFORCE, 42.91% SALESFORCE MARKETING CLOUD
      Two Salesforce variants = 99.98% of all contacts ***
  CMPGN_CONTCT_FCT.CTRL_FLG → MEDIUM_VALUE_SKEW + DATA QUALITY ISSUE:
    'No' (42.93%), true (30.64%), false (26.43%) — mixed string/boolean types
    Flag: CTRL_FLG_DATA_TYPE_INCONSISTENCY — recommend standardizing to BOOLEAN
  CHECK SQL:
    SELECT RSPNS_TYP_KEY::STRING AS col_value, COUNT(*) AS value_count,
           ROUND(COUNT(*)/SUM(COUNT(*)) OVER()*100,2) AS pct_of_table
    FROM CMPGN.TGT.CMPGN_RSPNS_FCT WHERE EVNT_RSPNS_DT >= DATEADD(day,-30,CURRENT_DATE)
    GROUP BY RSPNS_TYP_KEY QUALIFY ROW_NUMBER() OVER(ORDER BY value_count DESC) <= 20;

---

## KB SECTION 4: OPTIMIZATION PRIORITY MATRIX

| Priority | Finding                                          | Affected Tables                                    | Action                                               |
|----------|--------------------------------------------------|----------------------------------------------------|------------------------------------------------------|
| P1       | No clustering on any TGT table                   | All large facts (1B–7.4B rows)                     | CLUSTER BY date column on top 7 tables               |
| P1       | Full scan risk on 7.4B row tables                | USR_RCMNDTN_CNTNT_FCT, CMPGN_CNVS_APP_CONTCT_FCT  | Always enforce date filter in WHERE clause           |
| P2       | Snapshot/backup tables consuming 130+ GB         | 9 snapshot tables (Section 1C)                     | Review retention; DROP or ARCHIVE                    |
| P2       | SCD2 joins without IS_CURR_FLG filter            | CMPGN_DIM, CMPGN_SBSCRBR_DIM, CUST_APP_DVC_DIM    | Add IS_CURR_FLG filter on every SCD2 dim join        |
| P2       | Large-to-large fact joins without date filters   | CMPGN_CONTCT_FCT + CMPGN_RSPNS_FCT                | Pre-filter both sides in CTEs before joining         |
| P2       | Partition skew unmeasurable (no clustering)       | All large CMPGN.TGT fact tables                    | Add clustering; then run SYSTEM$CLUSTERING_INFORMATION |
| P3       | Nullable ACCT_KEY on 7.4B row tables             | USR_RCMNDTN_CNTNT_FCT, CMPGN_CNVS_APP_CONTCT_FCT  | Validate NULL key volumes; handle in ETL             |
| P3       | VARIANT/ARRAY columns in wide table scans        | USR_RCMNDTN_CNTNT_FCT, USR_RCMNDTN_FCT            | Explicit column select; flatten only when needed     |
| P3       | ACTV_FLG = false (77%) — HIGH_VALUE_SKEW         | USR_RCMNDTN_CNTNT_FCT                             | Always pre-filter ACTV_FLG = true before joins/agg  |
| P3       | RSPNS_TYP_KEY single value = 60% — HIGH_VALUE_SKEW | CMPGN_RSPNS_FCT                               | Filter RSPNS_TYP_KEY before aggregating              |
| P3       | CMPGN_CHNL_KEY single channel = 82% — HIGH_JOIN_KEY_SKEW | CMPGN_CNVS_APP_CONTCT_FCT             | Pre-filter or UNION ALL split on CMPGN_CHNL_KEY     |
| P3       | CTRL_FLG mixed type (string + boolean)           | CMPGN_CONTCT_FCT                                  | Standardize CTRL_FLG to BOOLEAN in ETL              |
| P3       | Join key skew on CMPGN_KEY (12%)                 | CMPGN_CONTCT_FCT, CMPGN_RSPNS_FCT                 | Run skew check; pre-aggregate if top value > 20%    |
| P4       | No search optimization enabled                   | All TGT tables                                     | Evaluate post-clustering; add on high-join columns   |
| P4       | No RELY constraints                              | CMPGN_DIM, CMPGN_SBSCRBR_DIM                      | Validate uniqueness then add PK/FK RELY              |