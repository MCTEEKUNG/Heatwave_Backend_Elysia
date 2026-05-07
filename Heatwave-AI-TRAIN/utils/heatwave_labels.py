# -*- coding: utf-8 -*-
"""
utils/heatwave_labels.py
Pluggable heatwave labeling functions for Thailand (hot-humid climate).

Available methods (controlled by config.heatwave_label.method):
  wbgt          — WBGT >= 32°C for >= 2 days (ISO 7243, ABoM approx) — DEFAULT
  heat_index    — NWS Rothfusz HI >= 35°C for >= 2 days (legacy)
  ehf           — Excess Heat Factor, percentile-based (Nairn & Fawcett 2015)
  tropical_night— Tmin >= 26°C for >= 2 days (nighttime relief failure)

Why WBGT for Thailand
---------------------
Thailand's deadly heat combines high temperature AND high humidity (80–90% RH in May).
Pure temperature (or even NWS Heat Index, calibrated for US shade) undercounts Thai
heatwave exposure because sweat evaporates poorly in humid air. WBGT accounts for
both and is already used by Thailand's MoPH and Department of Labor Protection for
occupational heat-stress thresholds.

WBGT formula (ABoM outdoor approximation, Lemke & Kjellstrom 2012):
  e    = (RH/100) × 6.105 × exp(17.27·T / (237.7+T))   [vapor pressure, hPa]
  WBGT = 0.567·T + 0.393·e + 3.94                        [°C]

This approximation is for shaded outdoor conditions (no globe temperature). It is
conservative (slightly lower than full WBGT with solar load), making it suitable
as a lower-bound public-health threshold.
"""
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core physical formulas
# ---------------------------------------------------------------------------

def compute_vapor_pressure(t_c: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Actual vapor pressure (hPa) from dry-bulb temperature (°C) and RH (%)."""
    e_sat = 6.105 * np.exp(17.27 * t_c / (237.7 + t_c))
    return (rh / 100.0) * e_sat


def compute_wbgt(t_c: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """
    ABoM simplified WBGT (Lemke & Kjellstrom 2012, outdoor, no globe temperature).

    Input : t_c in °C, rh in %
    Output: WBGT in °C
    """
    e = compute_vapor_pressure(t_c, rh)
    return 0.567 * t_c + 0.393 * e + 3.94


# ---------------------------------------------------------------------------
# Shared consecutive-run filter
# ---------------------------------------------------------------------------

def _mark_consecutive_runs(s: pd.Series, min_len: int) -> pd.Series:
    """Label every time step that belongs to a run of >= min_len consecutive 1s."""
    groups = (s != s.shift()).cumsum()
    run_lens = s.groupby(groups).transform("sum")
    return ((s == 1) & (run_lens >= min_len)).astype(int)


def _apply_run_filter(
    df: pd.DataFrame,
    hot_col: str,
    min_days: int,
) -> pd.Series:
    """Apply consecutive-run filter, grouping by (latitude, longitude) if present."""
    group_cols = [c for c in ("latitude", "longitude") if c in df.columns]
    sort_cols  = [c for c in ("latitude", "longitude", "time") if c in df.columns]

    if sort_cols:
        df = df.sort_values(sort_cols)

    if group_cols:
        return df.groupby(group_cols)[hot_col].transform(
            lambda s: _mark_consecutive_runs(s, min_days)
        )
    return _mark_consecutive_runs(df[hot_col], min_days)


# ---------------------------------------------------------------------------
# Labeling functions
# ---------------------------------------------------------------------------

def label_wbgt(
    df: pd.DataFrame,
    threshold_c: float = 32.0,
    min_days: int = 2,
) -> pd.DataFrame:
    """
    WBGT >= threshold_c for >= min_days consecutive time steps.
    Default: 32°C / 2 days — matches OSHA/NIOSH 'extreme caution' and Thai MoPH advisory.
    Requires: t2m_c (°C), rh (%) columns.
    """
    df = df.copy()
    for col in ("t2m_c", "rh"):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Run preprocessing steps first.")

    if "wbgt" not in df.columns:
        df["wbgt"] = compute_wbgt(df["t2m_c"].values, df["rh"].values)
    df["_hot"] = (df["wbgt"] >= threshold_c).astype(int)
    df["is_heatwave"] = _apply_run_filter(df, "_hot", min_days)
    df = df.drop(columns=["_hot"])

    logger.info(
        "label_wbgt: WBGT >= %.1f°C, min_days=%d, positive_rate=%.2f%%",
        threshold_c, min_days, 100 * df["is_heatwave"].mean(),
    )
    return df


def label_heat_index(
    df: pd.DataFrame,
    threshold_c: float = 35.0,
    min_days: int = 2,
) -> pd.DataFrame:
    """
    NWS Rothfusz Heat Index >= threshold_c for >= min_days consecutive time steps.
    Preserved from the original pipeline for backward compatibility.
    Requires: heat_index column (computed by _compute_derived_features).
    """
    df = df.copy()
    if "heat_index" not in df.columns:
        raise ValueError("Column 'heat_index' not found. Run _compute_derived_features() first.")

    df["_hot"] = (df["heat_index"] >= threshold_c).astype(int)
    df["is_heatwave"] = _apply_run_filter(df, "_hot", min_days)
    df = df.drop(columns=["_hot"])

    logger.info(
        "label_heat_index: HI >= %.1f°C, min_days=%d, positive_rate=%.2f%%",
        threshold_c, min_days, 100 * df["is_heatwave"].mean(),
    )
    return df


def label_ehf(
    df: pd.DataFrame,
    climatology_path: str = "experiments/eda/climatology_2000_2019.nc",
    percentile: int = 95,
    min_days: int = 3,
) -> pd.DataFrame:
    """
    Excess Heat Factor (Nairn & Fawcett 2015) — location-aware, percentile-based.

    A heatwave occurs when the 3-day mean temperature exceeds the local T{percentile}
    climatology baseline (computed over 2000-2019). This captures 'unusual for here'
    heat rather than fixed absolute thresholds — the standard in heat-mortality literature
    (Perkins & Alexander 2013).

    Requires: t2m_c, latitude, longitude, time columns.
    Requires: climatology_2000_2019.nc from eda/03_climatology_2000_2019.py.
    """
    import os
    import xarray as xr

    df = df.copy()
    if "t2m_c" not in df.columns:
        raise ValueError("Column 't2m_c' not found.")
    if not os.path.isfile(climatology_path):
        raise FileNotFoundError(
            f"Climatology file not found: {climatology_path}\n"
            "Run: python -m eda.run_all  (or eda/03_climatology_2000_2019.py)"
        )

    clim_ds = xr.open_dataset(climatology_path)
    clim_df = clim_ds.to_dataframe().reset_index()
    clim_ds.close()

    pcol = f"t2m_max_p{percentile}"
    if pcol not in clim_df.columns:
        available = [c for c in clim_df.columns if c.startswith("t2m")]
        raise ValueError(
            f"Column '{pcol}' not in climatology file. Available: {available}"
        )

    group_cols = [c for c in ("latitude", "longitude") if c in df.columns]
    sort_cols  = [c for c in ("latitude", "longitude", "time") if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    df["doy"]   = pd.to_datetime(df["time"]).dt.dayofyear
    df["lat_r"] = df["latitude"].round(2) if "latitude" in df.columns else 0.0
    df["lon_r"] = df["longitude"].round(2) if "longitude" in df.columns else 0.0

    clim_df["lat_r"] = clim_df["latitude"].round(2)
    clim_df["lon_r"] = clim_df["longitude"].round(2)

    df = df.merge(
        clim_df[["lat_r", "lon_r", "doy", pcol]],
        on=["lat_r", "lon_r", "doy"],
        how="left",
    )

    if group_cols:
        df["t_3day"] = df.groupby(group_cols)["t2m_c"].transform(
            lambda s: s.rolling(3, min_periods=1).mean()
        )
    else:
        df["t_3day"] = df["t2m_c"].rolling(3, min_periods=1).mean()

    df["_hot"] = (df["t_3day"] > df[pcol]).fillna(0).astype(int)
    df["is_heatwave"] = _apply_run_filter(df, "_hot", min_days)
    df = df.drop(columns=["_hot", "doy", "lat_r", "lon_r", "t_3day", pcol], errors="ignore")

    logger.info(
        "label_ehf: p%d, min_days=%d, positive_rate=%.2f%%",
        percentile, min_days, 100 * df["is_heatwave"].mean(),
    )
    return df


def label_tropical_night(
    df: pd.DataFrame,
    tmin_c: float = 26.0,
    min_days: int = 2,
) -> pd.DataFrame:
    """
    Tropical-night definition: Tmin >= tmin_c for >= min_days consecutive nights.

    High nighttime temperature (no cooling relief) is a key driver of heat-related
    mortality in tropical cities — bodies cannot recover between hot days. The 26°C
    WMO/WHO threshold for 'tropical night' corresponds to the approximate critical
    limit for physiological nocturnal recovery.

    Requires: t2m_min (daily minimum) or t2m_c (used as proxy with a warning).
    """
    df = df.copy()
    tmin_col = "t2m_min" if "t2m_min" in df.columns else "t2m_c"

    if tmin_col == "t2m_c":
        logger.warning(
            "label_tropical_night: 't2m_min' not found; using 't2m_c' as proxy. "
            "Compute daily Tmin before calling this function for accurate results."
        )

    df["_hot"] = (df[tmin_col] >= tmin_c).astype(int)
    df["is_heatwave"] = _apply_run_filter(df, "_hot", min_days)
    df = df.drop(columns=["_hot"])

    logger.info(
        "label_tropical_night: Tmin >= %.1f°C, min_days=%d, positive_rate=%.2f%%",
        tmin_c, min_days, 100 * df["is_heatwave"].mean(),
    )
    return df


# ---------------------------------------------------------------------------
# Dispatcher (used by preprocessing.py)
# ---------------------------------------------------------------------------

def dispatch(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Route to the correct labeler based on config.heatwave_label.method.
    Returns df with 'is_heatwave' column added.
    """
    label_cfg = cfg.get("heatwave_label", {})
    method = label_cfg.get("method", "wbgt")

    if method == "wbgt":
        c = label_cfg.get("wbgt", {})
        return label_wbgt(
            df,
            threshold_c=c.get("threshold_c", 32.0),
            min_days=c.get("min_consecutive_days", 2),
        )

    if method == "heat_index":
        c = label_cfg.get("heat_index", {})
        return label_heat_index(
            df,
            threshold_c=c.get("threshold_c", 35.0),
            min_days=c.get("min_consecutive_days", 2),
        )

    if method == "ehf":
        c = label_cfg.get("ehf", {})
        return label_ehf(
            df,
            climatology_path=c.get("climatology_file", "experiments/eda/climatology_2000_2019.nc"),
            percentile=c.get("percentile", 95),
            min_days=c.get("min_consecutive_days", 3),
        )

    if method == "tropical_night":
        c = label_cfg.get("tropical_night", {})
        return label_tropical_night(
            df,
            tmin_c=c.get("tmin_c", 26.0),
            min_days=c.get("min_consecutive_days", 2),
        )

    raise ValueError(
        f"Unknown heatwave_label.method: {method!r}. "
        "Choose: wbgt | heat_index | ehf | tropical_night"
    )
