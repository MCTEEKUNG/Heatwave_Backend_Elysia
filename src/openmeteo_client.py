# src/openmeteo_client.py
"""Open-Meteo client. History (ERA5) for training, forecast for inference.

Fetches ONLY the variables the pipeline consumes (daily Tmax + mean RH → sWBGT),
retries on HTTP 429 (free-tier rate limit), and optionally uses an API key
(OPENMETEO_API_KEY env) to hit the higher-limit commercial endpoints.

Free-tier limits are weighted by data volume (~600/min, 5000/hour, 10000/day),
so wide multi-decade requests are "heavy" — callers should also throttle between
locations (see pipeline.build_dataset).
"""
import os
import time

import pandas as pd
import requests

# Variables consumed downstream. Tmax + mean RH define the sWBGT label; the rest
# are research-backed predictors (soil moisture = #2 heatwave predictor; ET /
# precip = drought signal; pressure/radiation/wind = synoptic/surface state).
DAILY_VARS = [
    "temperature_2m_max",
    "relative_humidity_2m_mean",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
    "soil_moisture_28_to_100cm_mean",
    "soil_temperature_0_to_7cm_mean",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "surface_pressure_mean",
    "shortwave_radiation_sum",
    "wind_speed_10m_max",
]

_FREE_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
_FREE_FORECAST = "https://api.open-meteo.com/v1/forecast"
_PAID_ARCHIVE = "https://customer-archive-api.open-meteo.com/v1/archive"
_PAID_FORECAST = "https://customer-api.open-meteo.com/v1/forecast"


def _api_key():
    return os.environ.get("OPENMETEO_API_KEY") or None


def _archive_url() -> str:
    return _PAID_ARCHIVE if _api_key() else _FREE_ARCHIVE


def _forecast_url() -> str:
    return _PAID_FORECAST if _api_key() else _FREE_FORECAST


def _daily_to_df(payload: dict) -> pd.DataFrame:
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"Open-Meteo error: {payload.get('reason')}")
    df = pd.DataFrame(payload["daily"])
    df["time"] = pd.to_datetime(df["time"])
    return df


def _get_json(url: str, params: dict, timeout: int = 60, max_retries: int = 6) -> dict:
    """GET with retry on HTTP 429. Honors Retry-After; otherwise backs off in
    ~minute steps since Open-Meteo's per-minute window resets each minute."""
    key = _api_key()
    if key:
        params = {**params, "apikey": key}
    last = None
    for attempt in range(max_retries + 1):
        r = requests.get(url, params=params, timeout=timeout)
        if getattr(r, "status_code", None) == 429 and attempt < max_retries:
            ra = r.headers.get("Retry-After") if hasattr(r, "headers") else None
            wait = int(ra) if (ra and str(ra).isdigit()) else min(60 * (attempt + 1), 300)
            time.sleep(wait)
            last = r
            continue
        r.raise_for_status()
        return r.json()
    if last is not None:
        last.raise_for_status()
    raise RuntimeError("Open-Meteo: retries exhausted")


def fetch_history(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "timezone": "Asia/Bangkok",
    }
    return _daily_to_df(_get_json(_archive_url(), params))


def fetch_forecast(lat: float, lon: float, days: int = 16) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "forecast_days": days,
        "timezone": "Asia/Bangkok",
    }
    return _daily_to_df(_get_json(_forecast_url(), params))
