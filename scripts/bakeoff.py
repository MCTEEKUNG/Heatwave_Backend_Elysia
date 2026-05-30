"""Empirical model bake-off for Heatwave-AI.

Trains several model families on the SAME forecasting frame, temporal split,
calibration, and F2-threshold tuning as the production pipeline, then ranks them
with the repo's imbalance-aware metrics (PR-AUC, F2, MCC, ROC-AUC, Brier) plus a
Brier Skill Score vs the climatological base rate.

Models: LightGBM (production), Balanced Random Forest, Random Forest, XGBoost,
CatBoost, an MLP reference, and a soft-voting ensemble of the strong GBDTs.
KAN is deliberately deferred (dependency-heavy; tabular evidence says it loses).

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

BASE_MODELS = ["lightgbm", "balanced_rf", "random_forest", "xgboost", "catboost", "mlp"]
ENSEMBLE_MEMBERS = ["lightgbm", "xgboost", "catboost"]  # strong GBDTs; uses whatever fit


def _make(name, spw):
    if name == "balanced_rf":
        from imblearn.ensemble import BalancedRandomForestClassifier
        return BalancedRandomForestClassifier(
            n_estimators=200, max_depth=15, random_state=42, n_jobs=-1,
            replacement=True, sampling_strategy="auto", bootstrap=True)
    if name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=200, max_depth=15, class_weight="balanced",
            random_state=42, n_jobs=-1)
    if name == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, random_state=42, n_jobs=-1,
            eval_metric="logloss", tree_method="hist", scale_pos_weight=spw)
    if name == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(
            iterations=300, depth=6, learning_rate=0.1, random_seed=42,
            auto_class_weights="Balanced", verbose=0, allow_writing_files=False)
    if name == "mlp":
        from sklearn.neural_network import MLPClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), MLPClassifier(
            hidden_layer_sizes=(256, 128, 64), alpha=1e-4, learning_rate_init=1e-3,
            max_iter=60, early_stopping=True, n_iter_no_change=8, random_state=42))
    raise ValueError(name)


def _proba(model, X):
    return np.asarray(model.predict_proba(X))[:, 1]


def _fit_raw(name, Xtr, ytr, Xva, Xte, spw):
    """Fit a model and return (raw_val_probs, raw_test_probs, fit_seconds)."""
    t0 = time.time()
    if name == "lightgbm":
        model = lgbm_train(Xtr, ytr)  # production training (scale_pos_weight inside)
    else:
        model = _make(name, spw)
        model.fit(Xtr, ytr)
    return _proba(model, Xva), _proba(model, Xte), round(time.time() - t0, 1)


def _score(name, raw_val, raw_test, yva, yte, brier_clim, fit_s):
    cal = fit_calibrator(raw_val, yva)
    thr = tune_threshold(calibrate(cal, raw_val), yva)
    cal_test = np.clip(calibrate(cal, raw_test), 0, 1)
    m = compute_metrics(yte, cal_test, thr)
    m["brier_skill_score"] = float(1 - m["brier"] / brier_clim) if brier_clim else None
    m["fit_seconds"] = fit_s
    m.pop("reliability", None)
    return {"model": name, **m}


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
    pos, neg = int(ytr.sum()), int((ytr == 0).sum())
    spw = (neg / pos) if pos else 1.0
    print(f"frame rows={len(frame)} feats={len(feats)} provinces={ds['province_id'].nunique()} "
          f"train={len(tr)} val={len(va)} test={len(te)} test_pos_rate={yte.mean():.4f}", flush=True)

    base = float(yte.mean())
    brier_clim = base * (1 - base)

    raws, results = {}, []
    for name in BASE_MODELS:
        try:
            rv, rt, fit_s = _fit_raw(name, Xtr, ytr, Xva, Xte, spw)
            raws[name] = (rv, rt)
            results.append(_score(name, rv, rt, yva, yte, brier_clim, fit_s))
            r = results[-1]
            print(f"  {name:14s} F2={r['f2']:.3f} PR-AUC={r['pr_auc']:.3f} "
                  f"BSS={r['brier_skill_score']:.3f} ROC={r['roc_auc']:.3f} ({fit_s}s)", flush=True)
        except ImportError as exc:
            print(f"  {name:14s} SKIPPED ({exc})", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:14s} FAILED ({type(exc).__name__}: {exc})", flush=True)

    members = [m for m in ENSEMBLE_MEMBERS if m in raws]
    if len(members) >= 2:
        rv = np.mean([raws[m][0] for m in members], axis=0)
        rt = np.mean([raws[m][1] for m in members], axis=0)
        ename = "ensemble(" + "+".join(members) + ")"
        results.append(_score(ename, rv, rt, yva, yte, brier_clim, 0.0))
        r = results[-1]
        print(f"  {ename:32s} F2={r['f2']:.3f} PR-AUC={r['pr_auc']:.3f} "
              f"BSS={r['brier_skill_score']:.3f} ROC={r['roc_auc']:.3f}", flush=True)

    results.sort(key=lambda r: (r.get("f2") or 0, r.get("pr_auc") or 0), reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {
        "dataset": DATASET,
        "n_provinces": int(ds["province_id"].nunique()),
        "n_test": int(len(te)),
        "test_base_rate": base,
        "split": {"train": "<=2023", "val": "2024", "test": "2025"},
        "ranked_by": "f2 then pr_auc",
        "results": results,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\n==== LEADERBOARD (test 2025, ranked by F2) ====")
    print(f"{'model':34s} {'F2':>6s} {'PR-AUC':>7s} {'BSS':>6s} {'ROC':>6s} {'Brier':>7s} {'MCC':>6s}")
    for r in results:
        print(f"{r['model']:34s} {r['f2']:6.3f} {r['pr_auc']:7.3f} "
              f"{r['brier_skill_score']:6.3f} {r['roc_auc']:6.3f} {r['brier']:7.4f} {r['mcc']:6.3f}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
