from datetime import date

import numpy as np
import pandas as pd
import xarray as xr

from scripts.fetch_gefs_reforecast import gefs_tmax_url, daily_max_rows, build_inits


def test_gefs_url_layout():
    u = gefs_tmax_url(date(2018, 6, 16))
    assert u == ("https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast/"
                 "2018/2018061600/c00/Days:1-10/tmax_2m_2018061600_c00.grib2")


def test_build_inits_stride():
    inits = build_inits(date(2018, 3, 1), date(2018, 3, 11), stride_days=5)
    assert inits == [date(2018, 3, 1), date(2018, 3, 6), date(2018, 3, 11)]


def test_daily_max_rows_aggregates_subdaily_and_leads():
    init = pd.Timestamp("2018-06-16")
    # 4 sub-daily steps spanning lead day 1 and day 2 (in hours)
    steps = pd.to_timedelta([30, 36, 54, 60], unit="h")  # day1: 30/36h, day2: 54/60h
    temps_k = np.array([308.15, 310.15, 305.15, 306.15])  # 35,37,32,33 degC
    ds = xr.Dataset(
        {"tmax": (("step",), temps_k)},
        coords={"step": steps, "time": init,
                "latitude": 13.5, "longitude": 100.5})
    # make it indexable by lat/lon via expand (nearest sel needs dims)
    ds = ds.assign_coords(latitude=13.5, longitude=100.5)
    rows = daily_max_rows(ds.expand_dims(latitude=[13.5]).expand_dims(longitude=[100.5]),
                          province_id=1, lat=13.7, lon=100.5)
    by_lead = {r["lead_k"]: r["fc_tmax"] for r in rows}
    assert by_lead[1] == 37.0  # daily max of 35,37
    assert by_lead[2] == 33.0  # daily max of 32,33
    assert all(r["issue_date"] == "2018-06-16" for r in rows)
    assert all(r["target_date"] > r["issue_date"] for r in rows)  # leakage-safe
