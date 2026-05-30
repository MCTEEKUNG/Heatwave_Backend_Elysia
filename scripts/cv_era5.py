"""Rolling-origin CV for era5_lgbm with base-rate-fair, threshold-independent metrics.

Primary metrics (fold mean +/- std):
  - ROC-AUC          (threshold- AND prevalence-independent ranking)
  - PR-AUC lift      = PR-AUC / test prevalence  (PR-AUC's no-skill floor IS the
                       prevalence, so raw PR-AUC across years with different base
                       rates is not comparable; lift is)
Operating point: a FIXED rule (threshold set on val to hit target recall=0.80),
NOT per-year F2-max -- so the metric doesn't swing with year-to-year base rate.
This is the trustworthy, honest read of the clean antecedent model's ceiling.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate
from evaluation.cv import rolling_origin_folds

DATASET = "data/processed/dataset_era5.parquet"
TARGET_RECALL = 0.80


def threshold_for_recall(probs, y, target):
    """Largest threshold whose recall on (probs,y) is >= target (maximises precision)."""
    pos = probs[y == 1]
    if len(pos) == 0:
        return 0.5
    return float(np.quantile(pos, max(0.0, 1.0 - target)))


def at_threshold(probs, y, thr):
    yhat = (probs >= thr).astype(int)
    tp = int(((yhat == 1) & (y == 1)).sum()); fp = int(((yhat == 1) & (y == 0)).sum())
    fn = int(((yhat == 0) & (y == 1)).sum())
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    f2 = (5 * prec * rec) / (4 * prec + rec) if (prec + rec) else 0.0
    return rec, prec, f2


def main():
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    feats = feature_columns(frame)
    yr = pd.to_datetime(frame["origin_time"]).dt.year
    print(f"frame rows={len(frame)} features={len(feats)}  CV folds (test 2021-2025):\n", flush=True)

    rows = []
    for train_max, test_year in rolling_origin_folds(2021, 2025):
        val_year = train_max
        tr = frame[yr <= val_year - 1]; va = frame[yr == val_year]; te = frame[yr == test_year]
        if len(tr) == 0 or va["y"].sum() == 0 or te["y"].sum() == 0:
            print(f"  fold test={test_year}: skipped (insufficient positives)", flush=True); continue
        m = lgbm_train(tr[feats], tr["y"].to_numpy())
        cal = fit_calibrator(np.asarray(m.predict_proba(va[feats]))[:, 1], va["y"].to_numpy())
        vp = np.clip(calibrate(cal, np.asarray(m.predict_proba(va[feats]))[:, 1]), 0, 1)
        thr = threshold_for_recall(vp, va["y"].to_numpy(), TARGET_RECALL)
        tp_prob = np.clip(calibrate(cal, np.asarray(m.predict_proba(te[feats]))[:, 1]), 0, 1)
        yte = te["y"].to_numpy()
        roc = roc_auc_score(yte, tp_prob); prauc = average_precision_score(yte, tp_prob)
        prev = yte.mean(); lift = prauc / prev if prev else 0.0
        rec, prec, f2 = at_threshold(tp_prob, yte, thr)
        rows.append(dict(test=test_year, roc=roc, prauc=prauc, prev=prev, lift=lift,
                         rec=rec, prec=prec, f2=f2))
        print(f"  test={test_year}: ROC={roc:.3f} PR-AUC={prauc:.3f} prev={prev:.3f} "
              f"lift={lift:.2f}x  @rec~.80: rec={rec:.2f} prec={prec:.2f} F2={f2:.3f}", flush=True)

    df = pd.DataFrame(rows)
    print("\nMEAN +/- STD across folds:")
    for k, lab in [("roc", "ROC-AUC"), ("lift", "PR-AUC lift (x prevalence)"),
                   ("prec", "precision @rec~.80"), ("f2", "F2 @rec~.80")]:
        print(f"  {lab:30s} {df[k].mean():.3f} +/- {df[k].std():.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
