"""Fetch Open-Meteo ARCHIVE soil moisture (3-9cm) per province -> daily mean.

Antecedent (observed) soil moisture is a leakage-safe predictor of heatwaves via
land-atmosphere coupling (Felsche 2023; Benson 2020). This pulls the historical
hourly series for the GEFS-overlap window so we can A/B-test whether antecedent
soil moisture lifts the model. Reuses the tested daily_mean_from_hourly aggregator.

Bounded: one archive call per province (77), retry on 429. Output:
    data/processed/era5_soil_moisture.parquet  (province_id, date, soil_moisture)
"""
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from scripts.collect_forecast import daily_mean_from_hourly

# Archive (ERA5-Land) uses different soil-moisture layer names than the forecast
# model: near-surface root-zone layer is 0-7cm here (vs 3-9cm on the forecast API).
ARCHIVE_SOIL_VAR = "soil_moisture_0_to_7cm"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OUT = "data/processed/era5_soil_moisture.parquet"
START, END = "2016-02-01", "2019-06-30"  # covers Mar-May GEFS inits + lead-in + leads


def fetch_province(lat: float, lon: float) -> dict:
    p = {"latitude": lat, "longitude": lon, "start_date": START, "end_date": END,
         "hourly": ARCHIVE_SOIL_VAR, "timezone": "Asia/Bangkok"}
    for attempt in range(6):
        r = requests.get(ARCHIVE, params=p, timeout=180)
        if r.status_code == 429:
            time.sleep(20)
            continue
        r.raise_for_status()
        return r.json().get("hourly", {})
    r.raise_for_status()
    return {}


def main():
    prov = load_provinces()
    frames = []
    for i, (_, p) in enumerate(prov.iterrows(), 1):
        hourly = fetch_province(float(p["lat"]), float(p["lon"]))
        dm = daily_mean_from_hourly(hourly, ARCHIVE_SOIL_VAR)
        df = pd.DataFrame({"date": list(dm.keys()), "soil_moisture": list(dm.values())})
        df["province_id"] = int(p["id"])
        frames.append(df)
        print(f"[{i}/{len(prov)}] province {int(p['id'])}: {len(df)} days", flush=True)
        time.sleep(1)
    out = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"SAVED {OUT}: {len(out)} rows, {out['province_id'].nunique()} provinces", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
