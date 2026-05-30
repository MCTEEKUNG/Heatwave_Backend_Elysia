"""Improvement experiments on the clean ERA5 dataset (measure, don't theorize).

Diagnosis: era5_lgbm (train 2016-21 / test 24-25) scored F2 0.317 with a 2.6%->8.1%
train->test positive-rate shift. This sweeps fairer splits + HP to see what is
clean-recoverable. Prints PR-AUC/F2/ROC per configuration on its own test set.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset_era5.parquet"


def run(frame, feats, train_max, val_max, label, **hp):
    y = pd.to_datetime(frame["origin_time"]).dt.year
    tr, va, te = frame[y <= train_max], frame[(y > train_max) & (y <= val_max)], frame[y > val_max]
    m = lgbm_train(tr[feats], tr["y"].to_numpy(), **hp)
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    pt = np.clip(calibrate(cal, np.asarray(m.predict_proba(te[feats]))[:, 1]), 0, 1)
    mt = compute_metrics(te["y"].to_numpy(), pt, thr)
    print(f"  {label:46s} PR-AUC={mt['pr_auc']:.3f} F2={mt['f2']:.3f} ROC={mt['roc_auc']:.3f} "
          f"(train_pos={tr['y'].mean():.3f} test_pos={te['y'].mean():.3f} n_te={len(te)})", flush=True)
    return mt


def main():
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    feats = feature_columns(frame)
    print(f"frame rows={len(frame)} features={len(feats)}\n", flush=True)

    print("A) reproduce baseline split (train<=2021 / val 22-23 / test 24-25):", flush=True)
    run(frame, feats, 2021, 2023, "baseline (6 train yrs, hot 24-25 test)")

    print("\nB) more history + fair test year (matches old model's test=2025):", flush=True)
    run(frame, feats, 2023, 2024, "train<=2023 (8 yrs) / val 2024 / test 2025")

    print("\nC) B + heavier LightGBM (more trees, deeper):", flush=True)
    run(frame, feats, 2023, 2024, "train<=2023 + n_est=600 lr=0.03 leaves=63",
        n_estimators=600, learning_rate=0.03, num_leaves=63)

    return 0


if __name__ == "__main__":
    sys.exit(main())
