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


def build_forecast_rows(daily: dict, province_id: int, issue_date) -> list:
    """Pure: Open-Meteo `daily` dict -> rows with lead_k and forecast heat index."""
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
        rows.append({
            "province_id": int(province_id),
            "issue_date": issue.date().isoformat(),
            "target_date": target.date().isoformat(),
            "lead_k": lead,
            "fc_tmax": float(tx),
            "fc_rh": float(h),
            "fc_heat_index": float(heat_index_c(tx, h)),
        })
    return rows


def _fetch(lat: float, lon: float) -> dict:
    p = {"latitude": lat, "longitude": lon,
         "daily": "temperature_2m_max,relative_humidity_2m_mean",
         "forecast_days": FORECAST_DAYS, "timezone": "Asia/Bangkok"}
    r = requests.get(API, params=p, timeout=60)
    r.raise_for_status()
    return r.json().get("daily", {})


def collect(provinces: pd.DataFrame, store_path: str = STORE, issue_date=None) -> pd.DataFrame:
    issue_date = issue_date or date.today()
    issue_iso = pd.Timestamp(issue_date).date().isoformat()
    existing = pd.read_parquet(store_path) if os.path.exists(store_path) else pd.DataFrame()
    if not existing.empty and (existing["issue_date"] == issue_iso).any():
        print(f"already collected issue_date={issue_iso} — no-op", flush=True)
        return existing
    rows = []
    for _, p in provinces.iterrows():
        rows.extend(build_forecast_rows(_fetch(p["lat"], p["lon"]), int(p["id"]), issue_date))
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
