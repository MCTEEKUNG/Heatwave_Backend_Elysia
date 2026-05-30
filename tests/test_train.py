import numpy as np
import pandas as pd

from pipeline.train import train_model, build_frames


def _synth_dataset(seed=0):
    """Two provinces, 2021-2025 daily, with a seasonal heatwave signal."""
    rng = np.random.default_rng(seed)
    parts = []
    for pid, (lat, lon) in enumerate([(13.7, 100.5), (18.8, 99.0)], start=1):
        t = pd.date_range("2021-01-01", "2025-12-31", freq="D")
        n = len(t)
        tmax = 30 + 4 * np.sin(2 * np.pi * t.dayofyear / 365.25) + rng.normal(0, 2, n)
        rh = np.clip(60 + rng.normal(0, 10, n), 20, 100)
        e = (rh / 100) * 6.105 * np.exp(17.27 * tmax / (237.7 + tmax))
        sw = 0.567 * tmax + 0.393 * e + 3.94
        p95 = np.full(n, float(np.percentile(sw, 95)))
        is_hot = (sw >= p95).astype(int)
        s = pd.Series(is_hot)
        grp = (s != s.shift()).cumsum()
        run = s.groupby(grp).transform("size")
        hw = ((s == 1) & (run >= 2)).astype(int).to_numpy()
        parts.append(pd.DataFrame({
            "province_id": pid, "time": t, "swbgt_max": sw, "p95": p95,
            "is_hot": is_hot, "heatwave": hw, "temperature_2m_max": tmax,
            "relative_humidity_2m_mean": rh, "lat": lat, "lon": lon,
        }))
    return pd.concat(parts, ignore_index=True)


def test_train_model_runs_calibrates_and_reports():
    ds = _synth_dataset()
    bundle, report = train_model(ds, horizons=range(1, 4))

    assert 0 < report["threshold"] <= 1
    assert "test" in report
    assert report["n_train"] > 0 and report["n_val"] > 0

    # calibrated predict_proba: 2 columns, in [0,1], col1 = P(heatwave)
    frame = build_frames(ds, horizons=range(1, 4))
    p = bundle.predict_proba(frame[bundle.feature_cols])
    assert p.shape[1] == 2
    assert np.all((p >= 0) & (p <= 1))
    assert bundle.model_version == "lgbm-v1"


def test_features_have_no_leaky_columns():
    ds = _synth_dataset()
    frame = build_frames(ds, horizons=range(1, 4))
    from src.features import LEAKY_COLS, feature_columns
    assert set(feature_columns(frame)).isdisjoint(LEAKY_COLS)
