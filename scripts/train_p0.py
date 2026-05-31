"""Measure the REAL P0 lift: antecedent-only vs + genuine GEFS forecast covariate.

Joins the GEFS reforecast store (real lead-k forecast tmax) into the leakage-safe
forecasting frame at (province_id, origin=issue_date, horizon=lead_k, target),
then trains TWO models on the IDENTICAL matched rows / split:
  A = antecedent features only            (the ceiling we measured: ROC ~0.6-0.76)
  B = antecedent + fc_tmax                 (forecast of the target day -> P0)
The delta (B - A) on the same rows is the first HONEST P0 measurement: not the
leaky oracle, not the noise model, not analysis-disguised-as-forecast.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.heat_index import rh_from_specific_humidity, heat_index_c

DATASET = "data/processed/dataset_era5.parquet"
GEFS = "data/processed/gefs_forecast_store.parquet"


def join_forecast(frame: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Attach fc_tmax to frame rows whose (province, origin, horizon, target) matches
    a real forecast issued at origin for that target/lead. Inner join -> covered rows."""
    f = frame.copy()
    f["origin_d"] = pd.to_datetime(f["origin_time"]).dt.date.astype(str)
    f["target_d"] = pd.to_datetime(f["target_time"]).dt.date.astype(str)
    keep = ["province_id", "origin_d", "target_d", "horizon_k", "fc_tmax"]
    if "fc_spfh" in store.columns:
        keep.append("fc_spfh")
    s = store.rename(columns={"issue_date": "origin_d", "target_date": "target_d",
                              "lead_k": "horizon_k"})[keep]
    merged = f.merge(s, on=["province_id", "origin_d", "target_d", "horizon_k"], how="inner")
    return merged


def _evaluate(tr, te, feats, label):
    if tr["y"].sum() == 0 or te["y"].sum() == 0:
        print(f"  {label}: insufficient positives (train_pos={tr['y'].sum()}, test_pos={te['y'].sum()})")
        return None
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    p = np.asarray(m.predict_proba(te[feats]))[:, 1]
    yte = te["y"].to_numpy()
    roc = roc_auc_score(yte, p); prauc = average_precision_score(yte, p)
    prev = yte.mean()
    print(f"  {label:28s} ROC={roc:.3f} PR-AUC={prauc:.3f} lift={prauc/prev:.2f}x", flush=True)
    return dict(roc=roc, prauc=prauc, lift=prauc / prev)


def main():
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    base_feats = feature_columns(frame)
    store = pd.read_parquet(GEFS)
    merged = join_forecast(frame, store)
    # forecast heat-index covariate (humidity-inclusive — matches label + oracle signal)
    covariates = ["fc_tmax"]
    if "fc_spfh" in merged.columns and merged["fc_spfh"].notna().any():
        merged["fc_rh"] = rh_from_specific_humidity(merged["fc_spfh"], merged["fc_tmax"])
        merged["fc_heat_index"] = heat_index_c(merged["fc_tmax"], merged["fc_rh"])
        covariates = ["fc_tmax", "fc_rh", "fc_heat_index"]
        merged = merged.dropna(subset=["fc_heat_index"])
    print(f"P0 covariates: {covariates}", flush=True)
    yr = pd.to_datetime(merged["origin_time"]).dt.year
    print(f"matched rows={len(merged)} (covered by real forecasts) "
          f"years={sorted(yr.unique().tolist())} pos_rate={merged['y'].mean():.3f}", flush=True)
    if len(merged) == 0:
        print("no matched rows yet — GEFS store needs more inits overlapping frame origins")
        return 0

    # temporal split on whatever years are present (earliest=train, latest=test)
    years = sorted(yr.unique().tolist())
    if len(years) < 2:
        print("need >=2 origin years in the matched set for a temporal split; "
              f"have {years}. Download more inits across years.")
        return 0
    split = years[len(years) // 2]
    tr, te = merged[yr < split], merged[yr >= split]
    print(f"split: train origin<{split} (n={len(tr)}), test origin>={split} (n={len(te)})\n", flush=True)

    a = _evaluate(tr, te, base_feats, "A antecedent only")
    b = _evaluate(tr, te, base_feats + covariates, "B + GEFS forecast (P0)")
    if a and b:
        print(f"\nREAL P0 lift on identical rows: ROC {a['roc']:.3f} -> {b['roc']:.3f} "
              f"(+{b['roc']-a['roc']:.3f}), PR-AUC lift {a['lift']:.2f}x -> {b['lift']:.2f}x", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
