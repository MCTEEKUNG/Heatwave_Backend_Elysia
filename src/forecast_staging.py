"""Write candidate forecasts to a LOCAL staging file (isolated from Supabase).

The maintainer inner-loop tests a promoted candidate on the local app *before*
deploying. `run_daily_forecast.py --staging` writes the forecast rows here instead
of upserting to Supabase; the backend serves them when `HEATWAVE_FORECAST_FILE`
is set. JSON shape matches what `src/routes/forecast.ts` returns (lat/lon merged
for the map, ISO date strings) so the frontend needs no changes.
"""
from __future__ import annotations

import datetime as _dt
import json
import os


def _iso(v) -> str:
    """date / datetime / Timestamp / str -> ISO-8601 string (midnight for dates)."""
    if isinstance(v, str):
        return v
    if isinstance(v, _dt.datetime):
        return v.isoformat()
    if isinstance(v, _dt.date):
        return _dt.datetime(v.year, v.month, v.day).isoformat()
    # pandas Timestamp or anything date-like
    iso = getattr(v, "isoformat", None)
    return iso() if callable(iso) else str(v)


def to_staging_records(rows, provinces) -> list[dict]:
    """Forecast row dicts + a provinces frame (id/lat/lon) -> JSON-able records
    carrying lat/lon and ISO dates (one record per province x horizon)."""
    latlon = {int(p.id): (float(p.lat), float(p.lon)) for p in provinces.itertuples()}
    out = []
    for r in rows:
        pid = int(r["province_id"])
        lat, lon = latlon.get(pid, (None, None))
        sw = r.get("swbgt_pred")
        out.append({
            "province_id": pid,
            "lat": lat,
            "lon": lon,
            "target_date": _iso(r["target_date"]),
            "generated_at": _iso(r["generated_at"]),
            "horizon_days": int(r["horizon_days"]),
            "probability": float(r["probability"]),
            "predicted_label": bool(r["predicted_label"]),
            "swbgt_pred": None if sw is None else float(sw),
            "risk_level": r["risk_level"],
            "model_version": r["model_version"],
        })
    return out


def write_staging(rows, provinces, path: str) -> int:
    """Write staging records to ``path`` (JSON array). Returns the row count."""
    records = to_staging_records(rows, provinces)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f)
    return len(records)
