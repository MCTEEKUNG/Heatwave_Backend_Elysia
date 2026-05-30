# src/db_write.py
"""Postgres writer for ``heatwave.forecasts`` using psycopg (v3).

The connection is created lazily from the ``DATABASE_URL`` environment variable;
nothing connects at import time. ``upsert_forecasts`` performs a parameterized
batch INSERT ... ON CONFLICT DO UPDATE so re-running the daily job for the same
``generated_at`` overwrites the prior rows rather than duplicating them.

Expected row dict keys (one per province x horizon):
    province_id, target_date, generated_at, horizon_days,
    probability, predicted_label, swbgt_pred, risk_level, model_version
"""
import os

# psycopg is imported lazily inside the functions that need a live connection so
# that importing this module (e.g. for build_forecast_rows in tests) never
# requires the driver or a database.

_COLUMNS = (
    "province_id",
    "target_date",
    "generated_at",
    "horizon_days",
    "probability",
    "predicted_label",
    "swbgt_pred",
    "risk_level",
    "model_version",
)

# Parameterized upsert. Conflict target matches UNIQUE(province_id, target_date,
# generated_at); on conflict we refresh the prediction columns.
UPSERT_SQL = """
INSERT INTO heatwave.forecasts
    (province_id, target_date, generated_at, horizon_days,
     probability, predicted_label, swbgt_pred, risk_level, model_version)
VALUES
    (%(province_id)s, %(target_date)s, %(generated_at)s, %(horizon_days)s,
     %(probability)s, %(predicted_label)s, %(swbgt_pred)s, %(risk_level)s,
     %(model_version)s)
ON CONFLICT (province_id, target_date, generated_at) DO UPDATE SET
    horizon_days    = EXCLUDED.horizon_days,
    probability     = EXCLUDED.probability,
    predicted_label = EXCLUDED.predicted_label,
    swbgt_pred      = EXCLUDED.swbgt_pred,
    risk_level      = EXCLUDED.risk_level,
    model_version   = EXCLUDED.model_version
"""


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Export a Postgres connection string "
            "(e.g. postgresql://user:pass@host:5432/db) before writing forecasts."
        )
    return url


def get_connection():
    """Open a new psycopg connection from ``DATABASE_URL`` (lazy import).

    Validates ``DATABASE_URL`` *before* importing the driver so an unset URL
    raises the clear configuration error regardless of whether psycopg is
    installed.
    """
    url = _database_url()
    import psycopg  # local import: not needed for pure row building

    return psycopg.connect(url)


def upsert_forecasts(rows, conn=None) -> int:
    """Upsert forecast ``rows`` (list of dicts) into ``heatwave.forecasts``.

    Returns the number of rows submitted. If ``conn`` is provided it is used and
    left open (caller owns it); otherwise a connection is opened from
    ``DATABASE_URL`` and closed here. Raises a clear error if ``DATABASE_URL`` is
    unset and no connection was supplied.
    """
    rows = list(rows)
    if not rows:
        return 0

    params = [{c: r[c] for c in _COLUMNS} for r in rows]  # KeyError surfaces bad rows early

    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, params)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()
    return len(params)


_THRESHOLD_COLUMNS = (
    "province_id", "doy", "metric", "p90", "p95", "p975", "baseline_period",
)

THRESHOLD_UPSERT_SQL = """
INSERT INTO heatwave.province_thresholds
    (province_id, doy, metric, p90, p95, p975, baseline_period)
VALUES
    (%(province_id)s, %(doy)s, %(metric)s, %(p90)s, %(p95)s, %(p975)s,
     %(baseline_period)s)
ON CONFLICT (province_id, doy, metric) DO UPDATE SET
    p90             = EXCLUDED.p90,
    p95             = EXCLUDED.p95,
    p975            = EXCLUDED.p975,
    baseline_period = EXCLUDED.baseline_period,
    updated_at      = now()
"""


def upsert_thresholds(rows, conn=None) -> int:
    """Upsert per-province climatology ``rows`` into ``heatwave.province_thresholds``.

    Conflict target matches PRIMARY KEY(province_id, doy, metric). Same lazy
    connection / ``DATABASE_URL`` contract as ``upsert_forecasts``.
    """
    rows = list(rows)
    if not rows:
        return 0

    params = [{c: r[c] for c in _THRESHOLD_COLUMNS} for r in rows]

    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(THRESHOLD_UPSERT_SQL, params)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()
    return len(params)
