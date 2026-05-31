# src/cds_geopotential.py
"""ERA5 500 hPa geopotential — the #1 heatwave predictor (upper-level ridge /
circulation) — from the Copernicus Climate Data Store (CDS).

Monthly-mean geopotential is downloaded for the Thailand region, sampled at each
province centroid, and attached as the PREVIOUS month's value (lag-1). The lag is
deliberate: ERA5 has ~5-day latency, so a monthly prev-month value is always known
at time t for both training and real-time inference (no look-ahead, no gaps).

Setup:
  pip install cdsapi xarray netcdf4
  configure ~/.cdsapirc with your CDS key (https://cds.climate.copernicus.eu/how-to-api)
"""
import os

import numpy as np
import pandas as pd

DATASET = "reanalysis-era5-pressure-levels-monthly-means"
THAILAND_AREA = [21, 97, 5, 106]   # N, W, S, E bounding box
CACHE_PATH = "data/processed/geopotential.csv"
G = 9.80665  # m s^-2: geopotential (m^2/s^2) -> geopotential height (m)


def fetch_geopotential_nc(start_year, end_year, target,
                          area=THAILAND_AREA, level="500"):
    """Download monthly-mean 500 hPa geopotential over `area` to a NetCDF file."""
    import cdsapi
    client = cdsapi.Client()
    client.retrieve(DATASET, {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": ["geopotential"],
        "pressure_level": [str(level)],
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
        "area": list(area),
        "data_format": "netcdf",
    }, target)
    return target


def _sample_from_dataset(ds, provinces) -> pd.DataFrame:
    """Sample geopotential height at each province point (pure; unit-testable)."""
    z = ds["z"]
    if "pressure_level" in z.dims:
        z = z.sel(pressure_level=500)
    tdim = "valid_time" if "valid_time" in z.dims else "time"
    rows = []
    for _, p in provinces.iterrows():
        s = z.sel(latitude=float(p["lat"]), longitude=float(p["lon"]),
                  method="nearest")
        times = pd.to_datetime(np.atleast_1d(s[tdim].values))
        vals = np.atleast_1d(np.asarray(s.values, dtype=float)) / G
        for ts, v in zip(times, vals):
            if pd.isna(v):
                continue
            rows.append({"province_id": int(p["id"]), "year": int(ts.year),
                         "month": int(ts.month), "hpa500": float(v)})
    return pd.DataFrame(rows)


def sample_provinces(nc_path, provinces) -> pd.DataFrame:
    import xarray as xr
    ds = xr.open_dataset(nc_path)
    try:
        df = _sample_from_dataset(ds, provinces)
    finally:
        ds.close()
    if df.empty:
        raise RuntimeError("CDS geopotential: no samples extracted")
    return df


def build_geopotential_cache(provinces, start_year, end_year,
                             cache_path=CACHE_PATH, nc_path=None) -> pd.DataFrame:
    nc_path = nc_path or "data/processed/_era5_z500.nc"
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    fetch_geopotential_nc(start_year, end_year, nc_path)
    df = sample_provinces(nc_path, provinces)
    df.to_csv(cache_path, index=False)
    return df


def load_geopotential(cache_path: str = CACHE_PATH):
    if os.path.isfile(cache_path):
        return pd.read_csv(cache_path)
    return None


def attach_geopotential(daily: pd.DataFrame, geo_df: pd.DataFrame,
                        time_col: str = "time") -> pd.DataFrame:
    """Merge the PREVIOUS month's 500 hPa height per province (lag-1)."""
    d = daily.copy()
    prev = pd.to_datetime(d[time_col]).dt.to_period("M") - 1
    d["_y"] = prev.dt.year
    d["_m"] = prev.dt.month
    e = geo_df.rename(columns={"year": "_y", "month": "_m"})
    d = d.merge(e[["province_id", "_y", "_m", "hpa500"]],
                on=["province_id", "_y", "_m"], how="left")
    return d.drop(columns=["_y", "_m"])
