"""P0 real-data version -- forecast covariates from REAL archived forecasts.

Replaces the per-lead noise model (scripts/p0_forecast_prototype.py) with actual
historical forecasts from the Open-Meteo Historical Forecast API. Fetches daily
Tmax + mean RH for the 20 dataset provinces, computes forecast sWBGT the SAME way
the label is built (swbgt(Tmax, mean RH)), joins them at target_time, and trains
baseline vs +real-forecast on the forecast-covered window.

IMPORTANT CAVEAT (honest framing): the Historical Forecast API returns a single
archived series per date (~short-lead quality), not lead-specific forecasts. So
the forecast feature has roughly uniform quality across horizons -- OPTIMISTIC at
long leads (a real day-7 forecast is worse). The noise-model prototype captures
lead decay better; the truth is bracketed between the two. Fully correct would
need lead-specific reforecasts (Open-Meteo previous-runs / ECMWF), which lack
multi-year coverage. Coverage also starts ~2022, so train/val/test = 2022-23 /
2024 / 2025 -- a thinner window than the full 1991-2025 baseline.

Run from repo root:  .venv\\Scripts\\python.exe scripts\\p0_forecast_real.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.frame_cache import cached_build_frames
from src.provinces import load_provinces
from src.features import feature_columns
from src.swbgt import swbgt
from src.openmeteo_client import _get_with_retry, _daily_to_df
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset.parquet"
FC_CACHE = "data/processed/historical_forecast.parquet"
FC_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FC_VARS = ["temperature_2m_max", "relative_humidity_2m_mean"]
START, END = "2022-01-01", "2025-12-31"


def fetch_forecast_covariates(province_ids):
    if os.path.exists(FC_CACHE):
        print(f"using cached forecast covariates: {FC_CACHE}", flush=True)
        return pd.read_parquet(FC_CACHE)
    prov = load_provinces("data/provinces.csv")
    prov = prov[prov["id"].isin(province_ids)]
    frames = []
    for i, (_, p) in enumerate(prov.iterrows(), start=1):
        params = {"latitude": p["lat"], "longitude": p["lon"],
                  "start_date": START, "end_date": END,
                  "daily": ",".join(FC_VARS), "timezone": "Asia/Bangkok"}
        df = _daily_to_df(_get_with_retry(FC_URL, params).json())
        df["province_id"] = p["id"]
        frames.append(df)
        print(f"  [{i}/{len(prov)}] {p['name_en']:20s} rows={len(df)} "
              f"({df['time'].min().date()}..{df['time'].max().date()})", flush=True)
        time.sleep(1.0)  # stay under the weighted rate limit
    fc = pd.concat(frames, ignore_index=True)
    fc = fc.rename(columns={"time": "target_time",
                            "temperature_2m_max": "fc_tmax",
                            "relative_humidity_2m_mean": "fc_rh"})
    fc["fc_swbgt"] = swbgt(fc["fc_tmax"].to_numpy(), fc["fc_rh"].to_numpy())
    os.makedirs(os.path.dirname(FC_CACHE), exist_ok=True)
    fc.to_parquet(FC_CACHE, index=False)
    print(f"saved {len(fc)} forecast rows -> {FC_CACHE}", flush=True)
    return fc


def _fit(tr, va, feats):
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    return m, cal, thr


def _predict(m, cal, feats, df):
    return np.clip(calibrate(cal, np.asarray(m.predict_proba(df[feats]))[:, 1]), 0, 1)


def main():
    ds = pd.read_parquet(DATASET)
    ids = sorted(ds["province_id"].unique().tolist())
    fc = fetch_forecast_covariates(ids)

    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    base_feats = feature_columns(frame)
    fr = frame.copy()
    fr["target_time"] = pd.to_datetime(fr["target_time"])
    fc["target_time"] = pd.to_datetime(fc["target_time"])
    fr = fr.merge(fc[["province_id", "target_time", "fc_tmax", "fc_rh", "fc_swbgt"]],
                  on=["province_id", "target_time"], how="inner")  # forecast-covered only
    fc_feats = base_feats + ["fc_swbgt", "fc_tmax", "fc_rh"]

    yr = pd.to_datetime(fr["origin_time"]).dt.year
    tr, va, te = fr[yr <= 2023], fr[yr == 2024], fr[yr == 2025]
    print(f"\nforecast-covered frame rows={len(fr)} "
          f"train={len(tr)} val={len(va)} test={len(te)} "
          f"test_base_rate={te['y'].mean():.3f}\n", flush=True)

    runs = {}
    for label, feats in [("baseline (antecedent only)", base_feats),
                         ("+ REAL forecast covariates", fc_feats)]:
        m, cal, thr = _fit(tr, va, feats)
        p = _predict(m, cal, feats, te)
        mt = compute_metrics(te["y"].to_numpy(), p, thr)
        yhat = (p >= thr).astype(int)
        prec = precision_score(te["y"].to_numpy(), yhat, zero_division=0)
        rec = recall_score(te["y"].to_numpy(), yhat, zero_division=0)
        runs[label] = (mt, p, thr)
        print(f"  {label:34s} PR-AUC={mt['pr_auc']:.3f}  F2={mt['f2']:.3f}  "
              f"prec={prec:.3f}  rec={rec:.3f}", flush=True)

    b = runs["baseline (antecedent only)"][0]
    r = runs["+ REAL forecast covariates"][0]
    print(f"\nREAL-DATA LIFT  PR-AUC {b['pr_auc']:.3f} -> {r['pr_auc']:.3f}  "
          f"F2 {b['f2']:.3f} -> {r['f2']:.3f}", flush=True)

    print("\nper-horizon PR-AUC (note: forecast ~uniform quality, optimistic at long lead):", flush=True)
    yte = te["y"].to_numpy()
    kte = te["horizon_k"].to_numpy()
    pb = runs["baseline (antecedent only)"][1]
    prf = runs["+ REAL forecast covariates"][1]
    for kk in range(1, 8):
        mask = kte == kk
        if mask.sum() == 0 or yte[mask].sum() == 0:
            continue
        print(f"  lead {kk}d:  base {average_precision_score(yte[mask], pb[mask]):.3f} "
              f"-> real {average_precision_score(yte[mask], prf[mask]):.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
