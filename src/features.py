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

# Core columns (the heat signal): full rolling stats + p95 anomaly.
_CORE_COLS = ["swbgt_max", "temperature_2m_max", "relative_humidity_2m_mean"]
_CORE_WINDOWS = (3, 7, 14, 30)

# Research-backed driver columns (land-surface / synoptic state). A lighter
# feature set (lag-1 + 7/30-day means) adds signal without exploding dimensions.
_DRIVER_COLS = [
    "soil_moisture_0_to_7cm_mean", "soil_moisture_7_to_28cm_mean",
    "soil_moisture_28_to_100cm_mean",  # root-zone (slow, lagged control)
    "soil_temperature_0_to_7cm_mean", "precipitation_sum",
    "et0_fao_evapotranspiration", "surface_pressure_mean",
    "shortwave_radiation_sum", "wind_speed_10m_max",
]
_DRIVER_WINDOWS = (7, 30)

# Columns that encode the label / target-day truth -- must never appear raw as features.
LEAKY_COLS = frozenset(
    ["swbgt_max", "temperature_2m_max", "relative_humidity_2m_mean",
     "is_hot", "heatwave"]
)

# Monthly external features that may be missing without dropping a row (LightGBM
# tolerates NaN). Keeps the pipeline robust to date-range mismatch across sources.
_MISSING_OK_FEATURES = frozenset(["hpa500", "ndvi", "nino34"])


def _antecedent_features(d: pd.DataFrame) -> pd.DataFrame:
    """Rolling mean/max + climatology anomaly of PAST-only values.

    Every stat operates on ``.shift(1)`` so day t's own value is never part of
    its own feature (no same-day leakage).
    """
    feats = {}
    for col in _CORE_COLS:
        if col not in d.columns:
            continue
        past = d[col].shift(1)  # values strictly before day t
        for w in _CORE_WINDOWS:
            roll = past.rolling(window=w, min_periods=w)
            feats[f"{col}_mean_{w}d"] = roll.mean()
            feats[f"{col}_max_{w}d"] = roll.max()
        if "p95" in d.columns:
            feats[f"{col}_anom_lag1"] = past - d["p95"]

    for col in _DRIVER_COLS:
        if col not in d.columns:
            continue
        past = d[col].shift(1)
        feats[f"{col}_lag1"] = past
        for w in _DRIVER_WINDOWS:
            feats[f"{col}_mean_{w}d"] = past.rolling(window=w, min_periods=w).mean()

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

    # --- teleconnection + vegetation (already lagged to the previous month) ---
    if "nino34" in d.columns:
        ante["nino34"] = d["nino34"].to_numpy()
    if "ndvi" in d.columns:
        ante["ndvi"] = d["ndvi"].to_numpy()
    if "hpa500" in d.columns:  # ERA5 500 hPa geopotential height (circulation)
        ante["hpa500"] = d["hpa500"].to_numpy()

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

    # Drop only genuinely-unusable rows: NaN target, or NaN in an antecedent
    # feature (the first ~30 days of each series have no rolling history). Monthly
    # EXTERNAL features (geopotential / NDVI / ENSO) are allowed to be missing —
    # LightGBM handles NaN natively, so a source whose date range doesn't fully
    # cover the dataset degrades gracefully instead of silently dropping rows.
    required = ["y"] + [c for c in feature_cols if c not in _MISSING_OK_FEATURES]
    out = out.dropna(subset=required).reset_index(drop=True)
    out["y"] = out["y"].astype(int)
    return out


def feature_columns(frame: pd.DataFrame) -> list:
    """Return the model-input feature columns (excludes target/bookkeeping)."""
    drop = {"y", "origin_time", "target_time"}
    return [c for c in frame.columns if c not in drop]
