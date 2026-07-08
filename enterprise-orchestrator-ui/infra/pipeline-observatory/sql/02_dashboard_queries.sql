-- Dashboard Query: Job Health Overview
-- Replace __CATALOG__, __SCHEMA__, __REPO__ before execution

SELECT
  repo,
  total_jobs,
  success_count,
  failed_count,
  running_count,
  success_rate_pct,
  ROUND(avg_duration_min, 1) AS avg_duration_min,
  last_run_date
FROM __CATALOG__.__SCHEMA__.vw_job_health_summary
WHERE repo = '__REPO__' OR '__REPO__' = 'ALL';

-- Dashboard Query: Last 10 Failed Jobs
SELECT
  job_name,
  repo,
  status,
  start_time,
  end_time,
  duration_minutes
FROM __CATALOG__.__SCHEMA__.tbl_job_runs
WHERE status = 'Failed'
  AND repo = '__REPO__' OR '__REPO__' = 'ALL'
  AND run_date >= CURRENT_DATE - INTERVAL 7 DAY
ORDER BY end_time DESC
LIMIT 10;

-- Dashboard Query: DQ Incidents by Type
SELECT
  incident_type,
  COUNT(*) AS incident_count,
  SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) AS critical_count,
  SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_count
FROM __CATALOG__.__SCHEMA__.tbl_dq_incidents
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL 30 DAY
GROUP BY incident_type
ORDER BY incident_count DESC;

-- Dashboard Query: Top 20 Tables with Incidents
SELECT
  table_name,
  incident_type,
  severity,
  status,
  COUNT(*) AS incident_count,
  MAX(created_at) AS latest_incident
FROM __CATALOG__.__SCHEMA__.tbl_dq_incidents
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL 30 DAY
GROUP BY table_name, incident_type, severity, status
ORDER BY incident_count DESC
LIMIT 20;

-- Dashboard Query: Incident Trend (Last 30 Days)
SELECT
  DATE(created_at) AS incident_date,
  COUNT(*) AS total_incidents,
  SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) AS critical_count,
  SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_count
FROM __CATALOG__.__SCHEMA__.tbl_dq_incidents
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL 30 DAY
GROUP BY DATE(created_at)
ORDER BY incident_date DESC;

-- Dashboard Query: SQL Optimization Recommendations (Top 10 Jobs)
SELECT
  job_name,
  repo,
  parameter_name,
  recommendation,
  priority,
  estimated_improvement_pct,
  current_query_cost,
  optimized_query_cost,
  ROUND(current_query_cost - optimized_query_cost, 2) AS savings
FROM __CATALOG__.__SCHEMA__.tbl_sql_optimization
WHERE repo = '__REPO__' OR '__REPO__' = 'ALL'
ORDER BY estimated_improvement_pct DESC, priority
LIMIT 10;

-- Dashboard Query: Daily Job Run Trend (Last 30 Days)
SELECT
  run_date,
  COUNT(*) AS total_runs,
  SUM(CASE WHEN status = 'Success' THEN 1 ELSE 0 END) AS success_runs,
  SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) AS failed_runs,
  SUM(CASE WHEN status = 'Running' THEN 1 ELSE 0 END) AS running_runs
FROM __CATALOG__.__SCHEMA__.tbl_job_runs
WHERE run_date >= CURRENT_DATE - INTERVAL 30 DAY
GROUP BY run_date
ORDER BY run_date DESC;

-- Dashboard Query: Avg Execution Time Per Job (Top 5)
SELECT
  job_name,
  COUNT(*) AS run_count,
  ROUND(AVG(duration_minutes), 2) AS avg_duration_min,
  ROUND(MIN(duration_minutes), 2) AS min_duration_min,
  ROUND(MAX(duration_minutes), 2) AS max_duration_min
FROM __CATALOG__.__SCHEMA__.tbl_job_runs
WHERE run_date >= CURRENT_DATE - INTERVAL 30 DAY
  AND status IN ('Success', 'Failed')
GROUP BY job_name
ORDER BY avg_duration_min DESC
LIMIT 5;
