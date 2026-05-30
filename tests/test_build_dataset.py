import numpy as np
import pandas as pd
from pipeline import build_dataset as bd
from src.swbgt import swbgt


def test_hourly_to_daily_swbgt_takes_hourly_max():
    # 2 days x 24 hours; temp peaks midday with low RH (the case daily-mean misses)
    rows = []
    for day in ("2024-04-01", "2024-04-02"):
        for h in range(24):
            ta = 28 + 8 * np.sin(np.pi * h / 23)        # peak ~36C at midday
            rh = 80 - 40 * np.sin(np.pi * h / 23)        # dips when hot
            rows.append({"time": pd.Timestamp(f"{day} {h:02d}:00"),
                         "temperature_2m": ta, "relative_humidity_2m": rh})
    hourly = pd.DataFrame(rows)
    daily = bd.hourly_to_daily_swbgt(hourly)

    assert list(daily.columns) == ["time", "temperature_2m_max",
                                   "relative_humidity_2m_mean", "swbgt_max"]
    assert len(daily) == 2
    # daily swbgt_max must equal the max of the per-hour sWBGT for that day
    for _, r in daily.iterrows():
        day_h = hourly[hourly["time"].dt.floor("D") == r["time"]]
        expected = swbgt(day_h["temperature_2m"], day_h["relative_humidity_2m"]).max()
        assert abs(r["swbgt_max"] - expected) < 1e-9
        assert abs(r["temperature_2m_max"] - day_h["temperature_2m"].max()) < 1e-9


def test_build_one_province(monkeypatch):
    rng = pd.date_range("1991-01-01", "2025-12-31", freq="D")
    np.random.seed(1)
    fake = pd.DataFrame({
        "time": rng,
        "temperature_2m_max": 33 + np.random.normal(0, 3, len(rng)),
        "relative_humidity_2m_mean": 60 + np.random.normal(0, 10, len(rng)),
    })
    monkeypatch.setattr(bd.openmeteo_client, "fetch_history",
                        lambda lat, lon, s, e, daily_vars=None: fake.copy())

    prov = pd.DataFrame([{"id": 1, "code": "BKK", "name_th": "x", "name_en": "Bangkok",
                          "region": "Central", "lat": 13.75, "lon": 100.5}])
    ds, thr = bd.build_for_provinces(prov, start="1991-01-01", end="2025-12-31")
    assert {"province_id", "time", "swbgt_max", "heatwave"}.issubset(ds.columns)
    assert {"province_id", "doy", "p95"}.issubset(thr.columns)
    assert ds["heatwave"].isin([0, 1]).all()
    assert 0 < ds["heatwave"].mean() < 0.3
