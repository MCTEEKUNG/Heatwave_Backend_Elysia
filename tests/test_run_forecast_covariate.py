"""Serve-side P0: when the loaded model declares fc_* features, build_forecast_rows
must build the forecast covariate from the (already-fetched) forecast tail and feed
it to the model — using the SAME heat_index_c as the store writer (no train/serve
skew). Antecedent-only models (no feature_cols) are unaffected (covered by
tests/test_run_forecast.py)."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from pipeline.run_forecast import build_forecast_rows
from src.heat_index import heat_index_c
from src.swbgt import swbgt

GEN = pd.Timestamp("2025-06-01")


def _daily(province_id=1):
    n_hist, n_fc = 45, 7
    total = n_hist + n_fc + 1
    times = pd.date_range(GEN - pd.Timedelta(days=n_hist), periods=total, freq="D")
    tmax = 34 + 3 * np.sin(np.arange(total) / 5.0)
    rh = 60 + 5 * np.cos(np.arange(total) / 4.0)
    df = pd.DataFrame({
        "province_id": province_id, "time": times, "swbgt_max": swbgt(tmax, rh),
        "p95": 31.0, "temperature_2m_max": tmax, "relative_humidity_2m_mean": rh,
        "lat": 13.7, "lon": 100.5,
    })
    df["is_hot"] = (df["swbgt_max"] >= df["p95"]).astype(int)
    grp = (df["is_hot"] != df["is_hot"].shift()).cumsum()
    run_len = df.groupby(grp)["is_hot"].transform("size")
    df["heatwave"] = ((df["is_hot"] == 1) & (run_len >= 2)).astype(int)
    return df


class CovModel:
    """Model that declares an fc_ feature; records the matrix it is given."""
    threshold = 0.281
    model_version = "cov-v0"
    feature_cols = ["horizon_k", "fc_heat_index"]

    def __init__(self):
        self.seen = None

    def predict_proba(self, X):
        X = pd.DataFrame(X)
        self.seen = X.copy()
        p = np.clip(0.05 + 0.10 * (X["horizon_k"].to_numpy() - 1), 0, 1)
        return np.column_stack([1 - p, p])


def test_serve_feeds_forecast_covariate_matching_heat_index():
    model = CovModel()
    provinces = pd.DataFrame([{"id": 1, "lat": 13.7, "lon": 100.5}])
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)

    rows = build_forecast_rows(provinces, model, gen_at,
                               frame_builder=lambda p: _daily(1),
                               origin_date=GEN.date())

    assert len(rows) == 7
    assert model.seen is not None
    assert "fc_heat_index" in model.seen.columns
    assert model.seen["fc_heat_index"].notna().all()

    # the fed covariate values must equal heat_index_c over the 7 target days
    d = _daily(1)
    d["time"] = pd.to_datetime(d["time"]).dt.normalize()
    origin = pd.Timestamp(GEN.date())
    expected = []
    for k in range(1, 8):
        r = d[d["time"] == origin + pd.Timedelta(days=k)].iloc[0]
        expected.append(float(heat_index_c(r["temperature_2m_max"],
                                           r["relative_humidity_2m_mean"])))
    got = sorted(model.seen["fc_heat_index"].tolist())
    assert got == pytest.approx(sorted(expected))
