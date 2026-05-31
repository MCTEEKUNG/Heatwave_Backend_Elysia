# src/enso.py
"""ENSO (Niño 3.4) monthly index from NOAA PSL — a teleconnection predictor for
Southeast-Asian heat (El Niño tends to make Indochina hotter). Cached locally.

Source: https://psl.noaa.gov/data/correlation/nina34.anom.data
Format: a header line, then one row per year: ``YEAR m1 m2 ... m12`` where each
``m`` is that month's Niño-3.4 SST anomaly (-99.99 marks a missing value).
"""
import os

import pandas as pd
import requests

NOAA_NINO34_URL = "https://psl.noaa.gov/data/correlation/nina34.anom.data"
CACHE_PATH = "data/processed/enso_nino34.csv"
MISSING = -99.99


def fetch_nino34(url: str = NOAA_NINO34_URL, timeout: int = 30) -> pd.DataFrame:
    """Fetch + parse the monthly Niño-3.4 series -> DataFrame[year, month, nino34]."""
    text = requests.get(url, timeout=timeout).text
    rows = []
    for line in text.splitlines():
        parts = line.split()
        # data rows: a 4-digit year + 12 monthly values
        if len(parts) == 13 and parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])
            for month, raw in enumerate(parts[1:], start=1):
                val = float(raw)
                if val != MISSING:
                    rows.append({"year": year, "month": month, "nino34": val})
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("ENSO: parsed no rows from the NOAA source")
    return df


def load_enso(cache_path: str = CACHE_PATH, refresh: bool = False) -> pd.DataFrame:
    """Load Niño-3.4 from the local cache, fetching from NOAA if missing/refresh."""
    if not refresh and os.path.isfile(cache_path):
        return pd.read_csv(cache_path)
    df = fetch_nino34()
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df


def attach_nino34(daily: pd.DataFrame, enso: pd.DataFrame,
                  time_col: str = "time") -> pd.DataFrame:
    """Merge the PREVIOUS month's Niño-3.4 onto each daily row.

    Using the prior month (lag-1) guarantees the index is already known at time t
    — the monthly value is only finalized after the month ends, so the current
    month would be a look-ahead leak.
    """
    d = daily.copy()
    prev = pd.to_datetime(d[time_col]).dt.to_period("M") - 1
    d["_y"] = prev.dt.year
    d["_m"] = prev.dt.month
    e = enso.rename(columns={"year": "_y", "month": "_m"})
    d = d.merge(e[["_y", "_m", "nino34"]], on=["_y", "_m"], how="left")
    return d.drop(columns=["_y", "_m"])
