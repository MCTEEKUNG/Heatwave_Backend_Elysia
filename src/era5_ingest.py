"""ERA5 6-hourly NetCDF (2016-2025) -> per-province DAILY aggregates.

Daily-max heat index (computed per 6-hourly step THEN maxed over the day) is the
physically-correct intensity DATA.md flags as the #1 label-accuracy fix. A daily
file (2000-2015, t2m-only) is REJECTED loudly so it can never be silently averaged.
"""
import numpy as np
import pandas as pd
import xarray as xr

from src.heat_index import rh_from_dewpoint, heat_index_c

_REQUIRED_VARS = ("t2m", "d2m", "sp", "u10", "v10")


def _tname(ds: xr.Dataset) -> str:
    return "valid_time" if "valid_time" in ds.coords else "time"


def _coord_names(ds: xr.Dataset):
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    return lat, lon


def _squeeze_extra_dims(ds: xr.Dataset) -> xr.Dataset:
    for d in ("number", "expver"):
        if d in ds.dims:
            ds = ds.isel({d: 0}, drop=True)
        elif d in ds.coords:
            ds = ds.reset_coords(d, drop=True)
    return ds


def nearest_cell(ds: xr.Dataset, lat: float, lon: float):
    laname, loname = _coord_names(ds)
    la = float(ds[laname].sel({laname: lat}, method="nearest"))
    lo = float(ds[loname].sel({loname: lon}, method="nearest"))
    return la, lo


def daily_from_subdaily(ds: xr.Dataset, province_id: int, lat: float, lon: float) -> pd.DataFrame:
    ds = _squeeze_extra_dims(ds)
    tname = _tname(ds)
    times = pd.to_datetime(ds[tname].values)
    # GUARD: refuse daily data (would make heat_index_max a daily-mean bias)
    if len(times) >= 2 and np.median(np.diff(times)).astype("timedelta64[h]") >= np.timedelta64(24, "h"):
        raise ValueError(f"sub-daily data required; got daily spacing in this file "
                         f"(vars={list(ds.data_vars)}) — out of scope for v2")
    missing = [v for v in _REQUIRED_VARS if v not in ds.data_vars]
    if missing:
        raise ValueError(f"missing required vars {missing}; not a full surface file")

    laname, loname = _coord_names(ds)
    pt = ds.sel({laname: lat, loname: lon}, method="nearest")
    df = pd.DataFrame({
        "time": times,
        "t2m_c": np.asarray(pt["t2m"].values) - 273.15,
        "d2m_c": np.asarray(pt["d2m"].values) - 273.15,
        "sp": np.asarray(pt["sp"].values),
        "u10": np.asarray(pt["u10"].values),
        "v10": np.asarray(pt["v10"].values),
    })
    df["rh"] = rh_from_dewpoint(df["t2m_c"], df["d2m_c"])
    df["heat_index"] = heat_index_c(df["t2m_c"], df["rh"])
    df["wind_speed"] = np.hypot(df["u10"], df["v10"])
    df["date"] = df["time"].dt.floor("D")
    daily = df.groupby("date").agg(
        t2m_c_max=("t2m_c", "max"),
        t2m_c_mean=("t2m_c", "mean"),
        rh_mean=("rh", "mean"),
        rh_min=("rh", "min"),
        heat_index_max=("heat_index", "max"),
        wind_speed_max=("wind_speed", "max"),
        sp_mean=("sp", "mean"),
    ).reset_index().rename(columns={"date": "time"})
    daily["province_id"] = province_id
    return daily


def ingest_year(nc_path: str, provinces: pd.DataFrame) -> pd.DataFrame:
    """All provinces for one full (2016-2025) ERA5 surface file -> daily frame."""
    with xr.open_dataset(nc_path, engine="netcdf4") as ds:
        frames = [daily_from_subdaily(ds, int(p["id"]), float(p["lat"]), float(p["lon"]))
                  for _, p in provinces.iterrows()]
    return pd.concat(frames, ignore_index=True)
