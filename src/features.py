# src/features.py
"""Build a *forecasting* feature frame from a per-province daily dataframe.

THE #1 RULE: features must NOT contain the target day's swbgt/Tmax/RH or anything
that defines the label (`is_hot`, `heatwave`). Every antecedent feature is built
with ``.shift(1).rolling(...)`` so day t's OWN value is excluded -- features depend
only on data known at <= t. The target ``y`` for horizon k is ``heatwave.shift(-k)``,
i.e. the heatwave flag k days in the FUTURE.

Input row schema (from pipeline.build_dataset.build_for_provinces):
    province_id, time, swbgt_max, p95, is_hot, heatwave,
    temperature_2m_max, relative_humidity_2m_mean
"""
import numpy as np
import pandas as pd

# Source columns we derive antecedent/anomaly features from.
_VALUE_COLS = ["swbgt_max", "heat_index_max", "t2m_c_max", "rh_mean",
               "wind_speed_max", "sp_mean",
               "temperature_2m_max", "relative_humidity_2m_mean"]
_ROLL_WINDOWS = (3, 7, 14, 30)

# Columns that encode the label / target-day truth -- must never appear raw as features.
LEAKY_COLS = frozenset(
    ["swbgt_max", "heat_index_max", "t2m_c_max", "t2m_c_mean", "rh_mean", "rh_min",
     "wind_speed_max", "sp_mean", "temperature_2m_max", "relative_humidity_2m_mean",
     "is_hot", "heatwave"]
)


def _antecedent_features(d: pd.DataFrame) -> pd.DataFrame:
    """Rolling mean/max + climatology anomaly of past-only values.

    All rolling stats operate on ``.shift(1)`` so the current day's value is
    never part of its own feature (no same-day leakage).
    """
    feats = {}
    for col in _VALUE_COLS:
        if col not in d.columns:
            continue
        past = d[col].shift(1)  # values strictly before day t
        for w in _ROLL_WINDOWS:
            roll = past.rolling(window=w, min_periods=w)
            feats[f"{col}_mean_{w}d"] = roll.mean()
            feats[f"{col}_max_{w}d"] = roll.max()
        # anomaly of yesterday's value vs the static per-doy p95 climatology
        if "p95" in d.columns:
            feats[f"{col}_anom_lag1"] = past - d["p95"]

    return pd.DataFrame(feats, index=d.index)


def make_forecasting_frame(df_one_province: pd.DataFrame,
                           horizons=range(1, 8)) -> pd.DataFrame:
    """Build the stacked (one row per origin-day x horizon) forecasting frame.

    For each origin day t and horizon k, emit a row whose features are built
    ONLY from data at <= t, plus a ``horizon_k`` column and target
    ``y = heatwave(t + k)``. Rows with any NaN feature or NaN target are dropped.
    """
    d = df_one_province.copy()
    d["time"] = pd.to_datetime(d["time"])
    d = d.sort_values("time").reset_index(drop=True)

    # --- temporal-only antecedent features (computed once on the daily frame) ---
    ante = _antecedent_features(d)

    # --- calendar (seasonal) features, known for any date ---
    doy = d["time"].dt.dayofyear.to_numpy()
    ante["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    ante["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)

    # --- static per-province features (climatology / geography) ---
    if "p95" in d.columns:
        ante["p95"] = d["p95"].to_numpy()
    for static_col in ("lat", "lon", "province_id"):
        if static_col in d.columns:
            ante[static_col] = d[static_col].to_numpy()

    for ndvi_col in ("ndvi_lag1", "ndvi_lag2"):  # NOT raw "ndvi" (intra-month leak)
        if ndvi_col in d.columns:
            ante[ndvi_col] = d[ndvi_col].to_numpy()

    feature_cols = list(ante.columns)

    # --- stack one block per horizon, each with its own future target ---
    blocks = []
    for k in horizons:
        block = ante.copy()
        block["horizon_k"] = k
        block["y"] = d["heatwave"].shift(-k).to_numpy()  # heatwave k days ahead
        block["origin_time"] = d["time"].to_numpy()
        block["target_time"] = (d["time"] + pd.to_timedelta(k, unit="D")).to_numpy()
        blocks.append(block)

    out = pd.concat(blocks, ignore_index=True)

    # drop rows with NaN target or NaN in any feature column
    out = out.dropna(subset=["y"] + feature_cols).reset_index(drop=True)
    out["y"] = out["y"].astype(int)
    return out


def feature_columns(frame: pd.DataFrame) -> list:
    """Return the model-input feature columns (excludes target/bookkeeping)."""
    drop = {"y", "origin_time", "target_time"}
    return [c for c in frame.columns if c not in drop]
