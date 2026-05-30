"""Leaky-oracle HEADROOM test -- DIAGNOSTIC ONLY, never ships to production.

Adds the TARGET day's *actual* weather (sWBGT/Tmax/RH) as features. This is
deliberate leakage: at inference you don't know the target day's real weather.
Its only purpose is to measure the skill CEILING and decide where to invest:

  - PR-AUC jumps a lot  -> ceiling is SIGNAL. The model is blind to the future;
    real forecast (NWP) covariates for the target day are the lever (bounded by
    forecast error, and by lead time).
  - PR-AUC barely moves -> ceiling is the LABEL / intrinsic noise. Forecast
    features won't save you; redefine the label / target instead.

Run from repo root:  .venv\\Scripts\\python.exe scripts\\oracle_headroom.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset.parquet"


def _eval(tr, va, te, feats, label):
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    pt = np.clip(calibrate(cal, np.asarray(m.predict_proba(te[feats]))[:, 1]), 0, 1)
    mt = compute_metrics(te["y"].to_numpy(), pt, thr)
    print(f"  {label:38s} PR-AUC={mt['pr_auc']:.3f}  F2={mt['f2']:.3f}  ROC={mt['roc_auc']:.3f}", flush=True)
    return mt


def main():
    ds = pd.read_parquet(DATASET)
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    base_feats = feature_columns(frame)  # antecedent-only (current model inputs)

    # LEAKY join: target-day actual weather onto each (origin, horizon) row.
    tgt = ds[["province_id", "time", "swbgt_max", "temperature_2m_max",
              "relative_humidity_2m_mean"]].rename(columns={
                  "time": "target_time", "swbgt_max": "orc_swbgt",
                  "temperature_2m_max": "orc_tmax",
                  "relative_humidity_2m_mean": "orc_rh"})
    fr = frame.copy()
    fr["target_time"] = pd.to_datetime(fr["target_time"])
    tgt["target_time"] = pd.to_datetime(tgt["target_time"])
    fr = fr.merge(tgt, on=["province_id", "target_time"], how="left")
    orc_feats = base_feats + ["orc_swbgt", "orc_tmax", "orc_rh"]

    yr = pd.to_datetime(fr["origin_time"]).dt.year
    tr, va, te = fr[yr <= 2023], fr[yr == 2024], fr[yr == 2025]
    print(f"frame rows={len(fr)} provinces={fr['province_id'].nunique()} "
          f"test_pos_rate={te['y'].mean():.3f}", flush=True)

    b = _eval(tr, va, te, base_feats, "baseline (antecedent only)")
    o = _eval(tr, va, te, orc_feats, "+ ORACLE target-day weather (leaky)")

    print(f"\nHEADROOM  PR-AUC {b['pr_auc']:.3f} -> {o['pr_auc']:.3f}  "
          f"(x{o['pr_auc'] / b['pr_auc']:.1f})   F2 {b['f2']:.3f} -> {o['f2']:.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
