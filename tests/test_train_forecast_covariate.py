"""train_model gains an optional forecast_store: when given, forecast covariates
are joined into the frame and become model features; when omitted, behaviour is
unchanged (backward-compatible antecedent-only training)."""
import numpy as np
import pandas as pd

from pipeline.train import train_model


def _synth_dataset():
    """One province, daily 2023-2025, with a recurring heatwave pattern so each
    split year (train 2023 / val 2024 / test 2025) has positives."""
    days = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    doy = days.dayofyear.to_numpy()
    heatwave = (doy % 10 < 2).astype(int)  # ~20% positives, present every year
    swbgt = 30 + 6 * heatwave + np.sin(2 * np.pi * doy / 365.25)
    return pd.DataFrame({
        "province_id": 1,
        "time": days,
        "swbgt_max": swbgt,
        "heatwave": heatwave,
    })


def _full_store(dataset, horizons=range(1, 8)):
    """A forecast store covering every (province, origin, target, k) in dataset."""
    rows = []
    for _, r in dataset.iterrows():
        for k in horizons:
            rows.append({
                "province_id": int(r["province_id"]),
                "issue_date": r["time"],
                "target_date": r["time"] + pd.Timedelta(days=int(k)),
                "lead_k": int(k),
                "fc_heat_index": float(r["swbgt_max"]),
            })
    return pd.DataFrame(rows)


def test_train_model_backward_compatible_without_store():
    bundle, report = train_model(_synth_dataset())
    assert "fc_heat_index" not in bundle.feature_cols


def test_train_model_includes_forecast_covariate_when_store_given():
    ds = _synth_dataset()
    bundle, report = train_model(ds, forecast_store=_full_store(ds))
    assert "fc_heat_index" in bundle.feature_cols
