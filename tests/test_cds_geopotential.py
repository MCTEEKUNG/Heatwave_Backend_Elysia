import numpy as np
import pandas as pd
import xarray as xr

from src.cds_geopotential import _sample_from_dataset, attach_geopotential


def test_sample_from_dataset_nearest_and_height():
    times = pd.to_datetime(["2024-01-01", "2024-02-01"])
    lats = [13.0, 18.0]
    lons = [100.0, 99.0]
    # z in m^2/s^2; geopotential height = z / 9.80665
    z = np.array([[[58000.0, 58010.0], [58020.0, 58030.0]],
                  [[57000.0, 57010.0], [57020.0, 57030.0]]])  # (time, lat, lon)
    ds = xr.Dataset(
        {"z": (["valid_time", "latitude", "longitude"], z)},
        coords={"valid_time": times, "latitude": lats, "longitude": lons},
    )
    prov = pd.DataFrame([{"id": 1, "lat": 13.0, "lon": 100.0}])
    out = _sample_from_dataset(ds, prov)
    assert set(out.columns) == {"province_id", "year", "month", "hpa500"}
    assert len(out) == 2
    assert abs(out.iloc[0]["hpa500"] - 58000.0 / 9.80665) < 1e-6


def test_attach_geopotential_uses_previous_month():
    daily = pd.DataFrame({
        "time": pd.to_datetime(["2024-03-10", "2024-04-10"]),
        "province_id": [1, 1],
    })
    geo = pd.DataFrame({"province_id": [1, 1], "year": [2024, 2024],
                        "month": [2, 3], "hpa500": [5880.0, 5890.0]})
    out = attach_geopotential(daily, geo)
    # March -> prev Feb -> 5880 ; April -> prev March -> 5890
    assert list(out["hpa500"]) == [5880.0, 5890.0]
