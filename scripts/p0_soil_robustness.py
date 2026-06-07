"""Is the soil-moisture delta signal or noise? (review gate)

±0.008 ROC with ~452 test positives is within one standard error of zero. This
runs two discriminating checks on identical rows / split as train_p0_soil:
  1. SEED variance: train each model over several LightGBM seeds; if the D-C
     spread is >= the observed +0.008, the "lift" is training noise.
  2. BOOTSTRAP: resample the test set ~1000x and form 90% CIs for D-C and B-A;
     claim an effect only if the CI excludes 0.
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import train as lgbm_train
from scripts.train_p0_soil import prepare, SM_COV


def _split(merged):
    yr = pd.to_datetime(merged["origin_time"]).dt.year
    split = sorted(yr.unique())[len(yr.unique()) // 2]
    return merged[yr < split], merged[yr >= split]


def _fit_predict(tr, te, feats, seed):
    m = lgbm_train(tr[feats], tr["y"].to_numpy(), random_state=seed)
    return np.asarray(m.predict_proba(te[feats]))[:, 1]


def main():
    merged, base, fc_cov = prepare()
    tr, te = _split(merged)
    yte = te["y"].to_numpy()
    sets = {"A": base, "B": base + SM_COV, "C": base + fc_cov,
            "D": base + fc_cov + SM_COV}
    print(f"rows={len(merged)} train={len(tr)} test={len(te)} pos={int(yte.sum())}\n",
          flush=True)

    # --- 1. seed variance ---
    seeds = [0, 1]
    rocs = {k: [] for k in sets}
    for s in seeds:
        for k, feats in sets.items():
            rocs[k].append(roc_auc_score(yte, _fit_predict(tr, te, feats, s)))
    print("SEED variance (ROC mean±std over seeds 0-4):")
    for k in sets:
        print(f"  {k}: {np.mean(rocs[k]):.3f} ± {np.std(rocs[k]):.3f}", flush=True)
    dDC = np.array(rocs["D"]) - np.array(rocs["C"])
    dBA = np.array(rocs["B"]) - np.array(rocs["A"])
    print(f"  D-C across seeds: mean {dDC.mean():+.4f} (min {dDC.min():+.4f}, max {dDC.max():+.4f})")
    print(f"  B-A across seeds: mean {dBA.mean():+.4f} (min {dBA.min():+.4f}, max {dBA.max():+.4f})\n",
          flush=True)

    # --- 2. bootstrap test-set ΔROC (fixed seed=42 fits) ---
    pred = {k: _fit_predict(tr, te, feats, 42) for k, feats in sets.items()}
    rng = np.random.default_rng(0)
    n = len(yte)
    bDC, bBA = [], []
    for _ in range(1000):
        idx = rng.integers(0, n, n)
        ys = yte[idx]
        if ys.sum() == 0 or ys.sum() == len(ys):
            continue
        bDC.append(roc_auc_score(ys, pred["D"][idx]) - roc_auc_score(ys, pred["C"][idx]))
        bBA.append(roc_auc_score(ys, pred["B"][idx]) - roc_auc_score(ys, pred["A"][idx]))
    for name, b in [("D-C (soil on top of P0)", bDC), ("B-A (soil over base)", bBA)]:
        lo, hi = np.percentile(b, [5, 95])
        verdict = "EXCLUDES 0 (real)" if (lo > 0 or hi < 0) else "INCLUDES 0 (noise)"
        print(f"BOOTSTRAP {name:26s} dROC median {np.median(b):+.4f}  90% CI [{lo:+.4f}, {hi:+.4f}]  -> {verdict}",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
