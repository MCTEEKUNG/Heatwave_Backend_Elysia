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

    _plot_coverage_heatmap(df)
    return df


def _plot_coverage_heatmap(df: pd.DataFrame) -> None:
    """Traffic-light heatmap: years × variables, color = completeness %."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
    except ImportError:
        print("  [plot] matplotlib not installed — skipping coverage heatmap")
        return

    plots_dir = OUTPUT_DIR / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    nan_cols = [c for c in df.columns if c.startswith("nan_pct_")]
    variables = [c.replace("nan_pct_", "") for c in nan_cols]

    if df.empty or not nan_cols:
        return

    # Build matrix: completeness per (year, variable) = 100 - nan_pct
    df_plot = df[df["file_exists"]].copy()
    if df_plot.empty:
        return

    years = df_plot["year"].tolist()
    matrix = np.array(
        [(100.0 - df_plot[c].fillna(100).values) for c in nan_cols]
    ).T  # shape: (n_years, n_vars)

    # Also include overall time completeness as first column
    if "completeness_pct" in df_plot.columns:
        comp = df_plot["completeness_pct"].fillna(0).values.reshape(-1, 1)
        matrix = np.hstack([comp, matrix])
        variables = ["time_coverage"] + variables

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "traffic", [(0, "#d73027"), (0.7, "#fee08b"), (0.9, "#1a9850"), (1, "#1a9850")]
    )

    fig, ax = plt.subplots(figsize=(max(8, len(variables) * 1.2), max(4, len(years) * 0.4 + 1)))
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(variables)))
    ax.set_xticklabels(variables, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels(years, fontsize=8)
    ax.set_title("Data Coverage (% complete)\n🟢 ≥90%  🟡 70–90%  🔴 <70%", fontsize=10)

    for i in range(len(years)):
        for j in range(len(variables)):
            val = matrix[i, j]
            txt = f"{val:.0f}"
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=7, color="black" if val > 40 else "white")

    plt.colorbar(im, ax=ax, label="Completeness %", shrink=0.8)
    plt.tight_layout()
    out = plots_dir / "coverage_heatmap.png"
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  [plot] Saved: {out}")


if __name__ == "__main__":
    run()
