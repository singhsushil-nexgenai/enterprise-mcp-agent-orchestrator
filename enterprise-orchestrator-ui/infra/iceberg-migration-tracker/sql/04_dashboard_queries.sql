-- Replace these tokens before execution:
-- __CATALOG__, __SCHEMA__, __ENV__

-- Q1: KPI summary for selected environment
SELECT *
FROM __CATALOG__.__SCHEMA__.vw_iceberg_migration_kpis
WHERE environment = '__ENV__';

-- Q2: Category distribution
SELECT
  migration_category,
  COUNT(*) AS table_count
FROM __CATALOG__.__SCHEMA__.vw_iceberg_migration_tracker
WHERE environment = '__ENV__'
GROUP BY migration_category
ORDER BY table_count DESC;

-- Q3: Top reasons for Not Eligible
SELECT
  COALESCE(migration_reason, 'UNSPECIFIED') AS migration_reason,
  COUNT(*) AS table_count
FROM __CATALOG__.__SCHEMA__.vw_iceberg_migration_tracker
WHERE environment = '__ENV__'
  AND migration_category = 'Not Eligible'
GROUP BY COALESCE(migration_reason, 'UNSPECIFIED')
ORDER BY table_count DESC
LIMIT 20;

-- Q4: Daily migration trend (Migrated)
SELECT
  DATE(updated_at) AS migration_date,
  COUNT(*) AS migrated_count
FROM __CATALOG__.__SCHEMA__.vw_iceberg_migration_tracker
WHERE environment = '__ENV__'
  AND migration_category = 'Migrated'
GROUP BY DATE(updated_at)
ORDER BY migration_date;

-- Q5: Table-level detail grid
SELECT
  table_name,
  source_system,
  migration_category,
  migration_reason,
  CONCAT_WS('.', target_catalog, target_schema, target_table) AS iceberg_target,
  updated_at
FROM __CATALOG__.__SCHEMA__.vw_iceberg_migration_tracker
WHERE environment = '__ENV__'
ORDER BY updated_at DESC, table_name;
