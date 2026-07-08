-- Replace these tokens before execution:
-- __CATALOG__, __SCHEMA__

CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.vw_iceberg_migration_tracker AS
SELECT
  table_name,
  source_system,
  migration_category,
  migration_reason,
  target_catalog,
  target_schema,
  target_table,
  updated_at,
  environment
FROM __CATALOG__.__SCHEMA__.migration_inventory_current;

CREATE OR REPLACE VIEW __CATALOG__.__SCHEMA__.vw_iceberg_migration_kpis AS
SELECT
  environment,
  COUNT(*) AS total_tables,
  SUM(CASE WHEN migration_category = 'Eligible to Migrate' THEN 1 ELSE 0 END) AS eligible_to_migrate,
  SUM(CASE WHEN migration_category = 'Migrated' THEN 1 ELSE 0 END) AS migrated,
  SUM(CASE WHEN migration_category = 'Not Eligible' THEN 1 ELSE 0 END) AS not_eligible,
  SUM(CASE WHEN migration_category = 'In Progress' THEN 1 ELSE 0 END) AS in_progress,
  SUM(CASE WHEN migration_category = 'Pending Analysis' THEN 1 ELSE 0 END) AS pending_analysis,
  ROUND(
    100.0 * SUM(CASE WHEN migration_category = 'Migrated' THEN 1 ELSE 0 END)
    / NULLIF(COUNT(*), 0),
    2
  ) AS migrated_pct
FROM __CATALOG__.__SCHEMA__.migration_inventory_current
GROUP BY environment;
