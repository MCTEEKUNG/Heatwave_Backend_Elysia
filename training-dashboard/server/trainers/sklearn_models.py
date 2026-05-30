"""Trainers for the non-LightGBM model families shown in the dashboard:
Balanced Random Forest, Random Forest, XGBoost, CatBoost, and an MLP.

Each trains on data/processed/dataset.parquet through the SAME forecasting
frame, temporal split, isotonic calibration, and F2-threshold tuning as the
production pipeline, then returns the repo's imbalance-aware metrics (so the
dashboard's final-metrics panel is comparable to LightGBM / the leaderboard).

Progress is COARSE (phase-based): these families fit as a single black-box call
(no per-iteration callback like LightGBM), so the bar advances by pipeline phase
-- load -> features -> fit -> calibrate -> evaluate -> done. The 'fit' phase is
the long one for Random Forest / MLP; the status message says so.
"""
from __future__ import annotations

import os

from .base import ProgressCb, ShouldStop, Trainer

DATASET_PATH = "data/processed/dataset.parquet"
PROVINCES_PATH = "data/provinces.csv"

# Registry-facing names -> human labels are defined on the web side.
SUPPORTED = ("balanced_rf", "random_forest", "xgboost", "catboost", "mlp")


class _StopTraining(Exception):
    """Internal: raised at a phase boundary to abort cooperatively."""


def _make(name: str, scale_pos_weight: float):
    """Build an (unfitted) estimator exposing predict_proba; matches bakeoff.py."""
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
            eval_metric="logloss", tree_method="hist",
            scale_pos_weight=scale_pos_weight)
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
    raise ValueError(f"unsupported model: {name!r}")


class ModelTrainer(Trainer):
    """A dashboard trainer for one non-LightGBM model family."""

    def __init__(self, name: str):
        self.name = name

    def run(self, config: dict, progress_cb: ProgressCb, should_stop: ShouldStop) -> dict:
        import numpy as np
        import pandas as pd
        from pipeline.train import build_frames
        from src.features import feature_columns
        from src.calibration import fit_calibrator, calibrate, tune_threshold
        from evaluation.heatwave_metrics import compute_metrics

        if not os.path.exists(DATASET_PATH):
            raise FileNotFoundError(
                f"dataset not found: {DATASET_PATH} -- run build_dataset first")

        TOTAL = 6

        def check_stop():
            if should_stop():
                raise _StopTraining()

        try:
            progress_cb(1, TOTAL, "loading dataset")
            ds = pd.read_parquet(DATASET_PATH)
            if "lat" not in ds.columns:
                prov = pd.read_csv(PROVINCES_PATH)[["id", "lat", "lon"]]
                ds = ds.merge(prov, left_on="province_id", right_on="id",
                              how="left").drop(columns=["id"])
            check_stop()

            progress_cb(2, TOTAL, "building forecasting features")
            frame = build_frames(ds, horizons=range(1, 8))
            feats = feature_columns(frame)
            yr = pd.to_datetime(frame["origin_time"]).dt.year
            tr, va, te = frame[yr <= 2023], frame[yr == 2024], frame[yr == 2025]
            Xtr, ytr = tr[feats], tr["y"].to_numpy()
            Xva, yva = va[feats], va["y"].to_numpy()
            Xte, yte = te[feats], te["y"].to_numpy()
            pos, neg = int(ytr.sum()), int((ytr == 0).sum())
            spw = (neg / pos) if pos else 1.0
            check_stop()

            progress_cb(3, TOTAL, f"fitting {self.name} (this can take a while)")
            model = _make(self.name, spw)
            model.fit(Xtr, ytr)
            check_stop()

            progress_cb(4, TOTAL, "calibrating probabilities (isotonic)")
            raw_val = np.asarray(model.predict_proba(Xva))[:, 1]
            cal = fit_calibrator(raw_val, yva)
            thr = float(tune_threshold(calibrate(cal, raw_val), yva))
            check_stop()

            progress_cb(5, TOTAL, "evaluating on held-out test (2025)")
            cal_test = np.clip(calibrate(cal, np.asarray(model.predict_proba(Xte))[:, 1]), 0, 1)
            report = compute_metrics(yte, cal_test, thr)
            base = float(yte.mean())
            brier_clim = base * (1 - base)
            report["brier_skill_score"] = float(1 - report["brier"] / brier_clim) if brier_clim else None
            report.pop("reliability", None)
            report["trainer"] = self.name
            report["threshold"] = thr
            report["n_provinces"] = int(ds["province_id"].nunique())

            progress_cb(6, TOTAL, "done")
            return report
        except _StopTraining:
            return {"trainer": self.name, "stopped": True}
