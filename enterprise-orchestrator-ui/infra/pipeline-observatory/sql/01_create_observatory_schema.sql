-- ATT-DP10 Pipeline Observatory Schema
-- Replace __CATALOG__ and __SCHEMA__ before execution

CREATE SCHEMA IF NOT EXISTS __CATALOG__.__SCHEMA__;

-- Table 1: Job Run History
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.tbl_job_runs (
  run_id STRING NOT NULL,
  job_name STRING NOT NULL,
  repo STRING NOT NULL,  -- CMPGN, UMA, RVNU
  status STRING,  -- Success, Failed, Running, Cancelled
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  duration_minutes DECIMAL(10, 2),
  run_date DATE,
  created_at TIMESTAMP DEFAULT current_timestamp(),
  CONSTRAINT pk_job_runs PRIMARY KEY (run_id)
)
USING DELTA;

-- Table 2: Data Quality Incidents (Monte Carlo)
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.tbl_dq_incidents (
  incident_id STRING NOT NULL,
  table_name STRING NOT NULL,
  incident_type STRING,  -- Missing values, Schema change, Duplicate rows, etc.
  severity STRING,  -- Critical, High, Medium, Low
  status STRING,  -- Active, Resolved, Expected
  created_at TIMESTAMP,
  resolved_at TIMESTAMP,
  description STRING,
  inserted_at TIMESTAMP DEFAULT current_timestamp(),
  CONSTRAINT pk_dq_incidents PRIMARY KEY (incident_id)
)
USING DELTA;

-- Table 3: SQL Optimization Recommendations
CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.tbl_sql_optimization (
  opt_id STRING NOT NULL,
  job_name STRING NOT NULL,
  repo STRING NOT NULL,
  parameter_name STRING,  -- e.g., use_clustering_key, reduce_cte, push_down_filter
  recommendation TEXT,
  priority STRING,  -- Critical, High, Medium, Low
  estimated_improvement_pct DECIMAL(10, 2),
  current_query_cost DECIMAL(15, 2),
  optimized_query_cost DECIMAL(15, 2),
  created_at TIMESTAMP,
  inserted_at TIMESTAMP DEFAULT current_timestamp(),
  CONSTRAINT pk_sql_opt PRIMARY KEY (opt_id)
)
USING DELTA;

-- Creating indexes/views for dashboard queries
CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.vw_job_health_summary AS
SELECT
  repo,
  COUNT(DISTINCT job_name) AS total_jobs,
  SUM(CASE WHEN status = 'Success' THEN 1 ELSE 0 END) AS success_count,
  SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) AS failed_count,
  SUM(CASE WHEN status = 'Running' THEN 1 ELSE 0 END) AS running_count,
  ROUND(
    100.0 * SUM(CASE WHEN status = 'Success' THEN 1 ELSE 0 END)
    / NULLIF(COUNT(*), 0),
    2
  ) AS success_rate_pct,
  AVG(duration_minutes) AS avg_duration_min,
  DATE(MAX(end_time)) AS last_run_date
FROM __CATALOG__.__SCHEMA__.tbl_job_runs
WHERE run_date >= CURRENT_DATE - INTERVAL 7 DAY
GROUP BY repo;

CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.vw_dq_health_summary AS
SELECT
  COUNT(DISTINCT table_name) AS tables_with_incidents,
  SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) AS critical_count,
  SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) AS high_count,
  SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_incidents,
  ROUND(
    100.0 * COUNT(CASE WHEN status = 'Resolved' THEN 1 END)
    / NULLIF(COUNT(*), 0),
    2
  ) AS resolution_rate_pct
FROM __CATALOG__.__SCHEMA__.tbl_dq_incidents
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL 30 DAY;
