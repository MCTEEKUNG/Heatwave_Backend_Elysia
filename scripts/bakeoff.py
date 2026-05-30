"""Empirical model bake-off for Heatwave-AI.

Trains several model families on the SAME forecasting frame, temporal split,
calibration, and F2-threshold tuning as the production pipeline, then ranks them
with the repo's own imbalance-aware metrics (PR-AUC, F2, MCC, ROC-AUC, Brier)
plus a Brier Skill Score vs the climatological base rate.

Compared: LightGBM (production), Balanced Random Forest, Random Forest, XGBoost.

Run from repo root (needs data/processed/dataset.parquet):
  .venv\\Scripts\\python.exe scripts\\bakeoff.py
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.train import build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset.parquet"
PROVINCES = "data/provinces.csv"
OUT = "experiments/results/leaderboard.json"
HORIZONS = range(1, 8)


def _fit(name, Xtr, ytr):
    """Return a fitted estimator exposing predict_proba(X)[:, 1]."""
    pos = int((ytr == 1).sum())
    neg = int((ytr == 0).sum())
    spw = (neg / pos) if pos else 1.0
    if name == "lightgbm":
        return lgbm_train(Xtr, ytr)  # production training (scale_pos_weight inside)
    if name == "balanced_rf":
        from imblearn.ensemble import BalancedRandomForestClassifier
        m = BalancedRandomForestClassifier(
            n_estimators=200, max_depth=15, random_state=42, n_jobs=-1,
            replacement=True, sampling_strategy="auto", bootstrap=True)
        m.fit(Xtr, ytr)
        return m
    if name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        m = RandomForestClassifier(
            n_estimators=200, max_depth=15, class_weight="balanced",
            random_state=42, n_jobs=-1)
        m.fit(Xtr, ytr)
        return m
    if name == "xgboost":
        from xgboost import XGBClassifier
        m = XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, random_state=42, n_jobs=-1,
            eval_metric="logloss", tree_method="hist", scale_pos_weight=spw)
        m.fit(Xtr, ytr)
        return m
    raise ValueError(name)


def _proba(model, X):
    return np.asarray(model.predict_proba(X))[:, 1]


def main():
    if not os.path.exists(DATASET):
        print(f"missing {DATASET} -- run scripts/build_full_dataset.py first")
        return 1

    ds = pd.read_parquet(DATASET)
    if "lat" not in ds.columns:
        prov = pd.read_csv(PROVINCES)[["id", "lat", "lon"]]
        ds = ds.merge(prov, left_on="province_id", right_on="id", how="left").drop(columns=["id"])

    frame = build_frames(ds, horizons=HORIZONS)
    feats = feature_columns(frame)
    yr = pd.to_datetime(frame["origin_time"]).dt.year
    tr, va, te = frame[yr <= 2023], frame[yr == 2024], frame[yr == 2025]
    Xtr, ytr = tr[feats], tr["y"].to_numpy()
    Xva, yva = va[feats], va["y"].to_numpy()
    Xte, yte = te[feats], te["y"].to_numpy()
    print(f"frame rows={len(frame)} feats={len(feats)} "
          f"train={len(tr)} val={len(va)} test={len(te)} "
          f"test_pos_rate={yte.mean():.4f}", flush=True)

    base = float(yte.mean())
    brier_clim = base * (1 - base)  # Brier of always predicting the base rate

    candidates = ["lightgbm", "balanced_rf", "random_forest", "xgboost"]
    results = []
    for name in candidates:
        try:
            t0 = time.time()
            model = _fit(name, Xtr, ytr)
            raw_val = _proba(model, Xva)
            cal = fit_calibrator(raw_val, yva)
            thr = tune_threshold(calibrate(cal, raw_val), yva)
            cal_test = np.clip(calibrate(cal, _proba(model, Xte)), 0, 1)
            m = compute_metrics(yte, cal_test, thr)
            m["brier_skill_score"] = float(1 - m["brier"] / brier_clim) if brier_clim else None
            m["fit_seconds"] = round(time.time() - t0, 1)
            m.pop("reliability", None)  # keep leaderboard compact
            results.append({"model": name, **m})
            print(f"  {name:14s} F2={m['f2']:.3f} PR-AUC={m['pr_auc']:.3f} "
                  f"BSS={m['brier_skill_score']:.3f} ROC-AUC={m['roc_auc']:.3f} "
                  f"Brier={m['brier']:.4f} ({m['fit_seconds']}s)", flush=True)
        except ImportError as exc:
            print(f"  {name:14s} SKIPPED ({exc})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:14s} FAILED ({type(exc).__name__}: {exc})", flush=True)

    results.sort(key=lambda r: (r.get("f2") or 0, r.get("pr_auc") or 0), reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {
        "dataset": DATASET,
        "n_test": int(len(te)),
        "test_base_rate": base,
        "split": {"train": "<=2023", "val": "2024", "test": "2025"},
        "ranked_by": "f2 then pr_auc",
        "results": results,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\n==== LEADERBOARD (test 2025, ranked by F2) ====")
    print(f"{'model':14s} {'F2':>6s} {'PR-AUC':>7s} {'BSS':>6s} {'ROC':>6s} {'Brier':>7s} {'MCC':>6s}")
    for r in results:
        print(f"{r['model']:14s} {r['f2']:6.3f} {r['pr_auc']:7.3f} "
              f"{r['brier_skill_score']:6.3f} {r['roc_auc']:6.3f} {r['brier']:7.4f} {r['mcc']:6.3f}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
