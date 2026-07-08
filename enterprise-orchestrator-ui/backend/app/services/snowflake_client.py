"""
Snowflake connector client — table metadata, row counts, freshness.
Auth: password-based via snowflake-connector-python.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from app import config

logger = logging.getLogger(__name__)

_CONN = None


def _connect():
    """Create or reuse a Snowflake connection."""
    global _CONN
    if _CONN is not None:
        try:
            _CONN.cursor().execute("SELECT 1")
            return _CONN
        except Exception:
            _CONN = None

    try:
        import snowflake.connector
        _CONN = snowflake.connector.connect(
            account=config.SNOWFLAKE_ACCOUNT,
            user=config.SNOWFLAKE_USER,
            password=config.SNOWFLAKE_PASSWORD,
            role=config.SNOWFLAKE_ROLE,
            warehouse=config.SNOWFLAKE_WAREHOUSE,
            database=config.SNOWFLAKE_DATABASE,
            schema=config.SNOWFLAKE_SCHEMA,
            insecure_mode=True,  # corporate proxy TLS
        )
        return _CONN
    except Exception as e:
        logger.warning("Snowflake connection failed: %s", e)
        return None


def is_configured() -> bool:
    return bool(config.SNOWFLAKE_PASSWORD)


def _query(sql: str, params: dict | None = None) -> list[dict]:
    """Execute a SQL query and return list of row dicts."""
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.warning("Snowflake query error: %s", e)
        return []


def get_table_metadata(database: str, schema: str, table: str) -> dict[str, Any]:
    """Get table metadata: columns, row count, size, last altered."""
    fqn = f"{database}.{schema}.{table}"

    # Table info from information_schema
    info_rows = _query(f"""
        SELECT TABLE_TYPE, ROW_COUNT, BYTES, CREATED, LAST_ALTERED
        FROM {database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    """, {"1": schema, "2": table})

    if not info_rows:
        return {"found": False, "table": fqn}

    info = info_rows[0]

    # Column list
    col_rows = _query(f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """, {"1": schema, "2": table})

    columns = [
        {
            "name": r["COLUMN_NAME"],
            "type": r["DATA_TYPE"],
            "nullable": r["IS_NULLABLE"],
        }
        for r in col_rows
    ]

    return {
        "found": True,
        "table": fqn,
        "table_type": info.get("TABLE_TYPE"),
        "row_count": info.get("ROW_COUNT"),
        "bytes": info.get("BYTES"),
        "created": str(info.get("CREATED") or ""),
        "last_altered": str(info.get("LAST_ALTERED") or ""),
        "column_count": len(columns),
        "columns": columns,
    }


def get_row_count(database: str, schema: str, table: str) -> int | None:
    """Get exact row count (for small tables) or approximate from metadata."""
    rows = _query(f"""
        SELECT ROW_COUNT
        FROM {database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    """, {"1": schema, "2": table})
    if rows:
        return rows[0].get("ROW_COUNT")
    return None


def get_freshness(database: str, schema: str, table: str) -> dict[str, Any]:
    """Get table freshness: last_altered vs now."""
    rows = _query(f"""
        SELECT LAST_ALTERED, CREATED
        FROM {database}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    """, {"1": schema, "2": table})
    if not rows:
        return {"found": False}

    last_altered = rows[0].get("LAST_ALTERED")
    if last_altered and hasattr(last_altered, "timestamp"):
        now = datetime.now(timezone.utc)
        delta = now - last_altered.replace(tzinfo=timezone.utc)
        return {
            "found": True,
            "last_altered": str(last_altered),
            "hours_since_update": round(delta.total_seconds() / 3600, 1),
            "is_stale": delta.total_seconds() > 86400,  # >24h
        }
    return {"found": True, "last_altered": str(last_altered)}


def _parse_table_fqn(fqn: str) -> tuple[str, str, str]:
    """Parse DATABASE.SCHEMA.TABLE string."""
    parts = fqn.split(".")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return config.SNOWFLAKE_DATABASE, parts[0], parts[1]
    return config.SNOWFLAKE_DATABASE, config.SNOWFLAKE_SCHEMA, parts[0]


def get_full_table_intelligence(target_tables: list[str]) -> dict[str, dict]:
    """
    Get Snowflake metadata for a list of target tables.
    Returns {table_fqn: {metadata, freshness}} dict.
    """
    if not is_configured():
        return {}

    results = {}
    for table_fqn in target_tables:
        db, schema, table = _parse_table_fqn(table_fqn)
        meta = get_table_metadata(db, schema, table)
        freshness = get_freshness(db, schema, table) if meta.get("found") else {}
        results[table_fqn] = {
            "metadata": meta,
            "freshness": freshness,
        }
    return results
