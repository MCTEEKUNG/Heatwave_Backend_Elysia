"""Tests for src.forecast_covariates — the P0 forecast-covariate plumbing.

Covers: leakage-safe join (train side), serve-side covariate builder + parity
with the store's heat-index, require_coverage semantics, and the readiness gate.
"""
import numpy as np
import pandas as pd
import pytest

from src.forecast_covariates import (
    join_forecast_covariates,
    build_serve_covariate,
    load_forecast_store,
    forecast_store_readiness,
)
from src.heat_index import heat_index_c


def _frame(rows):
    """Minimal forecasting-frame rows: (province_id, origin, target, k, y)."""
    return pd.DataFrame(
        [
            {
                "province_id": p,
                "origin_time": pd.Timestamp(o),
                "target_time": pd.Timestamp(t),
                "horizon_k": k,
                "y": y,
                "some_feat": 1.0,
            }
            for (p, o, t, k, y) in rows
        ]
    )


def _store(rows):
    """Forecast-store rows: (province_id, issue, target, lead_k, fc_heat_index)."""
    return pd.DataFrame(
        [
            {
                "province_id": p,
                "issue_date": pd.Timestamp(i),
                "target_date": pd.Timestamp(t),
                "lead_k": k,
                "fc_heat_index": hi,
            }
            for (p, i, t, k, hi) in rows
        ]
    )


def test_join_attaches_covariate_on_matching_keys():
    frame = _frame([(1, "2026-06-01", "2026-06-02", 1, 0)])
    store = _store([(1, "2026-06-01", "2026-06-02", 1, 38.5)])
    out = join_forecast_covariates(frame, store)
    assert "fc_heat_index" in out.columns
    assert len(out) == 1
    assert out["fc_heat_index"].iloc[0] == pytest.approx(38.5)


def test_join_require_coverage_drops_unmatched():
    frame = _frame(
        [
            (1, "2026-06-01", "2026-06-02", 1, 0),  # matched
            (1, "2026-06-01", "2026-06-03", 2, 0),  # no store row
        ]
    )
    store = _store([(1, "2026-06-01", "2026-06-02", 1, 38.5)])
    out = join_forecast_covariates(frame, store, require_coverage=True)
    assert len(out) == 1
    assert out["horizon_k"].iloc[0] == 1


def test_join_left_keeps_unmatched_as_nan():
    frame = _frame(
        [
            (1, "2026-06-01", "2026-06-02", 1, 0),
            (1, "2026-06-01", "2026-06-03", 2, 0),
        ]
    )
    store = _store([(1, "2026-06-01", "2026-06-02", 1, 38.5)])
    out = join_forecast_covariates(frame, store, require_coverage=False)
    assert len(out) == 2
    assert out.sort_values("horizon_k")["fc_heat_index"].isna().tolist() == [False, True]


def test_load_store_rejects_leaky_rows(tmp_path):
    # issue_date >= target_date is a leak (covariate not knowable at origin)
    leaky = _store([(1, "2026-06-02", "2026-06-02", 0, 38.5)])
    p = tmp_path / "leaky.parquet"
    leaky.to_parquet(p)
    with pytest.raises(ValueError, match="issue_date"):
        load_forecast_store(str(p))


def test_build_serve_covariate_matches_heat_index_formula():
    # Open-Meteo-style forecast frame for origin 2026-06-01, k=1..2
    fcst = pd.DataFrame(
        {
            "time": [pd.Timestamp("2026-06-02"), pd.Timestamp("2026-06-03")],
            "temperature_2m_max": [40.0, 41.0],
            "relative_humidity_2m_mean": [55.0, 60.0],
        }
    )
    out = build_serve_covariate(
        fcst, province_id=1, origin_date=pd.Timestamp("2026-06-01"),
        horizons=range(1, 3),
    )
    assert set(["province_id", "origin_time", "target_time", "horizon_k",
                "fc_heat_index"]).issubset(out.columns)
    expected = heat_index_c(np.array([40.0, 41.0]), np.array([55.0, 60.0]))
    got = out.sort_values("horizon_k")["fc_heat_index"].to_numpy()
    assert got == pytest.approx(np.asarray(expected))


def test_serve_covariate_joins_like_store():
    # Parity: a serve covariate row, treated as a store, joins onto the frame
    # and yields the same value as build_serve_covariate produced.
    fcst = pd.DataFrame(
        {
            "time": [pd.Timestamp("2026-06-02")],
            "temperature_2m_max": [40.0],
            "relative_humidity_2m_mean": [55.0],
        }
    )
    serve = build_serve_covariate(
        fcst, province_id=1, origin_date=pd.Timestamp("2026-06-01"),
        horizons=range(1, 2),
    )
    store = serve.rename(
        columns={"origin_time": "issue_date", "target_time": "target_date",
                 "horizon_k": "lead_k"}
    )[["province_id", "issue_date", "target_date", "lead_k", "fc_heat_index"]]
    frame = _frame([(1, "2026-06-01", "2026-06-02", 1, 0)])
    out = join_forecast_covariates(frame, store)
    assert out["fc_heat_index"].iloc[0] == pytest.approx(serve["fc_heat_index"].iloc[0])


def test_readiness_gate_false_when_small_true_when_large():
    small = _store([(1, "2026-06-01", "2026-06-02", 1, 38.0)])
    r = forecast_store_readiness(small, min_issue_days=60)
    assert r["ready"] is False
    assert r["n_issue_days"] == 1

    big = _store(
        [(1, pd.Timestamp("2026-03-01") + pd.Timedelta(days=d),
          pd.Timestamp("2026-03-02") + pd.Timedelta(days=d), 1, 38.0)
         for d in range(70)]
    )
    r2 = forecast_store_readiness(big, min_issue_days=60)
    assert r2["ready"] is True
    assert r2["n_issue_days"] == 70
