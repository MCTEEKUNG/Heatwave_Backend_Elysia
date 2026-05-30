"""Small real-data validation: build the Open-Meteo -> sWBGT -> label pipeline
for a few geographically-spread provinces over the full date range, then check
the frame train_model actually consumes and report POSITIVE counts per split &
horizon (a rare 2+day-run label can be near-empty in a single val/test year).

Run from repo root:
  .venv\\Scripts\\python.exe scripts\\validate_data_seam.py
"""
import os
import sys
import pandas as pd

# Allow running as `python scripts/validate_data_seam.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from pipeline.build_dataset import build_for_provinces
from pipeline.train import build_frames, train_model

START, END = "1991-01-01", "2025-12-31"


def main():
    provinces = load_provinces("data/provinces.csv")
    # 3 spread-out provinces: first, middle, last row (geographic diversity).
    idx = [0, len(provinces) // 2, len(provinces) - 1]
    sub = provinces.iloc[idx].reset_index(drop=True)
    print("provinces:", list(sub["name_en"]), "ids", list(sub["id"]))

    ds, thr = build_for_provinces(sub, START, END)
    print(f"\n[dataset] rows={len(ds)} cols={list(ds.columns)}")
    print(f"[dataset] date range {ds['time'].min().date()}..{ds['time'].max().date()}")
    print(f"[dataset] is_hot rate={ds['is_hot'].mean():.4f}  "
          f"heatwave rate={ds['heatwave'].mean():.4f}")

    # merge lat/lon like train_model.main does
    if "lat" not in ds.columns:
        ds = ds.merge(provinces[["id", "lat", "lon"]],
                      left_on="province_id", right_on="id", how="left").drop(columns=["id"])

    # forecasting frame + per-split positive counts
    frame = build_frames(ds, horizons=range(1, 8))
    yr = pd.to_datetime(frame["origin_time"]).dt.year
    frame = frame.assign(_yr=yr)
    print("\n[positives per split x horizon]  (y==1 counts)")
    for label, mask in [("train<=2023", yr <= 2023), ("val 2024", yr == 2024), ("test 2025", yr == 2025)]:
        block = frame[mask]
        by_h = block.groupby("horizon_k")["y"].sum().to_dict()
        tot = int(block["y"].sum())
        print(f"  {label:12s} rows={len(block):7d} pos_total={tot:5d} per_horizon={by_h}")

    # train end-to-end on the real frame
    print("\n[train_model] fitting on real 3-province data ...")
    bundle, report = train_model(ds, horizons=range(1, 8))
    keys = {k: v for k, v in report.items() if k != "features"}
    print("[report]", {k: keys[k] for k in ("n_train", "n_val", "n_test", "threshold") if k in keys})
    if "test" in report:
        print("[test metrics]", report["test"])
    if "baseline_constant" in report:
        print("[baseline]", report["baseline_constant"])
    print("\nSEAM OK")


if __name__ == "__main__":
    sys.exit(main())
