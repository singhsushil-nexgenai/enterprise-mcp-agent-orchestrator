-- Replace these tokens before execution:
-- __CATALOG__, __SCHEMA__

CREATE SCHEMA IF NOT EXISTS __CATALOG__.__SCHEMA__;

CREATE TABLE IF NOT EXISTS __CATALOG__.__SCHEMA__.migration_inventory_current (
  table_name STRING NOT NULL,
  source_system STRING NOT NULL,
  migration_category STRING,
  migration_reason STRING,
  target_catalog STRING,
  target_schema STRING,
  target_table STRING,
  updated_at TIMESTAMP,
  environment STRING,
  load_ts TIMESTAMP
)
USING DELTA;
