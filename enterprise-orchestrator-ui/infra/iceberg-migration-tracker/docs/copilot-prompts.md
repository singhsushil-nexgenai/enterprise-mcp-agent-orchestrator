# Copilot Prompt Starters

Use these prompts while editing SQL files.

## Model refresh logic

Generate a deterministic MERGE strategy for Databricks SQL where the latest `updated_at` wins by (`table_name`, `source_system`, `environment`) and preserves existing target values for null source fields.

## Category standardization

Normalize migration categories to this canonical list only: `Eligible to Migrate`, `Migrated`, `Not Eligible`, `In Progress`, `Pending Analysis`. Route all unknown values to `Pending Analysis`.

## Dashboard KPIs

Create KPI queries for:
- Total tables
- Eligible count
- Migrated count
- Not eligible count
- In progress count
- Migration completion percentage

## DQ tests

Create SQL checks that return only failed records for:
- Null keys
- Duplicate latest records by (`table_name`, `source_system`, `environment`)
- Invalid category values
- Future-dated timestamps

## Performance

Rewrite this query for Databricks SQL performance by pushing filters early, minimizing wide scans, and avoiding repeated window functions.
