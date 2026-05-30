# pipeline/train.py
"""Train the heatwave forecasting model end-to-end.

dataset.parquet -> per-province forecasting frames -> temporal split
(train <= 2023 / val 2024 / test 2025) -> LightGBM -> isotonic calibration on
val -> F2 threshold tuning on val -> honest metrics on the held-out test year ->
save ``models/heatwave_model.pkl`` as a CalibratedModel.

The saved bundle's ``predict_proba`` returns CALIBRATED probabilities, so
``pipeline/run_forecast.py`` consumes it unchanged.
"""
import json

import numpy as np
import pandas as pd

from src.features import make_forecasting_frame, feature_columns
from src.model import train as train_lgbm, predict_proba, CalibratedModel
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET_PATH = "data/processed/dataset.parquet"
PROVINCES_PATH = "data/provinces.csv"
MODEL_PATH = "models/heatwave_model.pkl"
MODEL_VERSION = "lgbm-v1"


def build_frames(dataset: pd.DataFrame, horizons=range(1, 8)) -> pd.DataFrame:
    """Stack per-province forecasting frames into one training table."""
    frames = [make_forecasting_frame(grp, horizons=horizons)
              for _, grp in dataset.groupby("province_id")]
    return pd.concat(frames, ignore_index=True)


def train_model(dataset: pd.DataFrame, horizons=range(1, 8),
                train_end=2023, val_year=2024, test_year=2025):
    """Train + calibrate + evaluate. Returns ``(bundle, report)``.

    ``dataset`` must carry province ``lat``/``lon`` (so features match the
    forecast job) plus the build_dataset columns.
    """
    frame = build_frames(dataset, horizons=horizons)
    feat_cols = feature_columns(frame)
    yr = pd.to_datetime(frame["origin_time"]).dt.year

    tr = frame[yr <= train_end]
    va = frame[yr == val_year]
    te = frame[yr == test_year]
    if len(tr) == 0 or len(va) == 0:
        raise ValueError(
            f"empty split (train={len(tr)}, val={len(va)}, test={len(te)}); "
            "dataset must span the training years through 2024 validation")

    model = train_lgbm(tr[feat_cols], tr["y"].to_numpy())

    raw_val = predict_proba(model, va[feat_cols])
    calibrator = fit_calibrator(raw_val, va["y"].to_numpy())
    cal_val = calibrate(calibrator, raw_val)
    threshold = tune_threshold(cal_val, va["y"].to_numpy())

    bundle = CalibratedModel(model, calibrator, threshold, feat_cols, MODEL_VERSION)

    report = {
        "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
        "threshold": float(threshold), "features": feat_cols,
    }
    if len(te) > 0:
        cal_test = bundle.predict_proba(te[feat_cols])[:, 1]
        y_test = te["y"].to_numpy()
        report["test"] = compute_metrics(y_test, cal_test, threshold)
        # baseline: always predict the test base rate (no skill)
        base = float(y_test.mean())
        report["baseline_constant"] = compute_metrics(
            y_test, np.full(len(te), base), threshold)
    return bundle, report


def main():
    import os
    import joblib

    dataset = pd.read_parquet(DATASET_PATH)
    if "lat" not in dataset.columns:
        prov = pd.read_csv(PROVINCES_PATH)[["id", "lat", "lon"]]
        dataset = dataset.merge(
            prov, left_on="province_id", right_on="id", how="left"
        ).drop(columns=["id"])

    bundle, report = train_model(dataset)
    os.makedirs("models", exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)

    printable = {k: v for k, v in report.items() if k != "features"}
    print(json.dumps(printable, indent=2, default=str))
    print(f"saved {MODEL_PATH} (threshold={report['threshold']:.3f}, "
          f"version={MODEL_VERSION}, features={len(report['features'])})")


if __name__ == "__main__":
    main()
