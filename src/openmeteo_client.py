# src/openmeteo_client.py
"""Open-Meteo client (no API key). History (ERA5) for training, forecast for inference.

NOTE: For production accuracy, daily sWBGT_max should be computed from HOURLY data
(hourly sWBGT then daily max). The daily aggregates here are a scaffold; verify the
exact daily variable names against https://open-meteo.com/en/docs/historical-weather-api
"""
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


def _daily_to_df(payload: dict) -> pd.DataFrame:
    daily = payload["daily"]
    df = pd.DataFrame(daily)
    df["time"] = pd.to_datetime(df["time"])
    return df


def fetch_history(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(ARCHIVE_URL, params=params, timeout=60)
    r.raise_for_status()
    return _daily_to_df(r.json())


def fetch_forecast(lat: float, lon: float, days: int = 16) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "forecast_days": days,
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(FORECAST_URL, params=params, timeout=60)
    r.raise_for_status()
    return _daily_to_df(r.json())
