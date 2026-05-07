# -*- coding: utf-8 -*-
"""
eda/02_distribution_summary.py
Per-variable, per-year summary statistics and range/unit sanity checks.
Run from Heatwave-AI-TRAIN/: python eda/02_distribution_summary.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path("experiments/eda")
KELVIN_OFFSET = 273.15

# Sanity bounds after converting to °C / physical units
SANITY_BOUNDS = {
    "t2m_c":   (-10.0, 55.0),
    "d2m_c":   (-20.0, 40.0),
    "rh":      (0.0,  105.0),   # slight tolerance for RH clipping
    "sp":      (80000, 110000), # Pa
    "u10":     (-50.0, 50.0),
    "v10":     (-50.0, 50.0),
}


def _detect_time_dim(ds):
    for n in ("valid_time", "time"):
        if n in ds.dims or n in ds.coords:
            return n
    return None


def _year_stats(ds: xr.Dataset, year: int) -> dict:
    row = {"year": year}
    time_dim = _detect_time_dim(ds)
    if time_dim:
        times = pd.to_datetime(ds[time_dim].values)
        row["n_timesteps"] = len(times)

    for var in ("t2m", "d2m", "sp", "u10", "v10"):
        if var not in ds.data_vars:
            continue
        arr = ds[var].values.ravel().astype(float)
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            continue

        # Convert temp to Celsius for sanity check
        if var in ("t2m", "d2m") and arr.mean() > 200:
            arr_c = arr - KELVIN_OFFSET
            col = f"{var}_c"
        else:
            arr_c = arr
            col = var

        row[f"{col}_mean"]  = round(float(arr_c.mean()), 3)
        row[f"{col}_std"]   = round(float(arr_c.std()), 3)
        row[f"{col}_min"]   = round(float(arr_c.min()), 3)
        row[f"{col}_p5"]    = round(float(np.percentile(arr_c, 5)), 3)
        row[f"{col}_p50"]   = round(float(np.percentile(arr_c, 50)), 3)
        row[f"{col}_p95"]   = round(float(np.percentile(arr_c, 95)), 3)
        row[f"{col}_max"]   = round(float(arr_c.max()), 3)

        # Sanity check
        lo, hi = SANITY_BOUNDS.get(col, (-1e9, 1e9))
        out_of_range = int(((arr_c < lo) | (arr_c > hi)).sum())
        if out_of_range:
            row[f"{col}_out_of_range"] = out_of_range

    # Compute RH from t2m and d2m
    if "t2m" in ds.data_vars and "d2m" in ds.data_vars:
        t = ds["t2m"].values.ravel().astype(float)
        td = ds["d2m"].values.ravel().astype(float)
        mask = ~(np.isnan(t) | np.isnan(td))
        t, td = t[mask], td[mask]
        if t.mean() > 200:
            t -= KELVIN_OFFSET
            td -= KELVIN_OFFSET
        rh = 100 * np.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))
        rh = np.clip(rh, 0, 100)
        row["rh_mean"] = round(float(rh.mean()), 2)
        row["rh_p5"]   = round(float(np.percentile(rh, 5)), 2)
        row["rh_p95"]  = round(float(np.percentile(rh, 95)), 2)
        row["rh_max"]  = round(float(rh.max()), 2)
        over100 = int((rh > 100).sum())
        if over100:
            row["rh_over100"] = over100

    return row


def run(config_path: str = "config/config.yaml") -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    years   = cfg["data"]["years"]
    prefix  = cfg["data"]["surface_prefix"]

    all_rows = []
    for year in years:
        path = os.path.join(raw_dir, f"{prefix}{year}.nc")
        if not os.path.isfile(path):
            all_rows.append({"year": year, "status": "missing"})
            continue
        try:
            with xr.open_dataset(path, engine="netcdf4") as ds:
                row = _year_stats(ds, year)
        except Exception as exc:
            row = {"year": year, "error": str(exc)}
        all_rows.append(row)
        print(f"  processed {year}")

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_DIR / "distribution_summary.csv", index=False)

    print("\n=== Distribution Summary (t2m_c mean, p95 by year) ===")
    show_cols = [c for c in ("year", "t2m_c_mean", "t2m_c_p95", "rh_mean", "rh_p95") if c in df.columns]
    if show_cols:
        print(df[show_cols].to_string(index=False))

    # Flag out-of-range columns
    oor_cols = [c for c in df.columns if c.endswith("_out_of_range")]
    if oor_cols:
        print("\n⚠️  Out-of-range values detected:")
        print(df[["year"] + oor_cols].dropna(subset=oor_cols, how="all").to_string(index=False))

    print(f"\nSaved: {OUTPUT_DIR}/distribution_summary.csv")
    return df


if __name__ == "__main__":
    run()
