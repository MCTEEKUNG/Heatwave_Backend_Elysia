"""Add forecast humidity (GEFS spfh_2m, daily-mean) to the GEFS store so train_p0
can build a forecast HEAT-INDEX covariate (the humidity-inclusive signal the oracle
showed matters). Pulls spfh_2m for the inits already in the store and merges fc_spfh.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from scripts.fetch_gefs_reforecast import BUCKET, RAW, STORE, _download


def spfh_url(init_iso: str) -> str:
    i = init_iso.replace("-", "") + "00"
    y = init_iso[:4]
    return f"{BUCKET}/GEFSv12/reforecast/{y}/{i}/c00/Days:1-10/spfh_2m_{i}_c00.grib2"


def daily_mean_spfh_rows(ds, province_id, lat, lon):
    var = list(ds.data_vars)[0]
    init = pd.Timestamp(ds["time"].values).normalize()
    pt = ds[var].sel(latitude=lat, longitude=lon % 360.0, method="nearest").values
    steps = np.atleast_1d(ds["step"].values)
    valid = init + pd.to_timedelta(steps)
    df = pd.DataFrame({"valid": valid, "spfh": np.atleast_1d(pt)})
    df["target_date"] = df["valid"].dt.floor("D")
    daily = df.groupby("target_date")["spfh"].mean().reset_index()
    daily["lead_k"] = (daily["target_date"] - init).dt.days
    daily = daily[(daily["lead_k"] >= 1) & (daily["lead_k"] <= 7)]
    return [{"province_id": int(province_id), "issue_date": init.date().isoformat(),
             "target_date": r.target_date.date().isoformat(), "lead_k": int(r.lead_k),
             "fc_spfh": float(r.spfh)} for r in daily.itertuples()]


def main():
    import xarray as xr
    store = pd.read_parquet(STORE)
    if "fc_spfh" in store.columns:
        print("fc_spfh already present"); return 0
    provinces = load_provinces()
    inits = sorted(store["issue_date"].unique())
    rows = []
    for j, iso in enumerate(inits, 1):
        dest = os.path.join(RAW, f"spfh_2m_{iso.replace('-','')}00_c00.grib2")
        if not _download(spfh_url(iso), dest):
            continue
        ds = xr.open_dataset(dest, engine="cfgrib", backend_kwargs={"indexpath": ""})
        for _, p in provinces.iterrows():
            rows.extend(daily_mean_spfh_rows(ds, int(p["id"]), float(p["lat"]), float(p["lon"])))
        ds.close(); os.remove(dest)
        if j % 10 == 0:
            print(f"  {j}/{len(inits)} inits, spfh rows so far {len(rows)}", flush=True)
    spfh = pd.DataFrame(rows)
    merged = store.merge(spfh, on=["province_id", "issue_date", "target_date", "lead_k"], how="left")
    merged.to_parquet(STORE, index=False)
    print(f"merged fc_spfh: {merged['fc_spfh'].notna().mean()*100:.0f}% of rows have humidity; "
          f"store {len(merged)} rows", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
