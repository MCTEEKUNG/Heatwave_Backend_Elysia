# -*- coding: utf-8 -*-
"""
eda/01_data_coverage.py
Check per-year file presence, time-dimension completeness, and NaN counts.
Run from Heatwave-AI-TRAIN/: python eda/01_data_coverage.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path("experiments/eda")
ERA5_SURFACE_VARS = ["t2m", "d2m", "sp", "u10", "v10"]


def _detect_time_dim(ds: xr.Dataset) -> str:
    for name in ("valid_time", "time"):
        if name in ds.dims or name in ds.coords:
            return name
    return None


def run(config_path: str = "config/config.yaml") -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    years = cfg["data"]["years"]
    surface_prefix = cfg["data"]["surface_prefix"]

    rows = []
    gaps_report = []

    for year in years:
        surf_path = os.path.join(raw_dir, f"{surface_prefix}{year}.nc")
        row = {"year": year, "file_exists": False}

        if not os.path.isfile(surf_path):
            rows.append(row)
            continue

        row["file_exists"] = True
        row["file_size_mb"] = round(os.path.getsize(surf_path) / 1e6, 2)

        try:
            ds = xr.open_dataset(surf_path, engine="netcdf4")
            time_dim = _detect_time_dim(ds)

            if time_dim:
                times = pd.to_datetime(ds[time_dim].values)
                n = len(times)
                row["timesteps"] = n

                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                days = 366 if is_leap else 365
                # detect hourly vs daily based on steps per year
                if n > days * 2:
                    expected = days * 24
                    row["granularity"] = "hourly"
                else:
                    expected = days
                    row["granularity"] = "daily"

                row["completeness_pct"] = round(100 * n / expected, 1)

                if n > 1:
                    diffs = pd.Series(times).diff().dt.total_seconds().dropna()
                    expected_step = 3600 if row["granularity"] == "hourly" else 86400
                    gaps = int((diffs > expected_step * 1.5).sum())
                    row["time_gaps"] = gaps
                    if gaps:
                        gaps_report.append({"year": year, "gaps": gaps})
            else:
                row["timesteps"] = None
                row["granularity"] = "unknown"

            for var in ERA5_SURFACE_VARS:
                if var in ds.data_vars:
                    arr = ds[var].values
                    nan_count = int(np.isnan(arr).sum())
                    row[f"nan_pct_{var}"] = round(100 * nan_count / arr.size, 3)
                else:
                    row[f"missing_{var}"] = True

            ds.close()
        except Exception as exc:
            row["error"] = str(exc)

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / "coverage_matrix.csv", index=False)

    with open(OUTPUT_DIR / "gaps_report.json", "w") as f:
        json.dump(gaps_report, f, indent=2)

    summary_cols = ["year", "file_exists", "granularity", "timesteps",
                    "completeness_pct", "time_gaps", "file_size_mb"]
    print("\n=== Data Coverage ===")
    print(df[[c for c in summary_cols if c in df.columns]].to_string(index=False))
    print(f"\nFiles missing: {(~df['file_exists']).sum()}")
    print(f"Years with time gaps: {len(gaps_report)}")
    print(f"Saved: {OUTPUT_DIR}/coverage_matrix.csv")
    return df


if __name__ == "__main__":
    run()
