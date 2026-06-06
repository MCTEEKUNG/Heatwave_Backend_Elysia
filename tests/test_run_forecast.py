"""Tests for the daily forecast-generation job (pure, no network / no DB).

A stub model exposes ``predict_proba`` returning a 2-col array like sklearn, so
``src.model.predict_proba`` (which takes column 1) works unchanged. Per-province
daily frames are synthetic and mirror the real schema from build_dataset:
province_id, time, swbgt_max, p95, is_hot, heatwave, temperature_2m_max,
relative_humidity_2m_mean, lat, lon.
"""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from pipeline.run_forecast import build_forecast_rows, _province_daily_frame
from src.features import make_forecasting_frame, feature_columns
from src.risk import RISK_LEVELS


GEN_DATE = pd.Timestamp("2025-06-01")


class StubModel:
    """Deterministic stub: probability rises with horizon_k so we get a range
    of risk levels. Returns a 2-column array like sklearn predict_proba.
    Carries `threshold`/`model_version` like the real CalibratedModel bundle so
    build_forecast_rows resolves them without the untuned-fallback warning."""

    threshold = 0.281
    model_version = "stub-v0"

    def predict_proba(self, X):
        X = pd.DataFrame(X)
        # horizon_k in 1..7 -> p in ~0.05..0.65 (covers low..extreme)
        p = np.clip(0.05 + 0.10 * (X["horizon_k"].to_numpy() - 1), 0, 1)
        return np.column_stack([1 - p, p])


def _synthetic_daily(province_id=1, lat=13.7, lon=100.5, n_history=45,
                     n_forecast=7, seed=0, end=GEN_DATE):
    """Daily frame ending at ``end`` (the generated date) padded with a forecast
    tail of ``n_forecast`` future days. Mirrors the real per-province schema."""
    rng = np.random.default_rng(seed)
    # GEN_DATE sits at index n_history; the forecast tail covers the next
    # n_forecast days so origin==GEN_DATE survives for all horizons k=1..n_forecast.
    total = n_history + n_forecast + 1
    start = end - pd.Timedelta(days=n_history)
    times = pd.date_range(start, periods=total, freq="D")
    tmax = 34 + 3 * np.sin(np.arange(total) / 5.0) + rng.normal(0, 0.3, total)
    rh = 60 + 5 * np.cos(np.arange(total) / 4.0)
    # swbgt_max must be derived from tmax/rh exactly as the real builder does.
    from src.swbgt import swbgt as _swbgt
    swbgt = _swbgt(tmax, rh)
    df = pd.DataFrame({
        "province_id": province_id,
        "time": times,
        "swbgt_max": swbgt,
        "p95": 31.0,
        "temperature_2m_max": tmax,
        "relative_humidity_2m_mean": rh,
        "lat": lat,
        "lon": lon,
    })
    df["is_hot"] = (df["swbgt_max"] >= df["p95"]).astype(int)
    grp = (df["is_hot"] != df["is_hot"].shift()).cumsum()
    run_len = df.groupby(grp)["is_hot"].transform("size")
    df["heatwave"] = ((df["is_hot"] == 1) & (run_len >= 2)).astype(int)
    return df


def _provinces(n=3):
    return pd.DataFrame({
        "id": list(range(1, n + 1)),
        "lat": [13.7 + i for i in range(n)],
        "lon": [100.5 + i for i in range(n)],
    })


def _builder_factory():
    def builder(province):
        return _synthetic_daily(province_id=int(province["id"]),
                                lat=province["lat"], lon=province["lon"],
                                seed=int(province["id"]))
    return builder


def test_build_rows_basic_shape_and_validity():
    provinces = _provinces(3)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory())
    # 3 provinces x 7 horizons
    assert len(rows) == 3 * 7
    for r in rows:
        assert r["horizon_days"] in range(1, 8)
        assert 0.0 <= r["probability"] <= 1.0
        assert r["risk_level"] in RISK_LEVELS
        assert isinstance(r["predicted_label"], bool)
        assert r["generated_at"] == gen_at
        assert set(r.keys()) == {
            "province_id", "target_date", "generated_at", "horizon_days",
            "probability", "predicted_label", "swbgt_pred", "risk_level",
            "model_version"}


def test_exactly_one_row_per_province_horizon_no_dropna_regression():
    """Guards the dropna trap: origin == generated_date must survive for all k."""
    provinces = _provinces(2)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory())
    df = pd.DataFrame(rows)
    for pid in provinces["id"]:
        sub = df[df["province_id"] == pid]
        assert sorted(sub["horizon_days"]) == list(range(1, 8))


def test_target_date_equals_generated_plus_k():
    provinces = _provinces(1)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory())
    base = GEN_DATE.date()
    for r in rows:
        expected = base + pd.Timedelta(days=r["horizon_days"])
        assert r["target_date"] == expected.date() if hasattr(expected, "date") \
            else expected


def test_swbgt_pred_matches_forecast_weather():
    """swbgt_pred for a target_date should equal swbgt(forecast tmax, rh)."""
    from src.swbgt import swbgt
    province = pd.Series({"id": 1, "lat": 13.7, "lon": 100.5})
    daily = _synthetic_daily(province_id=1)
    by_time = dict(zip(daily["time"],
                       swbgt(daily["temperature_2m_max"],
                             daily["relative_humidity_2m_mean"])))
    provinces = pd.DataFrame([{"id": 1, "lat": 13.7, "lon": 100.5}])
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=lambda p: daily)
    for r in rows:
        t = pd.Timestamp(r["target_date"])
        assert r["swbgt_pred"] == pytest.approx(float(by_time[t]))


def test_probability_in_unit_interval_and_risk_consistent():
    provinces = _provinces(1)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory())
    # stub gives rising prob with horizon -> risk should be non-decreasing
    df = pd.DataFrame(rows).sort_values("horizon_days")
    order = {lvl: i for i, lvl in enumerate(RISK_LEVELS)}
    sev = [order[r] for r in df["risk_level"]]
    assert sev == sorted(sev)


def test_predicted_label_uses_bundle_threshold_and_version():
    """predicted_label must fire at the bundle's TUNED threshold (not 0.5) and
    model_version must come from the bundle when not overridden."""
    provinces = _provinces(1)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory())
    for r in rows:
        assert r["predicted_label"] == (r["probability"] >= StubModel.threshold)
        assert r["model_version"] == "stub-v0"
    # stub probs span ~0.05..0.65 -> at threshold 0.281 some labels MUST be True
    # (they would all be False at the old untuned 0.5-ish region for low ks).
    assert any(r["predicted_label"] for r in rows)
    assert not all(r["predicted_label"] for r in rows)


def test_threshold_fallback_warns_when_bundle_untuned():
    """A model without a tuned `threshold` must fall back loudly, not silently."""

    class BareStub:
        def predict_proba(self, X):
            return StubModel().predict_proba(X)

    provinces = _provinces(1)
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)
    with pytest.warns(RuntimeWarning, match="no tuned `threshold`"):
        build_forecast_rows(provinces, BareStub(), gen_at,
                            frame_builder=_builder_factory())


def test_feature_matrix_has_no_leaky_columns():
    """The columns fed to the model must exclude raw label-defining columns."""
    daily = _synthetic_daily()
    frame = make_forecasting_frame(daily, horizons=range(1, 8))
    feats = set(feature_columns(frame))
    for leaky in ("swbgt_max", "heatwave", "is_hot"):
        assert leaky not in feats


def test_requires_frame_builder():
    with pytest.raises(ValueError):
        build_forecast_rows(_provinces(1), StubModel(),
                            datetime.now(timezone.utc))


def test_origin_date_overrides_generated_at_timezone():
    """When generated_at (UTC) and the frame's local dates disagree, an explicit
    origin_date selects the correct origin -- the real-run alignment fix."""
    provinces = _provinces(1)
    # UTC stamp whose .date() is the day BEFORE the Bangkok-local origin
    gen_at = datetime(2025, 5, 31, 23, 30, tzinfo=timezone.utc)
    rows = build_forecast_rows(provinces, StubModel(), gen_at,
                               frame_builder=_builder_factory(),
                               origin_date=GEN_DATE.date())
    assert len(rows) == 7  # all horizons survive when origin is aligned
    for r in rows:
        assert r["generated_at"] == gen_at  # DB stamp stays the real UTC time
        assert r["target_date"] == (GEN_DATE.date()
                                    + pd.Timedelta(days=r["horizon_days"]))


def test_empty_origin_warns_not_silent():
    """A misaligned origin (not present in the frame) must warn, not pass silently."""
    provinces = _provinces(1)
    gen_at = datetime(2030, 1, 1, tzinfo=timezone.utc)  # far outside the frame
    with pytest.warns(RuntimeWarning):
        rows = build_forecast_rows(provinces, StubModel(), gen_at,
                                   frame_builder=_builder_factory())
    assert rows == []


def test_province_daily_frame_dedupes_overlap_and_computes_swbgt():
    """history + forecast overlap on 'today' should dedupe; forecast wins."""
    province = pd.Series({"id": 5, "lat": 18.0, "lon": 99.0})
    times = pd.date_range("2025-05-25", periods=8, freq="D")
    hist = pd.DataFrame({
        "time": times[:6],
        "temperature_2m_max": np.full(6, 35.0),
        "relative_humidity_2m_mean": np.full(6, 55.0),
    })
    # forecast overlaps last 2 history days with different values
    fcst = pd.DataFrame({
        "time": times[4:],
        "temperature_2m_max": np.full(4, 40.0),
        "relative_humidity_2m_mean": np.full(4, 50.0),
    })
    out = _province_daily_frame(province, hist, fcst)
    assert out["time"].is_unique
    assert len(out) == 8  # union of dates, no dupes
    assert "swbgt_max" in out.columns
    assert (out["province_id"] == 5).all()
    # overlap day takes forecast value (40.0 tmax)
    overlap = out[out["time"] == times[4]]
    assert overlap["temperature_2m_max"].iloc[0] == 40.0
