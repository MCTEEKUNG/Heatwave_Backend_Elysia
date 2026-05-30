import numpy as np
import pandas as pd
import pytest
import xarray as xr
from src.era5_ingest import daily_from_subdaily, nearest_cell

def _toy_6hourly():
    times = pd.date_range("2020-04-01", periods=8, freq="6h")  # 2 days x 4
    lat = np.array([13.5, 14.0]); lon = np.array([100.5, 101.0])
    shape = (len(times), len(lat), len(lon))
    def k(c): return np.full(shape, c + 273.15)
    ds = xr.Dataset(
        {"t2m": (("valid_time","latitude","longitude"), k(30.0)),
         "d2m": (("valid_time","latitude","longitude"), k(24.0)),
         "sp":  (("valid_time","latitude","longitude"), np.full(shape, 101325.0)),
         "u10": (("valid_time","latitude","longitude"), np.full(shape, 3.0)),
         "v10": (("valid_time","latitude","longitude"), np.full(shape, 4.0))},
        coords={"valid_time": times, "latitude": lat, "longitude": lon})
    return ds.expand_dims({"number": [0], "expver": [1]})  # extra dims to squeeze

def _toy_daily():
    times = pd.date_range("2003-04-01", periods=3, freq="D")
    lat = np.array([13.5]); lon = np.array([100.5])
    shape = (3, 1, 1)
    return xr.Dataset({"t2m": (("valid_time","latitude","longitude"), np.full(shape, 303.15))},
                      coords={"valid_time": times, "latitude": lat, "longitude": lon})

def test_nearest_cell_picks_closest():
    ds = _toy_6hourly()
    la, lo = nearest_cell(ds, 13.7563, 100.5018)
    # 13.7563 -> dist to 14.0 is 0.2437, dist to 13.5 is 0.2563 -> correct nearest is 14.0
    # (the original spec had 13.5 which is arithmetically incorrect)
    assert la == 14.0 and lo == 100.5

def test_daily_aggregates_units_and_squeeze():
    df = daily_from_subdaily(_toy_6hourly(), province_id=1, lat=13.7563, lon=100.5018)
    assert list(df["time"]) == [pd.Timestamp("2020-04-01"), pd.Timestamp("2020-04-02")]
    assert abs(df["t2m_c_max"].iloc[0] - 30.0) < 1e-6      # K->C
    assert abs(df["wind_speed_max"].iloc[0] - 5.0) < 1e-6  # hypot(3,4)
    assert (df["heat_index_max"] >= df["t2m_c_max"] - 5).all()

def test_daily_file_is_rejected_loudly():
    with pytest.raises(ValueError, match="sub-daily"):
        daily_from_subdaily(_toy_daily(), province_id=1, lat=13.5, lon=100.5)
