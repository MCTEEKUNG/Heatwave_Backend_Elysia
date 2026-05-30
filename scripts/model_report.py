"""Senior-engineer model report: a deep-dive on the production model so you know
*what to fix next*, not just the headline score.

Trains the production LightGBM through the real pipeline (calibrate + F2 tune on
2024, evaluate on 2025) and writes experiments/results/model_report.json with:
run/data/split metadata, headline metrics vs climatology + persistence
baselines, confusion matrix, a threshold sweep (operating-point selection on
VALIDATION), a calibration curve, LightGBM gain feature importance, per-horizon
skill (lead 1-7), and per-region / per-province error slices.

Split discipline (matches production):
  - threshold / operating point  -> selected on VALIDATION (2024)
  - confusion, headline, calibration, slices -> TEST (2025) at that fixed threshold

Run from repo root (needs data/processed/dataset.parquet):
  .venv\\Scripts\\python.exe scripts\\model_report.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.train import build_frames
from src.features import feature_columns
from src.model import train as lgbm_train, CalibratedModel
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics

DATASET = "data/processed/dataset.parquet"
PROVINCES = "data/provinces.csv"
OUT = "experiments/results/model_report.json"
HORIZONS = range(1, 8)
MODEL = "lightgbm"
MIN_POS = 30  # min positives for a slice to be ranked (avoid sparse-slice noise)


def _f2(p, r):
    return 0.0 if (4 * p + r) == 0 else (5 * p * r) / (4 * p + r)


def _git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       text=True).strip()
    except Exception:
        return None


def _slice_metrics(y, prob, thr):
    """F2/precision/recall + counts for one slice; None-safe on single-class."""
    y = np.asarray(y, dtype=int)
    n, n_pos = int(len(y)), int(y.sum())
    if n == 0:
        return None
    pred = (np.asarray(prob) >= thr).astype(int)
    if 0 < n_pos < n:
        p = float(precision_score(y, pred, zero_division=0))
        r = float(recall_score(y, pred, zero_division=0))
    else:
        p = r = None
    return {"n": n, "n_pos": n_pos, "base_rate": round(n_pos / n, 4),
            "precision": None if p is None else round(p, 4),
            "recall": None if r is None else round(r, 4),
            "f2": None if (p is None or r is None) else round(_f2(p, r), 4)}


def main():
    if not os.path.exists(DATASET):
        print(f"missing {DATASET} -- run scripts/build_full_dataset.py first")
        return 1

    ds = pd.read_parquet(DATASET)
    if "lat" not in ds.columns:
        prov = pd.read_csv(PROVINCES)[["id", "lat", "lon"]]
        ds = ds.merge(prov, left_on="province_id", right_on="id", how="left").drop(columns=["id"])
    prov_meta = pd.read_csv(PROVINCES)[["id", "name_en", "region"]]

    frame = build_frames(ds, horizons=HORIZONS)
    feats = feature_columns(frame)
    yr = pd.to_datetime(frame["origin_time"]).dt.year
    tr, va, te = frame[yr <= 2023], frame[yr == 2024], frame[yr == 2025]
    Xtr, ytr = tr[feats], tr["y"].to_numpy()
    Xva, yva = va[feats], va["y"].to_numpy()
    Xte, yte = te[feats], te["y"].to_numpy()
    print(f"frame={len(frame)} feats={len(feats)} train={len(tr)} val={len(va)} test={len(te)}", flush=True)

    # --- train production model + calibrate + tune threshold on VALIDATION ---
    model = lgbm_train(Xtr, ytr)
    raw_val = np.asarray(model.predict_proba(Xva))[:, 1]
    cal = fit_calibrator(raw_val, yva)
    cal_val = calibrate(cal, raw_val)
    thr = float(tune_threshold(cal_val, yva))
    bundle = CalibratedModel(model, cal, thr, feats, "lgbm-v1")
    cal_test = np.clip(bundle.predict_proba(Xte)[:, 1], 0, 1)
    print(f"trained lightgbm; threshold(val)={thr:.4f}", flush=True)

    base = float(yte.mean())
    brier_clim = base * (1 - base)

    # --- headline on TEST ---
    head = compute_metrics(yte, cal_test, thr)
    reliability = head.pop("reliability")
    pred_te = (cal_test >= thr).astype(int)
    tp = int(((pred_te == 1) & (yte == 1)).sum()); fp = int(((pred_te == 1) & (yte == 0)).sum())
    fn = int(((pred_te == 0) & (yte == 1)).sum()); tn = int(((pred_te == 0) & (yte == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    head["brier_skill_score"] = float(1 - head["brier"] / brier_clim) if brier_clim else None
    head.update(precision=round(precision, 4), recall=round(recall, 4),
                specificity=round(specificity, 4), evaluated_on="test(2025)")

    # --- baselines on TEST: climatology (const base rate) + persistence ---
    clim = compute_metrics(yte, np.full(len(yte), base), thr); clim.pop("reliability")
    persist = te.merge(ds[["province_id", "time", "heatwave"]],
                       left_on=["province_id", "origin_time"], right_on=["province_id", "time"],
                       how="left")["heatwave"].fillna(0).to_numpy()
    pm = compute_metrics(yte, persist.astype(float), 0.5); pm.pop("reliability")
    persist_pred = persist.astype(int)
    baselines = {
        "climatology": {"f2": round(clim["f2"], 4), "pr_auc": round(clim["pr_auc"] or 0, 4),
                        "brier": round(clim["brier"], 4)},
        "persistence": {
            "f2": round(pm["f2"], 4),
            "precision": round(float(precision_score(yte, persist_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(yte, persist_pred, zero_division=0)), 4)},
    }

    # --- threshold sweep on VALIDATION (operating-point selection) ---
    p, r, t = precision_recall_curve(yva, cal_val)
    sweep = []
    idx = np.linspace(0, len(t) - 1, min(60, len(t))).astype(int)
    for i in idx:
        sweep.append({"threshold": round(float(t[i]), 4), "precision": round(float(p[i]), 4),
                      "recall": round(float(r[i]), 4), "f2": round(_f2(float(p[i]), float(r[i])), 4)})

    # --- feature importance: LightGBM GAIN off the underlying booster, by name ---
    try:
        gains = model.booster_.feature_importance(importance_type="gain")
        fi = sorted(({"feature": f, "importance": round(float(g), 1)}
                     for f, g in zip(feats, gains)), key=lambda d: d["importance"], reverse=True)[:20]
    except Exception as exc:  # noqa: BLE001
        fi = []
        print(f"feature importance unavailable: {exc}", flush=True)

    # --- per-horizon skill on TEST (degradation vs lead time) ---
    per_h = []
    for k in HORIZONS:
        m = te["horizon_k"] == k
        s = _slice_metrics(yte[m.to_numpy()], cal_test[m.to_numpy()], thr)
        mm = compute_metrics(yte[m.to_numpy()], cal_test[m.to_numpy()], thr)
        per_h.append({"horizon": int(k), "n_pos": s["n_pos"], "recall": s["recall"],
                      "f2": round(mm["f2"], 4), "pr_auc": round(mm["pr_auc"] or 0, 4)})

    # --- error slices on TEST: per region + worst provinces ---
    te_pid = te["province_id"].to_numpy()
    pid2region = dict(zip(prov_meta["id"], prov_meta["region"]))
    pid2name = dict(zip(prov_meta["id"], prov_meta["name_en"]))
    by_region = []
    for region in sorted(set(pid2region.get(p) for p in te_pid)):
        mask = np.array([pid2region.get(p) == region for p in te_pid])
        sm = _slice_metrics(yte[mask], cal_test[mask], thr)
        if sm:
            by_region.append({"region": region, **sm})
    by_region.sort(key=lambda d: (d["f2"] is None, d["f2"] if d["f2"] is not None else 1))
    prov_slices = []
    for pid in sorted(set(te_pid)):
        mask = te_pid == pid
        sm = _slice_metrics(yte[mask], cal_test[mask], thr)
        if sm and sm["n_pos"] >= MIN_POS and sm["f2"] is not None:
            prov_slices.append({"province": pid2name.get(int(pid), str(pid)),
                                "region": pid2region.get(int(pid)), **sm})
    worst = sorted(prov_slices, key=lambda d: d["f2"])[:10]
    best = sorted(prov_slices, key=lambda d: -d["f2"])[:5]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "model": MODEL,
        "note": "production model (CalibratedModel = LightGBM + isotonic); within noise of balanced_rf on the leaderboard",
        "dataset": {"path": DATASET, "n_provinces": int(ds["province_id"].nunique()),
                    "rows_frame": int(len(frame)), "horizons": "1-7"},
        "split": {"train": "<=2023", "val": "2024", "test": "2025",
                  "n_train": int(len(tr)), "n_val": int(len(va)), "n_test": int(len(te)),
                  "train_pos_rate": round(float(ytr.mean()), 4),
                  "val_pos_rate": round(float(yva.mean()), 4),
                  "test_pos_rate": round(base, 4)},
        "params": {k: model.get_params()[k] for k in
                   ("n_estimators", "learning_rate", "num_leaves", "min_child_samples")
                   if k in model.get_params()},
        "operating_point": {"threshold": round(thr, 4), "selected_on": "validation(2024)"},
        "headline": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in head.items()},
        "confusion": {"evaluated_on": "test(2025)", "threshold": round(thr, 4),
                      "tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "baselines": {"evaluated_on": "test(2025)", **baselines},
        "threshold_sweep": {"selected_on": "validation(2024)", "chosen_threshold": round(thr, 4),
                            "points": sweep},
        "calibration": {"evaluated_on": "test(2025)",
                        "bins": [{"mean_pred": b["mean_pred"], "frac_pos": b["frac_pos"],
                                  "count": b["count"]} for b in reliability]},
        "feature_importance": {"type": "gain", "top": fi},
        "per_horizon": {"evaluated_on": "test(2025)", "rows": per_h},
        "slices": {"evaluated_on": "test(2025)", "min_pos": MIN_POS,
                   "by_region": by_region, "worst_provinces": worst, "best_provinces": best},
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nwrote {OUT}")
    print(f"  test F2={head['f2']:.3f}  precision={precision:.3f}  recall={recall:.3f}  "
          f"BSS={head['brier_skill_score']:.3f}")
    print(f"  per-horizon F2: {[round(h['f2'], 2) for h in per_h]}")
    print(f"  worst regions: {[(d['region'], d['f2']) for d in by_region[:3]]}")
    print(f"  worst provinces: {[(d['province'], d['f2']) for d in worst[:3]]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
