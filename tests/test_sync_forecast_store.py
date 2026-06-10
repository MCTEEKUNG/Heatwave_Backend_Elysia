"""Tests for the pure merge logic of scripts/sync_forecast_store.py."""
import pandas as pd

from scripts.sync_forecast_store import KEY, merge_stores


def _row(pid, issue, target, tmax=35.0):
    return {"province_id": pid, "issue_date": issue, "target_date": target,
            "lead_k": 0, "fc_tmax": tmax, "fc_rh": 60.0, "fc_heat_index": 40.0,
            "fc_soil_moisture": None}


def test_merge_unions_disjoint_days():
    local = pd.DataFrame([_row(1, "2026-06-09", "2026-06-09")])
    db = pd.DataFrame([_row(1, "2026-06-10", "2026-06-10")])
    out = merge_stores(local, db)
    assert len(out) == 2
    assert set(out["issue_date"]) == {"2026-06-09", "2026-06-10"}


def test_merge_dedupes_on_key_local_wins():
    local = pd.DataFrame([_row(1, "2026-06-10", "2026-06-10", tmax=36.0)])
    db = pd.DataFrame([_row(1, "2026-06-10", "2026-06-10", tmax=99.0)])
    out = merge_stores(local, db)
    assert len(out) == 1
    assert out.iloc[0]["fc_tmax"] == 36.0  # local row kept on identical key


def test_merge_handles_empty_frames():
    df = pd.DataFrame([_row(1, "2026-06-10", "2026-06-11")])
    empty = pd.DataFrame()
    assert len(merge_stores(df, empty)) == 1
    assert len(merge_stores(empty, df)) == 1
    assert merge_stores(empty, empty).empty


def test_merge_sorted_and_key_is_unique():
    local = pd.DataFrame([_row(2, "2026-06-10", "2026-06-12"),
                          _row(1, "2026-06-10", "2026-06-11")])
    db = pd.DataFrame([_row(1, "2026-06-09", "2026-06-09")])
    out = merge_stores(local, db)
    assert list(out["issue_date"]) == sorted(out["issue_date"])
    assert not out.duplicated(subset=KEY).any()
