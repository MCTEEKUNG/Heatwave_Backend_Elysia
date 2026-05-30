"""Assemble ERA5 (+NDVI) -> data/processed/dataset_era5.parquet (forecasting-ready).

Schema mirrors the current dataset so src.features.make_forecasting_frame works
unchanged; adds ERA5/NDVI feature columns. Label mode is chosen in Phase 3.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from src.provinces import load_provinces
from src.era5_ingest import ingest_year
from src.climatology import compute_doy_percentiles
from src.labels import label_heatwave, label_absolute

RAW_ERA5 = "data/raw/era5"
DAILY_OUT = "data/processed/era5_daily.parquet"
DATASET_OUT = "data/processed/dataset_era5.parquet"


def attach_climatology_label(df, mode="absolute", abs_threshold=41.0,
                             value_col="heat_index_max", baseline=(1991, 2020)):
    """Add swbgt_max alias + p95/is_hot/heatwave per the chosen label mode."""
    out = df.copy()
    out["swbgt_max"] = out[value_col]  # climatology/feature code keys on swbgt_max
    if mode == "absolute":
        out = label_absolute(out, value_col=value_col, threshold=abs_threshold)
        out["p95"] = abs_threshold
        return out
    # relative p95 + >=2-day run
    thr = compute_doy_percentiles(out, value_col=value_col)
    out = label_heatwave(out, thr, value_col=value_col, min_run=2)
    return out


def main(mode="relative", abs_threshold=41.0):  # canonical label = relative (p95 + 2-day run)
    provinces = load_provinces()
    # v2 scope: 2016-2025 only (earlier years are daily + t2m-only, no humidity).
    years = sorted(y for y in (int(f.split("_")[-1].split(".")[0])
                   for f in os.listdir(RAW_ERA5) if f.startswith("era5_surface_"))
                   if y >= 2016)
    frames = [ingest_year(os.path.join(RAW_ERA5, f"era5_surface_{y}.nc"), provinces)
              for y in years]
    daily = pd.concat(frames, ignore_index=True)
    daily = daily.merge(provinces.rename(columns={"id": "province_id"})[
        ["province_id", "lat", "lon"]], on="province_id", how="left")
    os.makedirs("data/processed", exist_ok=True)
    daily.to_parquet(DAILY_OUT, index=False)  # input to scripts/profile_dataset.py

    # pandas 3.0 drops the groupby-key column from apply() results, so we use
    # concat-over-groups which preserves province_id in every sub-frame.
    labeled = pd.concat(
        [attach_climatology_label(g.sort_values("time"), mode=mode,
                                  abs_threshold=abs_threshold)
         for _, g in daily.groupby("province_id")],
        ignore_index=True)
    labeled.to_parquet(DATASET_OUT, index=False)
    print(f"dataset_era5 rows={len(labeled)} provinces={labeled['province_id'].nunique()} "
          f"heatwave_rate={labeled['heatwave'].mean():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
