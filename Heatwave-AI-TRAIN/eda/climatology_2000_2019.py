# -*- coding: utf-8 -*-
"""
eda/03_climatology_2000_2019.py
Compute per-cell, per-day-of-year temperature and WBGT percentiles from 2000-2019.
Output: experiments/eda/climatology_2000_2019.nc (used by label_ehf and by 05/06).

Method: load each year, aggregate to daily Tmax/Tmin/Tmean, compute WBGT,
accumulate across 20 years, then group by (lat, lon, DOY) for percentiles.
Run from Heatwave-AI-TRAIN/: python eda/03_climatology_2000_2019.py
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

OUTPUT_DIR  = Path("experiments/eda")
OUTPUT_FILE = OUTPUT_DIR / "climatology_2000_2019.nc"
KELVIN_OFFSET = 273.15


def _detect_time_dim(ds):
    for n in ("valid_time", "time"):
        if n in ds.dims or n in ds.coords:
            return n
    return None


def _compute_wbgt(t_c, rh):
    e = (rh / 100.0) * 6.105 * np.exp(17.27 * t_c / (237.7 + t_c))
    return 0.567 * t_c + 0.393 * e + 3.94


def _year_to_daily(ds: xr.Dataset, year: int) -> pd.DataFrame:
    """Extract daily Tmax, Tmin, Tmean, RH_mean, WBGT_mean from one year's dataset."""
    time_dim = _detect_time_dim(ds)
    if time_dim is None:
        return pd.DataFrame()

    # Rename spatial dims to standard names
    rename = {k: v for k, v in {"lat": "latitude", "lon": "longitude",
                                  "y": "latitude", "x": "longitude"}.items()
              if k in ds.dims}
    if rename:
        ds = ds.rename(rename)

    frames = []
    for var in ("t2m", "d2m"):
        if var not in ds.data_vars:
            continue
        da = ds[var]
        if da.mean().values > 200:
            da = da - KELVIN_OFFSET

        # Resample to daily
        daily_max  = da.resample({time_dim: "1D"}).max()
        daily_min  = da.resample({time_dim: "1D"}).min()
        daily_mean = da.resample({time_dim: "1D"}).mean()

        for agg, da_agg in (("max", daily_max), ("min", daily_min), ("mean", daily_mean)):
            df_tmp = da_agg.to_dataframe(name=f"{var}_{agg}").reset_index()
            # Rename time dim
            if time_dim in df_tmp.columns:
                df_tmp = df_tmp.rename(columns={time_dim: "time"})
            frames.append(df_tmp.set_index(["time", "latitude", "longitude"]))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, axis=1).reset_index()
    df["year"] = year
    df["doy"]  = pd.to_datetime(df["time"]).dt.dayofyear

    # Relative humidity from daily mean T and Td
    if "t2m_mean" in df.columns and "d2m_mean" in df.columns:
        t = df["t2m_mean"].values
        td = df["d2m_mean"].values
        rh = 100 * np.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))
        df["rh_mean"] = np.clip(rh, 0, 100)
        df["wbgt_mean"] = _compute_wbgt(t, df["rh_mean"].values)

    return df


def run(config_path: str = "config/config.yaml") -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    prefix  = cfg["data"]["surface_prefix"]
    clim_years = cfg["split"].get(
        "climatology_years",
        list(range(2000, 2020)),
    )

    print(f"Computing climatology for {len(clim_years)} years: {min(clim_years)}–{max(clim_years)}")
    daily_frames = []

    for year in clim_years:
        path = os.path.join(raw_dir, f"{prefix}{year}.nc")
        if not os.path.isfile(path):
            print(f"  {year}: file missing — skipped")
            continue
        try:
            with xr.open_dataset(path, engine="netcdf4") as ds:
                df_yr = _year_to_daily(ds, year)
            if len(df_yr):
                daily_frames.append(df_yr)
                print(f"  {year}: {len(df_yr):,} daily records loaded")
        except Exception as exc:
            print(f"  {year}: ERROR — {exc}")

    if not daily_frames:
        print("No data loaded. Check data paths.")
        return

    daily = pd.concat(daily_frames, ignore_index=True)
    print(f"\nTotal daily records: {len(daily):,}")

    percentiles = [90, 95]
    group_cols = ["latitude", "longitude", "doy"]
    agg_vars = {
        "t2m_max": "Tmax (°C)",
        "t2m_min": "Tmin (°C)",
        "wbgt_mean": "WBGT (°C)",
    }

    result_frames = []
    for var, label in agg_vars.items():
        if var not in daily.columns:
            continue
        for p in percentiles:
            col = f"{var.split('_')[0]}_{var.split('_')[1]}_p{p}" if "_" in var else f"{var}_p{p}"
            # standardize names: t2m_max_p90, t2m_min_p90, wbgt_mean_p90
            col = f"{var}_p{p}"
            pct = (
                daily.groupby(group_cols)[var]
                .quantile(p / 100)
                .rename(col)
                .reset_index()
            )
            result_frames.append(pct.set_index(group_cols))

    if not result_frames:
        print("No variables found to compute percentiles.")
        return

    clim_df = pd.concat(result_frames, axis=1).reset_index()
    print(f"\nClimatology shape: {clim_df.shape}")
    print(clim_df.head(3).to_string(index=False))

    # Save as NetCDF via xarray
    clim_xr = clim_df.set_index(["latitude", "longitude", "doy"]).to_xarray()
    clim_xr.attrs["description"] = (
        f"Per-cell, per-DOY temperature/WBGT percentiles from "
        f"{min(clim_years)}–{max(clim_years)}. Used by label_ehf()."
    )
    clim_xr.to_netcdf(OUTPUT_FILE)
    print(f"\nSaved climatology: {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
