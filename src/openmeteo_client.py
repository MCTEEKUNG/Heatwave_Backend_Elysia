# src/openmeteo_client.py
"""Open-Meteo client (no API key). History (ERA5) for training, forecast for inference.

NOTE: For production accuracy, daily sWBGT_max should be computed from HOURLY data
(hourly sWBGT then daily max). The daily aggregates here are a scaffold; verify the
exact daily variable names against https://open-meteo.com/en/docs/historical-weather-api
"""
import time

import pandas as pd
import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
]

# Open-Meteo's free tier rate-limits by weighted request size; large multi-decade
# history pulls can return 429. Retry with backoff (honoring Retry-After) so a
# bulk build survives transient limiting instead of aborting mid-run.
MAX_RETRIES = 6
MAX_BACKOFF_S = 60.0


def _get_with_retry(url: str, params: dict) -> "requests.Response":
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=60)
        except requests.RequestException as exc:  # network blip
            last_exc = exc
            time.sleep(min(2.0 ** attempt, MAX_BACKOFF_S))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            hdrs = getattr(r, "headers", {}) or {}
            ra = hdrs.get("Retry-After")
            delay = float(ra) if ra and str(ra).isdigit() else min(2.0 ** attempt, MAX_BACKOFF_S)
            last_exc = requests.HTTPError(f"{r.status_code} from {url}")
            time.sleep(delay)
            continue
        r.raise_for_status()
        return r
    raise last_exc if last_exc else RuntimeError(f"failed to GET {url}")


def _daily_to_df(payload: dict) -> pd.DataFrame:
    daily = payload["daily"]
    df = pd.DataFrame(daily)
    df["time"] = pd.to_datetime(df["time"])
    return df


def fetch_history(lat: float, lon: float, start: str, end: str,
                  daily_vars: list | None = None) -> pd.DataFrame:
    """Fetch daily history. ``daily_vars`` defaults to the full DAILY_VARS list;
    bulk builds can pass a smaller subset to reduce request weight."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(daily_vars or DAILY_VARS),
        "timezone": "Asia/Bangkok",
    }
    return _daily_to_df(_get_with_retry(ARCHIVE_URL, params).json())


def fetch_forecast(lat: float, lon: float, days: int = 16) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "forecast_days": days,
        "timezone": "Asia/Bangkok",
    }
    return _daily_to_df(_get_with_retry(FORECAST_URL, params).json())
