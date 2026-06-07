"""Report the full imbalance-aware skill metrics (TSS/HSS/balanced-acc/G-mean,
plus ROC/PR-AUC) for the soil-moisture experiment's C (forecast covariate) vs
D (forecast + soil), with an F2 operating point tuned on a held-out val year
(2016 train / 2017 val / 2018-19 test). Feeds the HTML report."""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.train_p0_soil import prepare, SM_COV
from src.model import train as lgbm_train
from src.calibration import tune_threshold
from evaluation.heatwave_metrics import compute_metrics

KEYS = ["roc_auc", "pr_auc", "f2", "tss", "hss", "balanced_accuracy", "g_mean"]


def run(tr, va, te, feats, name):
    m = lgbm_train(tr[feats], tr["y"].to_numpy(), random_state=42)
    pv = m.predict_proba(va[feats])[:, 1]
    thr = float(tune_threshold(pv, va["y"].to_numpy()))
    pt = m.predict_proba(te[feats])[:, 1]
    met = compute_metrics(te["y"].to_numpy(), pt, threshold=thr)
    out = {k: (round(met[k], 4) if met[k] is not None else None) for k in KEYS}
    out["threshold"] = round(thr, 4)
    print(f"{name}: {json.dumps(out)}", flush=True)
    return out


def main():
    merged, base, fc_cov = prepare()
    yr = pd.to_datetime(merged["origin_time"]).dt.year
    tr, va, te = merged[yr <= 2016], merged[yr == 2017], merged[yr >= 2018]
    print(f"train(2016)={len(tr)} val(2017)={len(va)} test(2018-19)={len(te)} "
          f"test_pos={int(te['y'].sum())}\n", flush=True)
    run(tr, va, te, base + fc_cov, "C +forecast")
    run(tr, va, te, base + fc_cov + SM_COV, "D +forecast+soil")
    return 0


if __name__ == "__main__":
    sys.exit(main())
