import numpy as np
import pandas as pd

from src.features import make_forecasting_frame, feature_columns, LEAKY_COLS


def _synthetic_province(n=60, seed=0, future_tail=None):
    """Build a deterministic single-province daily frame of length n.

    If ``future_tail`` is given, values from that index onward are overwritten
    (used to prove features at earlier origin days don't see the future).
    """
    rng = np.random.default_rng(seed)
    times = pd.date_range("2024-01-01", periods=n, freq="D")
    swbgt = 28 + 3 * np.sin(np.arange(n) / 5.0) + rng.normal(0, 0.3, n)
    tmax = swbgt + 4
    rh = 60 + 5 * np.cos(np.arange(n) / 4.0)
    df = pd.DataFrame({
        "province_id": 1,
        "time": times,
        "swbgt_max": swbgt,
        "p95": 30.0,
        "temperature_2m_max": tmax,
        "relative_humidity_2m_mean": rh,
        "lat": 13.7,
        "lon": 100.5,
    })
    df["is_hot"] = (df["swbgt_max"] >= df["p95"]).astype(int)
    grp = (df["is_hot"] != df["is_hot"].shift()).cumsum()
    run_len = df.groupby(grp)["is_hot"].transform("size")
    df["heatwave"] = ((df["is_hot"] == 1) & (run_len >= 2)).astype(int)

    if future_tail is not None:
        idx, scale = future_tail
        df.loc[df.index >= idx, ["swbgt_max", "temperature_2m_max",
                                 "relative_humidity_2m_mean"]] *= scale
        df["is_hot"] = (df["swbgt_max"] >= df["p95"]).astype(int)
        grp = (df["is_hot"] != df["is_hot"].shift()).cumsum()
        run_len = df.groupby(grp)["is_hot"].transform("size")
        df["heatwave"] = ((df["is_hot"] == 1) & (run_len >= 2)).astype(int)
    return df


def test_frame_not_empty_and_has_horizon_and_target():
    frame = make_forecasting_frame(_synthetic_province())
    assert len(frame) > 0
    assert "horizon_k" in frame.columns
    assert "y" in frame.columns
    assert set(frame["horizon_k"].unique()) == set(range(1, 8))
    assert set(frame["y"].unique()).issubset({0, 1})


def test_no_leaky_target_day_columns_in_features():
    """CRITICAL: feature matrix must NOT contain any raw label-defining column."""
    frame = make_forecasting_frame(_synthetic_province())
    feats = set(feature_columns(frame))
    # none of the raw same-day / label columns may be feature inputs
    assert feats.isdisjoint(LEAKY_COLS)
    # explicit belt-and-suspenders: the target-day swbgt column is absent
    assert "swbgt_max" not in feats
    assert "heatwave" not in feats
    assert "is_hot" not in feats


def test_features_depend_only_on_past_value_based():
    """CRITICAL value-based proof: two frames identical through day t but
    differing strictly AFTER t must yield bit-identical feature rows for all
    origin days <= t-ish. We compare feature rows on overlapping origin days."""
    base = _synthetic_province(n=60, seed=1)
    # mutate everything from index 40 onward -- the "future"
    mutated = _synthetic_province(n=60, seed=1, future_tail=(40, 1.5))

    fb = make_forecasting_frame(base)
    fm = make_forecasting_frame(mutated)

    # compare every feature except merge keys and the static province_id
    cols = [c for c in feature_columns(fb)
            if c not in ("province_id", "horizon_k")]

    # restrict to origin days strictly before the mutation point (index 40),
    # i.e. origin_time < 2024-01-01 + 40 days. For those days every feature is
    # built from values at <= origin (all < mutation point), so must match.
    cutoff = pd.Timestamp("2024-01-01") + pd.Timedelta(days=39)
    fb_e = fb[fb["origin_time"] <= cutoff].sort_values(
        ["origin_time", "horizon_k"]).reset_index(drop=True)
    fm_e = fm[fm["origin_time"] <= cutoff].sort_values(
        ["origin_time", "horizon_k"]).reset_index(drop=True)

    common = fb_e["origin_time"].isin(fm_e["origin_time"].unique())
    fb_e = fb_e[common].reset_index(drop=True)

    # align on (origin_time, horizon_k)
    merged = fb_e.merge(fm_e, on=["origin_time", "horizon_k"],
                        suffixes=("_b", "_m"))
    assert len(merged) > 0
    for c in cols:
        np.testing.assert_allclose(
            merged[f"{c}_b"].to_numpy(), merged[f"{c}_m"].to_numpy(),
            err_msg=f"feature {c} changed when only the FUTURE changed -> leakage",
        )


def test_target_is_future_heatwave_shift_negative_k():
    """Hand-traced row: y at origin t for horizon k equals heatwave at t+k."""
    df = _synthetic_province(n=60, seed=2)
    frame = make_forecasting_frame(df)

    # pick a concrete origin day with full antecedent history
    origin = pd.Timestamp("2024-02-15")
    hw_by_time = dict(zip(df["time"], df["heatwave"]))
    for k in range(1, 8):
        row = frame[(frame["origin_time"] == origin) & (frame["horizon_k"] == k)]
        assert len(row) == 1
        target_time = origin + pd.Timedelta(days=k)
        assert int(row["y"].iloc[0]) == int(hw_by_time[target_time])
        assert row["target_time"].iloc[0] == target_time


def test_rolling_excludes_current_day():
    """The 3-day mean feature at origin t must use days t-3..t-1 (not t)."""
    df = _synthetic_province(n=60, seed=3)
    frame = make_forecasting_frame(df)
    origin = pd.Timestamp("2024-02-15")
    oi = df.index[df["time"] == origin][0]
    expected_mean3 = df["swbgt_max"].iloc[oi - 3:oi].mean()  # t-3,t-2,t-1
    row = frame[(frame["origin_time"] == origin) & (frame["horizon_k"] == 1)]
    np.testing.assert_allclose(row["swbgt_max_mean_3d"].iloc[0], expected_mean3)
    # the current-day value must NOT equal the feature (sanity: shift applied)
    assert not np.isclose(row["swbgt_max_mean_3d"].iloc[0],
                          df["swbgt_max"].iloc[oi - 2:oi + 1].mean())


def test_era5_features_are_antecedent_and_not_leaky():
    days = pd.date_range("2003-01-01", periods=120, freq="D")
    df = pd.DataFrame({
        "province_id": 1, "time": days, "lat": 13.7, "lon": 100.5,
        "swbgt_max": 30.0, "heat_index_max": 32.0, "t2m_c_max": 34.0,
        "rh_mean": 60.0, "wind_speed_max": 5.0, "sp_mean": 101000.0,
        "ndvi": 0.4, "ndvi_lag1": 0.39, "ndvi_lag2": 0.38,
        "p95": 33.0, "is_hot": 0, "heatwave": 0,
    })
    frame = make_forecasting_frame(df, horizons=range(1, 4))
    cols = feature_columns(frame)
    # raw truth columns must NOT be features
    assert "heat_index_max" not in cols and "t2m_c_max" not in cols
    # raw (current-month) NDVI is NOT knowable intra-month -> only completed-month lags
    assert "ndvi" not in cols
    # antecedent rolling forms + NDVI lags + wind must be present
    assert "heat_index_max_mean_7d" in cols
    assert "wind_speed_max_mean_7d" in cols
    assert "ndvi_lag1" in cols and "ndvi_lag2" in cols
    assert {"heat_index_max", "t2m_c_max", "rh_mean"} <= LEAKY_COLS
