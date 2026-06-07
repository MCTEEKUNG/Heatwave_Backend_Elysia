"""P0 data engine: forward-collect REAL lead-k forecasts (leakage-safe by design).

The oracle test proved the only lever that reaches production is the target day's
forecast weather. ERA5 reanalysis and the Historical Forecast API both return
analysis-quality values for past dates (leakage) — so the ONLY clean source of
genuine lead-k forecasts is to capture them going forward, at issue time.

Each run on issue date D fetches Open-Meteo's forecast for D..D+6 (daily Tmax +
mean RH) for all 77 provinces and appends rows keyed by
(province_id, issue_date, target_date, lead_k). Because issue_date < target_date
by construction, a model predicting heatwave at t+k may use the forecast issued at
t for t+k with NO leakage and NO train/serve skew. Append-only + idempotent
(re-running on the same day is a no-op). Run daily (Task Scheduler / cron):
    .venv\\Scripts\\python.exe scripts\\collect_forecast.py

After ~2-3 months this store is a clean forecast-hindcast that can train P0
covariates. There is no shortcut: past_days/Historical-Forecast return analysis,
not the forecast issued k days earlier.
"""
import os
import sys
from datetime import date

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.provinces import load_provinces
from src.heat_index import heat_index_c

API = "https://api.open-meteo.com/v1/forecast"
STORE = "data/processed/forecast_store.parquet"
FORECAST_DAYS = 7
# Near-surface root-zone soil moisture: the highest-evidence land-atmosphere
# coupling covariate (dry soil -> more sensible heat -> faster warming). Open-Meteo
# serves it hourly only, so we aggregate to a daily mean per target_date.
SOIL_VAR = "soil_moisture_3_to_9cm"


def daily_mean_from_hourly(hourly: dict, var: str) -> dict:
    """Pure: {time:[hourly iso], var:[...]} -> {YYYY-MM-DD: daily mean} (skips None)."""
    times = hourly.get("time", [])
    vals = hourly.get(var, [])
    sums, counts = {}, {}
    for t, v in zip(times, vals):
        if v is None:
            continue
        d = str(t)[:10]
        sums[d] = sums.get(d, 0.0) + float(v)
        counts[d] = counts.get(d, 0) + 1
    return {d: sums[d] / counts[d] for d in sums}


def build_forecast_rows(daily: dict, province_id: int, issue_date,
                        soil_by_date: dict | None = None) -> list:
    """Pure: Open-Meteo `daily` dict -> rows with lead_k, forecast heat index, and
    (when provided) forecast soil moisture per target_date."""
    issue = pd.Timestamp(issue_date).normalize()
    rows = []
    times = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    rh = daily.get("relative_humidity_2m_mean", [])
    for t, tx, h in zip(times, tmax, rh):
        target = pd.Timestamp(t).normalize()
        lead = int((target - issue).days)
        if lead < 0 or tx is None or h is None:
            continue
        target_iso = target.date().isoformat()
        sm = None if soil_by_date is None else soil_by_date.get(target_iso)
        rows.append({
            "province_id": int(province_id),
            "issue_date": issue.date().isoformat(),
            "target_date": target_iso,
            "lead_k": lead,
            "fc_tmax": float(tx),
            "fc_rh": float(h),
            "fc_heat_index": float(heat_index_c(tx, h)),
            "fc_soil_moisture": None if sm is None else float(sm),
        })
    return rows


def _fetch(lat: float, lon: float):
    """Return (daily dict, {target_date: soil moisture daily-mean})."""
    p = {"latitude": lat, "longitude": lon,
         "daily": "temperature_2m_max,relative_humidity_2m_mean",
         "hourly": SOIL_VAR,
         "forecast_days": FORECAST_DAYS, "timezone": "Asia/Bangkok"}
    r = requests.get(API, params=p, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j.get("daily", {}), daily_mean_from_hourly(j.get("hourly", {}), SOIL_VAR)


def collect(provinces: pd.DataFrame, store_path: str = STORE, issue_date=None) -> pd.DataFrame:
    issue_date = issue_date or date.today()
    issue_iso = pd.Timestamp(issue_date).date().isoformat()
    existing = pd.read_parquet(store_path) if os.path.exists(store_path) else pd.DataFrame()
    if not existing.empty and (existing["issue_date"] == issue_iso).any():
        print(f"already collected issue_date={issue_iso} — no-op", flush=True)
        return existing
    rows = []
    for _, p in provinces.iterrows():
        daily, soil = _fetch(p["lat"], p["lon"])
        rows.extend(build_forecast_rows(daily, int(p["id"]), issue_date,
                                        soil_by_date=soil))
    new = pd.DataFrame(rows)
    out = pd.concat([existing, new], ignore_index=True) if not existing.empty else new
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    out.to_parquet(store_path, index=False)
    print(f"collected issue_date={issue_iso}: +{len(new)} rows "
          f"({new['province_id'].nunique()} provinces, leads {new['lead_k'].min()}-{new['lead_k'].max()}) "
          f"-> store now {len(out)} rows, {out['issue_date'].nunique()} issue dates", flush=True)
    return out


def main():
    collect(load_provinces())
    return 0


if __name__ == "__main__":
    sys.exit(main())
