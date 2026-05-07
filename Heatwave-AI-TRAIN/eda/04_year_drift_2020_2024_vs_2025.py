# -*- coding: utf-8 -*-
"""
eda/04_year_drift_2020_2024_vs_2025.py
Validate that 2025 is a plausible held-out year — not out-of-distribution.
Uses Population Stability Index (PSI) and 2-sample KS test.

PSI thresholds: < 0.1 stable | 0.1–0.25 minor shift | > 0.25 significant shift
Run from Heatwave-AI-TRAIN/: python eda/04_year_drift_2020_2024_vs_2025.py
"""
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from pathlib import Path
from scipy.stats import ks_2samp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path("experiments/eda")
KELVIN_OFFSET = 273.15
TRAIN_YEARS = list(range(2020, 2025))
VAL_YEAR = 2025


def _detect_time_dim(ds):
    for n in ("valid_time", "time"):
        if n in ds.dims or n in ds.coords:
            return n
    return None


def _compute_wbgt(t_c, rh):
    e = (rh / 100.0) * 6.105 * np.exp(17.27 * t_c / (237.7 + t_c))
    return 0.567 * t_c + 0.393 * e + 3.94


def _load_year_flat(raw_dir: str, prefix: str, year: int) -> pd.DataFrame:
    """Load one year, return flattened DataFrame with engineered features."""
    path = os.path.join(raw_dir, f"{prefix}{year}.nc")
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        ds = xr.open_dataset(path, engine="netcdf4")
        time_dim = _detect_time_dim(ds)
        df = ds[["t2m", "d2m"]].to_dataframe().reset_index()
        ds.close()

        if time_dim and time_dim in df.columns:
            df = df.rename(columns={time_dim: "time"})

        # Convert K → °C if needed
        for col in ("t2m", "d2m"):
            if col in df.columns and df[col].median() > 200:
                df[f"{col}_c"] = df[col] - KELVIN_OFFSET
            elif col in df.columns:
                df[f"{col}_c"] = df[col]

        if "t2m_c" in df.columns and "d2m_c" in df.columns:
            rh = 100 * np.exp(
                17.625 * df["d2m_c"] / (243.04 + df["d2m_c"])
                - 17.625 * df["t2m_c"] / (243.04 + df["t2m_c"])
            )
            df["rh"] = np.clip(rh, 0, 100)
            df["wbgt"] = _compute_wbgt(df["t2m_c"].values, df["rh"].values)
            # Rothfusz HI
            T_f = df["t2m_c"] * 9 / 5 + 32
            RH  = df["rh"]
            HI_f = (-42.379 + 2.04901523*T_f + 10.14333127*RH
                    - 0.22475541*T_f*RH - 0.00683783*T_f**2
                    - 0.05481717*RH**2 + 0.00122874*T_f**2*RH
                    + 0.00085282*T_f*RH**2 - 0.00000199*T_f**2*RH**2)
            df["heat_index"] = np.where(
                (df["t2m_c"] >= 26.7) & (RH >= 40),
                (HI_f - 32) * 5 / 9,
                df["t2m_c"],
            )

        df["year"] = year
        return df[["year"] + [c for c in ("t2m_c", "d2m_c", "rh", "wbgt", "heat_index") if c in df.columns]]
    except Exception as exc:
        print(f"  {year}: ERROR — {exc}")
        return pd.DataFrame()


def _psi(train_arr, val_arr, n_bins=10):
    """Population Stability Index between two 1-D arrays."""
    eps = 1e-6
    combined = np.concatenate([train_arr, val_arr])
    bins = np.percentile(combined, np.linspace(0, 100, n_bins + 1))
    bins = np.unique(bins)
    if len(bins) < 2:
        return 0.0

    t_counts, _ = np.histogram(train_arr, bins=bins)
    v_counts, _ = np.histogram(val_arr,   bins=bins)

    t_pct = (t_counts + eps) / (len(train_arr) + eps)
    v_pct = (v_counts + eps) / (len(val_arr)   + eps)

    return float(np.sum((v_pct - t_pct) * np.log(v_pct / t_pct)))


def run(config_path: str = "config/config.yaml") -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    prefix  = cfg["data"]["surface_prefix"]
    train_years = cfg["split"].get("train_years", TRAIN_YEARS)
    val_years   = cfg["split"].get("val_years",   [VAL_YEAR])

    print(f"Loading train years: {train_years}")
    train_frames = [_load_year_flat(raw_dir, prefix, y) for y in train_years]
    train_df = pd.concat([f for f in train_frames if len(f)], ignore_index=True)

    print(f"Loading val years:   {val_years}")
    val_frames = [_load_year_flat(raw_dir, prefix, y) for y in val_years]
    val_df = pd.concat([f for f in val_frames if len(f)], ignore_index=True)

    if train_df.empty or val_df.empty:
        print("Insufficient data — check file paths.")
        return pd.DataFrame()

    features = [c for c in ("t2m_c", "rh", "wbgt", "heat_index") if c in train_df.columns]
    results = []
    for feat in features:
        tr = train_df[feat].dropna().values
        vl = val_df[feat].dropna().values
        psi_val = _psi(tr, vl)
        ks_stat, ks_p = ks_2samp(tr, vl)
        flag = "STABLE" if psi_val < 0.1 else ("MINOR_SHIFT" if psi_val < 0.25 else "SIGNIFICANT_SHIFT")
        results.append({
            "feature": feat,
            "train_mean": round(float(tr.mean()), 3),
            "val_mean":   round(float(vl.mean()), 3),
            "mean_diff":  round(float(vl.mean() - tr.mean()), 3),
            "psi":        round(psi_val, 4),
            "ks_stat":    round(float(ks_stat), 4),
            "ks_p":       round(float(ks_p), 6),
            "status":     flag,
        })

    df_result = pd.DataFrame(results)
    df_result.to_csv(OUTPUT_DIR / "drift_report.csv", index=False)
    with open(OUTPUT_DIR / "drift_report.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n=== Distribution Drift (2025 vs 2020-2024) ===")
    print(df_result.to_string(index=False))
    print(f"\nPSI > 0.25 (significant shift): "
          f"{(df_result['psi'] > 0.25).sum()} features")
    print(f"Saved: {OUTPUT_DIR}/drift_report.csv")
    return df_result


if __name__ == "__main__":
    run()
