# src/forecast_store_db.py
"""Postgres twin of ``data/processed/forecast_store.parquet`` (P0 forward-collector).

Table: ``heatwave.forecast_store`` (migration 0002). Rows are immutable once
collected — a forecast already issued never changes — so the writer uses
``ON CONFLICT DO NOTHING`` and re-pushing any subset is always safe.

Connection comes lazily from ``DATABASE_URL`` (same pattern as src/db_write.py);
importing this module never requires psycopg or a database, so the pure helpers
stay testable offline.
"""
import os

_COLUMNS = (
    "province_id",
    "issue_date",
    "target_date",
    "lead_k",
    "fc_tmax",
    "fc_rh",
    "fc_heat_index",
    "fc_soil_moisture",
)

UPSERT_SQL = """
INSERT INTO heatwave.forecast_store
    (province_id, issue_date, target_date, lead_k,
     fc_tmax, fc_rh, fc_heat_index, fc_soil_moisture)
VALUES
    (%(province_id)s, %(issue_date)s, %(target_date)s, %(lead_k)s,
     %(fc_tmax)s, %(fc_rh)s, %(fc_heat_index)s, %(fc_soil_moisture)s)
ON CONFLICT (province_id, issue_date, target_date) DO NOTHING
"""

FETCH_SQL = """
SELECT province_id, issue_date::text, target_date::text, lead_k,
       fc_tmax, fc_rh, fc_heat_index, fc_soil_moisture
FROM heatwave.forecast_store
ORDER BY issue_date, province_id, target_date
"""


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Export the Supabase Postgres connection "
            "string before reading/writing heatwave.forecast_store."
        )
    return url


def rows_for_upsert(df) -> list[dict]:
    """Pure: store DataFrame -> list of param dicts with NaN coerced to None."""
    import pandas as pd

    if df is None or df.empty:
        return []
    sub = df[list(_COLUMNS)].astype(object).where(pd.notnull(df[list(_COLUMNS)]), None)
    return sub.to_dict("records")


def upsert_rows(rows: list[dict]) -> int:
    """Batch-insert rows (ON CONFLICT DO NOTHING); returns rows actually inserted."""
    if not rows:
        return 0
    import psycopg

    # Supabase pooler (transaction mode) breaks named prepared statements.
    with psycopg.connect(_database_url(), prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)
            inserted = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
        conn.commit()
    return inserted


def fetch_df():
    """All cloud-collected rows as a DataFrame (ISO-string dates, parquet-compatible)."""
    import pandas as pd
    import psycopg

    with psycopg.connect(_database_url(), prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(FETCH_SQL)
            data = cur.fetchall()
    return pd.DataFrame(data, columns=list(_COLUMNS))
