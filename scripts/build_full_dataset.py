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
#   HEATWAVE_SUBSET=N   build a regionally-stratified subset of ~N provinces
#   HEATWAVE_HOURLY=1   use the heavier hourly endpoint (correct daily-max sWBGT)
#   HEATWAVE_WAIT_RESET=1  poll gently until the hourly rate limit clears, then build
SUBSET = int(os.environ.get("HEATWAVE_SUBSET", "0"))
HOURLY = os.environ.get("HEATWAVE_HOURLY", "0") == "1"
WAIT_RESET = os.environ.get("HEATWAVE_WAIT_RESET", "0") == "1"


def _stratified(provinces, n):
    """Pick ~n provinces spread across regions (and within region by latitude)
    so a subset still covers Thailand's climate diversity."""
    import pandas as pd
    if n <= 0 or n >= len(provinces):
        return provinces
    out = []
    regions = list(provinces.groupby("region"))
    per = max(1, n // max(1, len(regions)))
    for _, grp in regions:
        g = grp.sort_values("lat")
        take = min(len(g), per)
        idx = [int(round(i * (len(g) - 1) / max(1, take - 1))) for i in range(take)] if take > 1 else [0]
        out.append(g.iloc[sorted(set(idx))])
    sub = pd.concat(out).drop_duplicates("id").head(n).reset_index(drop=True)
    return sub


def _wait_for_reset():
    """Poll a tiny request until the hourly limit clears (gentle: small probe
    every 2 min, up to ~75 min). Avoids hammering the API with heavy requests."""
    import requests
    for _ in range(38):
        try:
            r = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={"latitude": 13.7, "longitude": 100.5,
                        "start_date": "2024-04-01", "end_date": "2024-04-02",
                        "daily": "temperature_2m_max", "timezone": "Asia/Bangkok"},
                timeout=30)
            if r.status_code == 200:
                print("rate limit clear -- starting build", flush=True)
                return True
            print("still rate-limited; waiting 120s ...", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"probe error ({exc}); waiting 120s ...", flush=True)
        time.sleep(120)
    print("gave up waiting for rate-limit reset", flush=True)
    return False


def main():
    # Fail fast BEFORE any API call if the parquet engine is missing, so we
    # never waste rate-limited Open-Meteo requests only to fail on write.
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        print("pyarrow is required (pip install -r requirements.txt). Aborting.")
        return 3

    if WAIT_RESET and not _wait_for_reset():
        return 4

    provinces = load_provinces("data/provinces.csv")
    if SUBSET > 0:
        provinces = _stratified(provinces, SUBSET)
        print(f"SUBSET={SUBSET} -> regionally-stratified {len(provinces)} provinces: "
              f"{list(provinces['name_en'])}", flush=True)
    elif STRIDE > 1:
        provinces = provinces.iloc[::STRIDE].reset_index(drop=True)
        print(f"STRIDE={STRIDE} -> representative subset of {len(provinces)} provinces", flush=True)
    if HOURLY:
        print("HOURLY=1 -> deriving daily-max sWBGT from hourly data (heavier requests)", flush=True)
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
            ds_i, thr_i = build_for_provinces(one, START, END, hourly=HOURLY)
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
