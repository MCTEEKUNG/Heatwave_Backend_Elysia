"""Build the full training dataset from Open-Meteo for ALL provinces.

Resilient + resumable:
- one province per Open-Meteo call (retry/backoff lives in openmeteo_client),
- a short sleep between provinces to stay under the weighted rate limit,
- per-province checkpoint parts so a late failure never wastes earlier work
  (re-run to resume; already-built provinces are skipped),
- concat parts -> data/processed/dataset.parquet + province_thresholds.parquet.

Run from repo root:
  .venv\\Scripts\\python.exe scripts\\build_full_dataset.py
"""
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from pipeline.build_dataset import build_for_provinces

START, END = "1991-01-01", "2025-12-31"
PARTS_DIR = "data/processed/_parts"
OUT_DS = "data/processed/dataset.parquet"
OUT_THR = "data/processed/province_thresholds.parquet"

# Open-Meteo's free tier weight-limits large multi-decade requests, so pace
# politely. All tunable via env so a slow full run can be left in the background.
#   HEATWAVE_SLEEP    seconds between successful requests   (default 20)
#   HEATWAVE_COOLDOWN seconds to wait after a 429 failure   (default 75)
#   HEATWAVE_STRIDE   take provinces[::stride] for a quick representative subset
SLEEP_BETWEEN_S = float(os.environ.get("HEATWAVE_SLEEP", "20"))
COOLDOWN_S = float(os.environ.get("HEATWAVE_COOLDOWN", "75"))
STRIDE = int(os.environ.get("HEATWAVE_STRIDE", "1"))


def main():
    # Fail fast BEFORE any API call if the parquet engine is missing, so we
    # never waste rate-limited Open-Meteo requests only to fail on write.
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        print("pyarrow is required (pip install -r requirements.txt). Aborting.")
        return 3

    provinces = load_provinces("data/provinces.csv")
    if STRIDE > 1:
        provinces = provinces.iloc[::STRIDE].reset_index(drop=True)
        print(f"STRIDE={STRIDE} -> representative subset of {len(provinces)} provinces", flush=True)
    os.makedirs(PARTS_DIR, exist_ok=True)
    n = len(provinces)
    failed = []

    for i, (_, p) in enumerate(provinces.iterrows(), start=1):
        pid = int(p["id"])
        ds_part = os.path.join(PARTS_DIR, f"ds_{pid:03d}.parquet")
        thr_part = os.path.join(PARTS_DIR, f"thr_{pid:03d}.parquet")
        if os.path.exists(ds_part) and os.path.exists(thr_part):
            print(f"[{i:3d}/{n}] id={pid:3d} {p['name_en']:<22} (cached)", flush=True)
            continue
        try:
            one = provinces.iloc[[i - 1]]
            ds_i, thr_i = build_for_provinces(one, START, END)
            ds_i.to_parquet(ds_part, index=False)
            thr_i.to_parquet(thr_part, index=False)
            print(f"[{i:3d}/{n}] id={pid:3d} {p['name_en']:<22} rows={len(ds_i):6d} "
                  f"hw_rate={ds_i['heatwave'].mean():.3f}", flush=True)
            time.sleep(SLEEP_BETWEEN_S)
        except Exception as exc:  # noqa: BLE001
            is_429 = "429" in str(exc)
            print(f"[{i:3d}/{n}] id={pid:3d} {p['name_en']:<22} FAILED: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            failed.append(pid)
            # After a rate-limit hit, wait out the window before the next request
            # instead of hammering (which just keeps failing).
            time.sleep(COOLDOWN_S if is_429 else SLEEP_BETWEEN_S)

    # Stitch all available parts together.
    ds_files = sorted(f for f in os.listdir(PARTS_DIR) if f.startswith("ds_"))
    thr_files = sorted(f for f in os.listdir(PARTS_DIR) if f.startswith("thr_"))
    if not ds_files:
        print("no parts built; aborting")
        return 1
    ds = pd.concat([pd.read_parquet(os.path.join(PARTS_DIR, f)) for f in ds_files],
                   ignore_index=True)
    thr = pd.concat([pd.read_parquet(os.path.join(PARTS_DIR, f)) for f in thr_files],
                    ignore_index=True)
    ds.to_parquet(OUT_DS, index=False)
    thr.to_parquet(OUT_THR, index=False)

    print("\n==== BUILD SUMMARY ====", flush=True)
    print(f"provinces built : {ds['province_id'].nunique()} / {n}")
    print(f"rows            : {len(ds)}")
    print(f"date range      : {ds['time'].min().date()}..{ds['time'].max().date()}")
    print(f"is_hot rate     : {ds['is_hot'].mean():.4f}")
    print(f"heatwave rate   : {ds['heatwave'].mean():.4f}")
    print(f"wrote           : {OUT_DS} , {OUT_THR}")
    if failed:
        print(f"FAILED provinces (re-run to resume): {failed}")
        return 2
    print("ALL PROVINCES BUILT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
