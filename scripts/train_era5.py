"""Train + evaluate the production model on the clean ERA5+NDVI dataset (temporal)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics
from pipeline.leaderboard import upsert_model

DATASET = "data/processed/dataset_era5.parquet"


def year_split(frame, train_max=2021, val_max=2023):
    y = pd.to_datetime(frame["origin_time"]).dt.year
    return frame[y <= train_max], frame[(y > train_max) & (y <= val_max)], frame[y > val_max]


def main():
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    feats = feature_columns(frame)
    tr, va, te = year_split(frame)
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    pt = np.clip(calibrate(cal, np.asarray(m.predict_proba(te[feats]))[:, 1]), 0, 1)
    mt = compute_metrics(te["y"].to_numpy(), pt, thr)
    print(f"ERA5 clean model — PR-AUC={mt['pr_auc']:.3f} F2={mt['f2']:.3f} "
          f"ROC={mt['roc_auc']:.3f} (test n={mt['n']}, base={mt['base_rate']:.3f})")
    upsert_model("era5_lgbm", mt, n_provinces=int(frame["province_id"].nunique()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
