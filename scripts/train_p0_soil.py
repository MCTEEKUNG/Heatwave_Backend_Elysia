"""Measure whether ANTECEDENT soil moisture lifts the model — clean A/B/C/D on
identical matched rows (no leakage, no oracle).

Soil moisture is the highest-evidence land-atmosphere coupling predictor
(Felsche 2023; Benson 2020). It is ANTECEDENT here (observed at <= origin), so it
is leakage-safe and complementary to the forecast covariate (P0). We compare, on
the SAME rows (GEFS-matched + soil-covered) and temporal split:
  A = antecedent base features
  B = base + antecedent soil moisture (sm_lag1, sm_mean_7d)
  C = base + forecast heat-index (the proven P0 covariate)
  D = base + forecast HI + antecedent soil moisture
ROC / PR-AUC-lift deltas are the honest answer to "does soil moisture help?".
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.heat_index import rh_from_specific_humidity, heat_index_c
from src.forecast_covariates import join_forecast_covariates

DATASET = "data/processed/dataset_era5.parquet"
GEFS = "data/processed/gefs_forecast_store.parquet"
SOIL = "data/processed/era5_soil_moisture.parquet"
SM_COV = ["sm_lag1", "sm_mean_7d"]


def add_antecedent_soil(frame: pd.DataFrame, soil: pd.DataFrame) -> pd.DataFrame:
    """Attach leakage-safe antecedent soil-moisture features (values strictly
    before origin) onto the frame by (province_id, origin_time)."""
    s = soil.copy()
    s["date"] = pd.to_datetime(s["date"]).dt.normalize()
    s = s.sort_values(["province_id", "date"]).reset_index(drop=True)
    s["sm_lag1"] = s.groupby("province_id")["soil_moisture"].shift(1)
    s["sm_mean_7d"] = s.groupby("province_id")["soil_moisture"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=7).mean())
    f = frame.copy()
    f["_d"] = pd.to_datetime(f["origin_time"]).dt.normalize()
    merged = f.merge(s[["province_id", "date"] + SM_COV],
                     left_on=["province_id", "_d"],
                     right_on=["province_id", "date"], how="left")
    return merged.drop(columns=["_d", "date"])


def _eval(tr, te, feats, label):
    if tr["y"].sum() == 0 or te["y"].sum() == 0:
        print(f"  {label}: insufficient positives", flush=True)
        return None
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    p = np.asarray(m.predict_proba(te[feats]))[:, 1]
    yte = te["y"].to_numpy()
    roc = roc_auc_score(yte, p)
    lift = average_precision_score(yte, p) / yte.mean()
    print(f"  {label:34s} ROC={roc:.3f} PR-AUC-lift={lift:.2f}x", flush=True)
    return dict(roc=roc, lift=lift)


def prepare():
    """Return (merged rows with forecast+soil coverage, base feats, fc covariates).
    Shared by main() and the robustness check so both use identical data prep."""
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    base = feature_columns(frame)

    gefs = pd.read_parquet(GEFS)
    merged = join_forecast_covariates(frame, gefs, cols=("fc_tmax", "fc_spfh"),
                                      require_coverage=True)
    merged["fc_rh"] = rh_from_specific_humidity(merged["fc_spfh"], merged["fc_tmax"])
    merged["fc_heat_index"] = heat_index_c(merged["fc_tmax"], merged["fc_rh"])
    merged = merged.dropna(subset=["fc_heat_index"])
    fc_cov = ["fc_tmax", "fc_rh", "fc_heat_index"]

    soil = pd.read_parquet(SOIL)
    merged = add_antecedent_soil(merged, soil)
    merged = merged.dropna(subset=SM_COV)  # identical soil-covered rows for all models
    return merged, base, fc_cov


def main():
    merged, base, fc_cov = prepare()
    print(f"rows (GEFS-matched + soil-covered)={len(merged)} "
          f"provinces={merged['province_id'].nunique()} pos_rate={merged['y'].mean():.3f}",
          flush=True)
    if len(merged) == 0:
        print("no rows with both forecast + soil coverage")
        return 0

    yr = pd.to_datetime(merged["origin_time"]).dt.year
    years = sorted(yr.unique().tolist())
    if len(years) < 2:
        print(f"need >=2 origin years, have {years}")
        return 0
    split = years[len(years) // 2]
    tr, te = merged[yr < split], merged[yr >= split]
    print(f"split: train origin<{split} (n={len(tr)}), test>= (n={len(te)}, "
          f"pos={int(te['y'].sum())})\n", flush=True)

    A = _eval(tr, te, base, "A antecedent base")
    B = _eval(tr, te, base + SM_COV, "B + antecedent soil moisture")
    C = _eval(tr, te, base + fc_cov, "C + forecast heat-index (P0)")
    D = _eval(tr, te, base + fc_cov + SM_COV, "D + forecast HI + soil")

    print("\nVERDICT (ROC delta on identical rows):", flush=True)
    if A and B:
        print(f"  antecedent soil over base : {A['roc']:.3f} -> {B['roc']:.3f} "
              f"({B['roc'] - A['roc']:+.3f})", flush=True)
    if C and D:
        print(f"  soil on top of P0         : {C['roc']:.3f} -> {D['roc']:.3f} "
              f"({D['roc'] - C['roc']:+.3f})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
