"""Tests for src.forecast_staging — write candidate forecasts to a LOCAL staging
file (isolated from Supabase) so the local app can serve them for a pre-deploy test."""
import datetime as dt
import json

import pandas as pd

from src.forecast_staging import to_staging_records, write_staging


def _rows():
    return [{
        "province_id": 1,
        "target_date": dt.date(2026, 6, 8),
        "generated_at": dt.datetime(2026, 6, 7, 5, 0, tzinfo=dt.timezone.utc),
        "horizon_days": 1,
        "probability": 0.2,
        "predicted_label": False,
        "swbgt_pred": 37.1,
        "risk_level": "moderate",
        "model_version": "lgbm-v1",
    }]


def _provinces():
    return pd.DataFrame([{"id": 1, "lat": 13.7, "lon": 100.5}])


def test_to_staging_records_merges_latlon_and_isoformats():
    r = to_staging_records(_rows(), _provinces())[0]
    assert r["lat"] == 13.7 and r["lon"] == 100.5
    assert r["target_date"].startswith("2026-06-08")
    assert r["generated_at"].startswith("2026-06-07")
    assert r["horizon_days"] == 1
    assert r["predicted_label"] is False
    assert r["swbgt_pred"] == 37.1
    assert r["risk_level"] == "moderate"
    assert r["model_version"] == "lgbm-v1"


def test_to_staging_records_missing_province_latlon_is_none():
    rows = _rows()
    rows[0]["province_id"] = 999  # not in provinces table
    r = to_staging_records(rows, _provinces())[0]
    assert r["lat"] is None and r["lon"] is None


def test_write_staging_roundtrips_json(tmp_path):
    path = tmp_path / "staging.json"
    n = write_staging(_rows(), _provinces(), str(path))
    assert n == 1
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data[0]["province_id"] == 1
    assert data[0]["lat"] == 13.7
