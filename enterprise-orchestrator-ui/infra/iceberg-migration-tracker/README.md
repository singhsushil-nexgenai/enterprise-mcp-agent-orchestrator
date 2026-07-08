# Iceberg Migration Tracker Scaffold

This scaffold is a Copilot-friendly starting point to build and promote the Iceberg Migration Tracker into Databricks (dev -> uat -> prod).

## What is included

- `databricks.yml`: Databricks Asset Bundle targets and variables.
- `sql/`: Ordered SQL models and dashboard query templates.
- `tests/`: Data quality checks you can run in Databricks SQL.
- `docs/copilot-prompts.md`: Prompt templates to speed up Copilot iteration.

## Inputs you need to set

1. `catalog` (per target)
2. `schema` (per target)
3. `source_table` (fully qualified table that has migration inventory)

Expected source columns in `source_table`:

- `table_name` STRING
- `source_system` STRING
- `migration_category` STRING
- `migration_reason` STRING
- `target_catalog` STRING
- `target_schema` STRING
- `target_table` STRING
- `updated_at` TIMESTAMP
- `environment` STRING

## Build flow with Copilot

1. Open `sql/02_refresh_tracker.sql`.
2. Ask Copilot to adapt merge keys, category rules, and environment logic.
3. Open `sql/04_dashboard_queries.sql`.
4. Ask Copilot to generate KPI and trend queries for your dashboard tiles.
5. Open `tests/01_dq_checks.sql`.
6. Ask Copilot to add rule-based tests that match your migration policy.

## Deploy flow to Databricks

1. Authenticate CLI:

```powershell
databricks auth login --host https://<your-databricks-host>.cloud.databricks.com
```

2. Validate bundle:

```powershell
cd enterprise-orchestrator-ui/infra/iceberg-migration-tracker
databricks bundle validate -t dev
```

3. Deploy files to workspace target:

```powershell
databricks bundle deploy -t dev
```

4. In Databricks SQL editor, run SQL in this order:

1. `sql/01_create_schema_and_tables.sql`
2. `sql/02_refresh_tracker.sql`
3. `sql/03_serving_views.sql`
4. `sql/04_dashboard_queries.sql`
5. `tests/01_dq_checks.sql`

5. Create or update dashboard using the queries from `sql/04_dashboard_queries.sql`.

## Promotion checklist

1. Run all DQ checks in dev and confirm no failures.
2. Snapshot KPI outputs and compare against current dashboard.
3. Promote with `databricks bundle deploy -t uat` then `-t prod`.
4. Re-run DQ and KPI comparisons in each environment.

## Notes

- Keep all business rules in versioned SQL files.
- Avoid editing dashboard logic directly in UI without backporting to SQL files.
- Use pull requests for all category-rule changes.
