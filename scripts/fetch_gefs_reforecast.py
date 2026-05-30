"""P0 REAL hindcast: NOAA GEFSv12 reforecast -> per-province daily-max forecast tmax.

Unlike ERA5/Historical-Forecast (which return analysis = leakage), GEFS reforecasts
are GENUINE forecasts issued at init time for future lead days — the only free,
no-credential, multi-year (2000-2019) source of real lead-k forecasts. Proven
readable here (cfgrib on Windows). This builds the clean forecast-covariate store
that P0 needs, WITHOUT waiting for the forward-collector to accumulate.

Each init date D: download control-member tmax_2m (Days 1-10, global 0.25 deg),
aggregate its sub-daily max-intervals to daily-max per valid date, extract the
nearest cell to each province centroid -> rows (province_id, issue_date=D,
target_date, lead_k, fc_tmax). issue_date < target_date by construction (no leak).

Volume note: ~39 MB per init (global). A useful 2016-2019 hot-season subset
(e.g. every 5 days, Mar-Jun) is a few GB — run with --inits or in the background.
"""
import os
import sys
import urllib.request
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces

BUCKET = "https://noaa-gefs-retrospective.s3.amazonaws.com"
RAW = "data/raw/gefs"
STORE = "data/processed/gefs_forecast_store.parquet"


def gefs_tmax_url(init: date, member: str = "c00") -> str:
    i = init.strftime("%Y%m%d") + "00"
    return (f"{BUCKET}/GEFSv12/reforecast/{init.year}/{i}/{member}/"
            f"Days:1-10/tmax_2m_{i}_{member}.grib2")


def daily_max_rows(ds, province_id: int, lat: float, lon: float) -> list:
    """cfgrib dataset (one init, sub-daily tmax steps) -> daily-max rows for one province."""
    var = list(ds.data_vars)[0]
    init = pd.Timestamp(ds["time"].values).normalize()
    glon = lon % 360.0  # GEFS uses 0-360 longitude
    pt = ds[var].sel(latitude=lat, longitude=glon, method="nearest").values - 273.15
    steps = np.atleast_1d(ds["step"].values)
    valid = init + pd.to_timedelta(steps)
    df = pd.DataFrame({"valid": valid, "tmax": np.atleast_1d(pt)})
    df["target_date"] = df["valid"].dt.floor("D")
    daily = df.groupby("target_date")["tmax"].max().reset_index()
    daily["lead_k"] = (daily["target_date"] - init).dt.days
    daily = daily[(daily["lead_k"] >= 1) & (daily["lead_k"] <= 7)]
    return [{"province_id": int(province_id), "issue_date": init.date().isoformat(),
             "target_date": r.target_date.date().isoformat(), "lead_k": int(r.lead_k),
             "fc_tmax": float(r.tmax)} for r in daily.itertuples()]


def _download(url: str, dest: str) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:  # some init dates are missing in the archive
        print(f"  miss {url.split('/')[-1]}: {type(e).__name__}", flush=True)
        return False


def collect(inits, provinces, store_path: str = STORE) -> pd.DataFrame:
    import xarray as xr
    os.makedirs(RAW, exist_ok=True)
    existing = pd.read_parquet(store_path) if os.path.exists(store_path) else pd.DataFrame()
    done = set(existing["issue_date"]) if not existing.empty else set()
    all_rows = []
    for init in inits:
        if init.isoformat() in done:
            print(f"  skip {init} (in store)", flush=True); continue
        dest = os.path.join(RAW, f"tmax_2m_{init.strftime('%Y%m%d')}00_c00.grib2")
        if not _download(gefs_tmax_url(init), dest):
            continue
        ds = xr.open_dataset(dest, engine="cfgrib", backend_kwargs={"indexpath": ""})
        for _, p in provinces.iterrows():
            all_rows.extend(daily_max_rows(ds, int(p["id"]), float(p["lat"]), float(p["lon"])))
        ds.close()
        os.remove(dest)  # 39 MB each — don't keep global files around
        print(f"  ingested init {init}: store rows +{len(all_rows)}", flush=True)
    new = pd.DataFrame(all_rows)
    out = pd.concat([existing, new], ignore_index=True) if not existing.empty and not new.empty else (new if existing.empty else existing)
    if not new.empty:
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        out.to_parquet(store_path, index=False)
    print(f"GEFS store: {len(out)} rows, {out['issue_date'].nunique() if len(out) else 0} inits, "
          f"{out['province_id'].nunique() if len(out) else 0} provinces", flush=True)
    return out


def build_inits(start: date, end: date, stride_days: int = 5):
    out, d = [], start
    while d <= end:
        out.append(d); d += timedelta(days=stride_days)
    return out


def main():
    # demo subset: 2 hot-season inits to prove the chain end-to-end on real data
    inits = build_inits(date(2018, 6, 16), date(2018, 6, 21), stride_days=5)
    collect(inits, load_provinces())
    return 0


if __name__ == "__main__":
    sys.exit(main())
