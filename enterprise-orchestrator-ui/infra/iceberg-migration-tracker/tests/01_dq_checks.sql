-- Replace these tokens before execution:
-- __CATALOG__, __SCHEMA__

-- Test 1: Null key fields (should return 0 rows)
SELECT *
FROM __CATALOG__.__SCHEMA__.migration_inventory_current
WHERE table_name IS NULL
   OR source_system IS NULL
   OR environment IS NULL;

-- Test 2: Duplicate latest records (should return 0 rows)
WITH dups AS (
  SELECT
    table_name,
    source_system,
    environment,
    COUNT(*) AS cnt
  FROM __CATALOG__.__SCHEMA__.migration_inventory_current
  GROUP BY table_name, source_system, environment
)
SELECT *
FROM dups
WHERE cnt > 1;

-- Test 3: Invalid category values (should return 0 rows)
SELECT *
FROM __CATALOG__.__SCHEMA__.migration_inventory_current
WHERE migration_category NOT IN (
  'Eligible to Migrate',
  'Migrated',
  'Not Eligible',
  'In Progress',
  'Pending Analysis'
)
AND migration_category IS NOT NULL;

-- Test 4: Future timestamps (should return 0 rows)
SELECT *
FROM __CATALOG__.__SCHEMA__.migration_inventory_current
WHERE updated_at > current_timestamp();
