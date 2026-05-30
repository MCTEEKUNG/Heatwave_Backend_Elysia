"""P0 prototype -- measure the REALIZABLE headroom from NWP forecast covariates.

The oracle test (scripts/oracle_headroom.py) showed PR-AUC 0.33 -> 0.88 when the
model can see the target day's *perfect* weather. Real forecasts aren't perfect:
error grows with lead time. This script brackets how much of that headroom
survives a realistic forecast by adding a per-lead error model to the target-day
weather, then training with those (degraded) values as features.

Three feature sets, same temporal split / calibration / threshold tuning:
  1. baseline            -- antecedent-only (today's production model)
  2. + perfect forecast  -- target-day actuals (oracle ceiling)
  3. + realistic forecast -- target-day actuals + per-lead Gaussian error

Per-lead error schedule is calibrated to typical 2 m-temperature NWP skill
(~1 deg C day-1 growing to ~3 deg C day-7; RH ~5% to ~12%). Real archived
forecasts (Open-Meteo Historical Forecast API -- probed, returns 200) would
replace this model in the full build; this prototype's job is to decide whether
that sourcing work is worth it, and how skill decays with lead time.

Run from repo root:  .venv\\Scripts\\python.exe scripts\\p0_forecast_prototype.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.swbgt import swbgt
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset.parquet"
SEED = 7

# Per-lead NWP error (std). day-k index = horizon_k. Calibrated to typical
# 2 m-temp forecast error growth; deliberately conservative (real != perfect).
TMAX_ERR = lambda k: 1.0 + 0.30 * (k - 1)   # 1.0 C (k=1) -> 2.8 C (k=7)
RH_ERR = lambda k: 5.0 + 1.20 * (k - 1)     # 5%  (k=1) -> 12.2% (k=7)


def _fit(tr, va, feats):
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    return m, cal, thr


def _predict(m, cal, feats, df):
    return np.clip(calibrate(cal, np.asarray(m.predict_proba(df[feats]))[:, 1]), 0, 1)


def main():
    rng = np.random.default_rng(SEED)
    ds = pd.read_parquet(DATASET)
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    base_feats = feature_columns(frame)

    tgt = ds[["province_id", "time", "swbgt_max", "temperature_2m_max",
              "relative_humidity_2m_mean"]].rename(columns={
                  "time": "target_time", "swbgt_max": "orc_swbgt",
                  "temperature_2m_max": "orc_tmax", "relative_humidity_2m_mean": "orc_rh"})
    fr = frame.copy()
    fr["target_time"] = pd.to_datetime(fr["target_time"])
    tgt["target_time"] = pd.to_datetime(tgt["target_time"])
    fr = fr.merge(tgt, on=["province_id", "target_time"], how="left")
    fr = fr.dropna(subset=["orc_swbgt", "orc_tmax", "orc_rh"]).reset_index(drop=True)

    # realistic forecast = actuals + per-lead error, then recompute sWBGT.
    k = fr["horizon_k"].to_numpy()
    fr["fc_tmax"] = fr["orc_tmax"] + rng.normal(0, TMAX_ERR(k))
    fr["fc_rh"] = np.clip(fr["orc_rh"] + rng.normal(0, RH_ERR(k)), 0, 100)
    fr["fc_swbgt"] = swbgt(fr["fc_tmax"].to_numpy(), fr["fc_rh"].to_numpy())

    perfect_feats = base_feats + ["orc_swbgt", "orc_tmax", "orc_rh"]
    realistic_feats = base_feats + ["fc_swbgt", "fc_tmax", "fc_rh"]

    yr = pd.to_datetime(fr["origin_time"]).dt.year
    tr, va, te = fr[yr <= 2023], fr[yr == 2024], fr[yr == 2025]
    print(f"frame rows={len(fr)} provinces={fr['province_id'].nunique()} "
          f"test n={len(te)} base_rate={te['y'].mean():.3f}\n", flush=True)

    runs = {}
    for label, feats in [("baseline (antecedent only)", base_feats),
                         ("+ perfect forecast (oracle)", perfect_feats),
                         ("+ realistic forecast (per-lead error)", realistic_feats)]:
        m, cal, thr = _fit(tr, va, feats)
        p = _predict(m, cal, feats, te)
        mt = compute_metrics(te["y"].to_numpy(), p, thr)
        runs[label] = (mt, p, thr)
        yhat = (p >= thr).astype(int)
        prec = precision_score(te["y"].to_numpy(), yhat, zero_division=0)
        rec = recall_score(te["y"].to_numpy(), yhat, zero_division=0)
        print(f"  {label:40s} PR-AUC={mt['pr_auc']:.3f}  F2={mt['f2']:.3f}  "
              f"prec={prec:.3f}  rec={rec:.3f}", flush=True)

    b = runs["baseline (antecedent only)"][0]
    r = runs["+ realistic forecast (per-lead error)"][0]
    o = runs["+ perfect forecast (oracle)"][0]
    captured = (r["pr_auc"] - b["pr_auc"]) / (o["pr_auc"] - b["pr_auc"])
    print(f"\nREALIZABLE  PR-AUC {b['pr_auc']:.3f} -> {r['pr_auc']:.3f}  "
          f"(captures {captured*100:.0f}% of the 0.33->0.88 headroom)", flush=True)

    # per-lead decay: realistic-forecast PR-AUC by horizon (the physics story).
    print("\nper-horizon realizable lift (PR-AUC):", flush=True)
    yte = te["y"].to_numpy()
    pr_real = runs["+ realistic forecast (per-lead error)"][1]
    pr_base = runs["baseline (antecedent only)"][1]
    kte = te["horizon_k"].to_numpy()
    for kk in range(1, 8):
        mask = kte == kk
        if mask.sum() == 0 or yte[mask].sum() == 0:
            continue
        ap_b = average_precision_score(yte[mask], pr_base[mask])
        ap_r = average_precision_score(yte[mask], pr_real[mask])
        print(f"  lead {kk}d:  base {ap_b:.3f} -> realistic {ap_r:.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
