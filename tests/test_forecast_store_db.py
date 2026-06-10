"""Tests for src/forecast_store_db.py (pure parts; DB I/O is lazy + mocked)."""
import numpy as np
import pandas as pd
import pytest

from src.forecast_store_db import rows_for_upsert, UPSERT_SQL


def _frame():
    return pd.DataFrame([
        {"province_id": 1, "issue_date": "2026-06-10", "target_date": "2026-06-12",
         "lead_k": 2, "fc_tmax": 38.5, "fc_rh": 60.0, "fc_heat_index": 44.1,
         "fc_soil_moisture": 0.21},
        {"province_id": 2, "issue_date": "2026-06-10", "target_date": "2026-06-10",
         "lead_k": 0, "fc_tmax": 35.0, "fc_rh": 70.0, "fc_heat_index": 41.0,
         "fc_soil_moisture": np.nan},
    ])


def test_rows_for_upsert_converts_nan_to_none():
    rows = rows_for_upsert(_frame())
    assert rows[0]["fc_soil_moisture"] == pytest.approx(0.21)
    assert rows[1]["fc_soil_moisture"] is None


def test_rows_for_upsert_preserves_keys_and_types():
    rows = rows_for_upsert(_frame())
    assert len(rows) == 2
    r = rows[0]
    assert r["province_id"] == 1
    assert r["issue_date"] == "2026-06-10"
    assert r["target_date"] == "2026-06-12"
    assert r["lead_k"] == 2
    assert isinstance(r["fc_tmax"], float)


def test_rows_for_upsert_empty_frame():
    assert rows_for_upsert(pd.DataFrame()) == []


def test_upsert_sql_is_conflict_do_nothing():
    # Rows are immutable once collected — never overwrite on conflict.
    assert "ON CONFLICT (province_id, issue_date, target_date) DO NOTHING" in UPSERT_SQL
    assert "heatwave.forecast_store" in UPSERT_SQL
