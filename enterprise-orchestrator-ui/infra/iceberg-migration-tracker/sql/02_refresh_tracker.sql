-- Replace these tokens before execution:
-- __CATALOG__, __SCHEMA__, __SOURCE_TABLE__

MERGE INTO __CATALOG__.__SCHEMA__.migration_inventory_current t
USING (
  SELECT
    table_name,
    source_system,
    CASE
      WHEN migration_category IN (
        'Eligible to Migrate',
        'Migrated',
        'Not Eligible',
        'In Progress',
        'Pending Analysis'
      ) THEN migration_category
      WHEN migration_category IS NULL THEN 'Pending Analysis'
      ELSE 'Pending Analysis'
    END AS migration_category,
    migration_reason,
    target_catalog,
    target_schema,
    target_table,
    updated_at,
    environment,
    current_timestamp() AS load_ts,
    ROW_NUMBER() OVER (
      PARTITION BY table_name, source_system, environment
      ORDER BY updated_at DESC
    ) AS rn
  FROM __SOURCE_TABLE__
) s
ON t.table_name = s.table_name
 AND t.source_system = s.source_system
 AND t.environment = s.environment
WHEN MATCHED AND s.rn = 1 AND s.updated_at >= t.updated_at THEN UPDATE SET
  t.migration_category = s.migration_category,
  t.migration_reason = s.migration_reason,
  t.target_catalog = s.target_catalog,
  t.target_schema = s.target_schema,
  t.target_table = s.target_table,
  t.updated_at = s.updated_at,
  t.load_ts = s.load_ts
WHEN NOT MATCHED AND s.rn = 1 THEN INSERT (
  table_name,
  source_system,
  migration_category,
  migration_reason,
  target_catalog,
  target_schema,
  target_table,
  updated_at,
  environment,
  load_ts
) VALUES (
  s.table_name,
  s.source_system,
  s.migration_category,
  s.migration_reason,
  s.target_catalog,
  s.target_schema,
  s.target_table,
  s.updated_at,
  s.environment,
  s.load_ts
);
