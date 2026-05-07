# -*- coding: utf-8 -*-
"""
eda/06_spatial_maps.py
Per-year spatial maps over Thailand: mean temperature, WBGT, and heatwave-day count.
Requires matplotlib and cartopy (optional — falls back to CSV if not installed).
Run from Heatwave-AI-TRAIN/: python eda/06_spatial_maps.py
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

OUTPUT_DIR = Path("experiments/eda/maps")
KELVIN_OFFSET = 273.15
WBGT_THRESHOLD = 32.0
WBGT_MIN_DAYS  = 2


def _detect_time_dim(ds):
    for n in ("valid_time", "time"):
        if n in ds.dims or n in ds.coords:
            return n
    return None


def _compute_wbgt(t_c, rh):
    e = (rh / 100.0) * 6.105 * np.exp(17.27 * t_c / (237.7 + t_c))
    return 0.567 * t_c + 0.393 * e + 3.94


def _year_spatial(ds: xr.Dataset, year: int) -> pd.DataFrame:
    """Compute per-cell annual stats: mean T, WBGT, heatwave days."""
    time_dim = _detect_time_dim(ds)
    if time_dim is None:
        return pd.DataFrame()

    rename = {k: v for k, v in {"lat": "latitude", "lon": "longitude",
                                  "y": "latitude", "x": "longitude"}.items()
              if k in ds.dims}
    if rename:
        ds = ds.rename(rename)

    results = []

    lat_vals = ds["latitude"].values if "latitude" in ds.coords else None
    lon_vals = ds["longitude"].values if "longitude" in ds.coords else None
    if lat_vals is None or lon_vals is None:
        return pd.DataFrame()

    # Work in xarray for efficiency — compute daily max T, mean WBGT
    t2m = ds["t2m"]
    d2m = ds["d2m"] if "d2m" in ds.data_vars else None

    if t2m.mean().values > 200:
        t2m = t2m - KELVIN_OFFSET
    if d2m is not None and d2m.mean().values > 200:
        d2m = d2m - KELVIN_OFFSET

    # Daily max temperature per cell
    t_daily_max = t2m.resample({time_dim: "1D"}).max()

    # WBGT if d2m available
    hw_days = None
    if d2m is not None:
        t_daily_mean = t2m.resample({time_dim: "1D"}).mean()
        d_daily_mean = d2m.resample({time_dim: "1D"}).mean()
        t_np = t_daily_mean.values
        d_np = d_daily_mean.values
        rh = 100 * np.exp(17.625 * d_np / (243.04 + d_np) - 17.625 * t_np / (243.04 + t_np))
        rh = np.clip(rh, 0, 100)
        wbgt = _compute_wbgt(t_np, rh)  # shape: (days, lat, lon)

        # Heatwave days: WBGT >= threshold
        hot = (wbgt >= WBGT_THRESHOLD).astype(int)
        # Simple count (not consecutive-run filtered, for map visualization)
        hw_days = hot.sum(axis=0)  # (lat, lon)

    t_np_max = t_daily_max.values  # (days, lat, lon)
    t_mean = t_np_max.mean(axis=0)
    t_p99  = np.percentile(t_np_max, 99, axis=0)

    for i, lat in enumerate(lat_vals):
        for j, lon in enumerate(lon_vals):
            row = {
                "year": year,
                "latitude":  round(float(lat), 2),
                "longitude": round(float(lon), 2),
                "t_mean_c":  round(float(t_mean[i, j]), 2),
                "t_p99_c":   round(float(t_p99[i, j]),  2),
            }
            if hw_days is not None:
                row["hw_days_wbgt32"] = int(hw_days[i, j])
            results.append(row)

    return pd.DataFrame(results)


def _try_plot(df_all: pd.DataFrame) -> None:
    """Attempt to plot maps; skip gracefully if matplotlib/cartopy unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm

        years = sorted(df_all["year"].unique())
        fig, axes = plt.subplots(
            len(years), 2, figsize=(10, 3 * len(years)),
            constrained_layout=True
        )
        if len(years) == 1:
            axes = [axes]

        for row_idx, year in enumerate(years):
            yr = df_all[df_all["year"] == year]
            pivot_t = yr.pivot(index="latitude", columns="longitude", values="t_mean_c")
            pivot_hw = yr.pivot(index="latitude", columns="longitude", values="hw_days_wbgt32") \
                if "hw_days_wbgt32" in yr.columns else None

            ax0 = axes[row_idx][0]
            im0 = ax0.pcolormesh(
                pivot_t.columns, pivot_t.index, pivot_t.values,
                cmap="RdYlBu_r", vmin=25, vmax=40,
            )
            plt.colorbar(im0, ax=ax0, label="°C")
            ax0.set_title(f"{year} — Mean Tmax (°C)")
            ax0.set_xlabel("Longitude"); ax0.set_ylabel("Latitude")

            ax1 = axes[row_idx][1]
            if pivot_hw is not None:
                im1 = ax1.pcolormesh(
                    pivot_hw.columns, pivot_hw.index, pivot_hw.values,
                    cmap="Reds", vmin=0,
                )
                plt.colorbar(im1, ax=ax1, label="days")
                ax1.set_title(f"{year} — HW Days (WBGT≥32°C)")
                ax1.set_xlabel("Longitude"); ax1.set_ylabel("Latitude")
            else:
                ax1.axis("off")

        out_path = OUTPUT_DIR / "spatial_maps.png"
        plt.savefig(out_path, dpi=120)
        plt.close()
        print(f"Saved plot: {out_path}")
    except ImportError:
        print("matplotlib not installed — skipping plots (CSV output still saved).")


def run(config_path: str = "config/config.yaml") -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    prefix  = cfg["data"]["surface_prefix"]
    train_years = cfg["split"].get("train_years", list(range(2020, 2025)))
    val_years   = cfg["split"].get("val_years",   [2025])
    map_years = sorted(set(train_years) | set(val_years))

    all_frames = []
    for year in map_years:
        path = os.path.join(raw_dir, f"{prefix}{year}.nc")
        if not os.path.isfile(path):
            print(f"  {year}: file missing — skipped")
            continue
        print(f"  processing {year} ...")
        try:
            with xr.open_dataset(path, engine="netcdf4") as ds:
                df_yr = _year_spatial(ds, year)
            if len(df_yr):
                all_frames.append(df_yr)
        except Exception as exc:
            print(f"  {year}: ERROR — {exc}")

    if not all_frames:
        print("No data loaded.")
        return pd.DataFrame()

    df_all = pd.concat(all_frames, ignore_index=True)
    csv_path = OUTPUT_DIR.parent / "spatial_summary.csv"
    df_all.to_csv(csv_path, index=False)
    print(f"\nSaved spatial summary: {csv_path}")

    _try_plot(df_all)
    return df_all


if __name__ == "__main__":
    run()
