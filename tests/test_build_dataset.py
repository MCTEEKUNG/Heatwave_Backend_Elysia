import numpy as np
import pandas as pd
from pipeline import build_dataset as bd


def test_build_one_province(monkeypatch):
    rng = pd.date_range("1991-01-01", "2025-12-31", freq="D")
    np.random.seed(1)
    fake = pd.DataFrame({
        "time": rng,
        "temperature_2m_max": 33 + np.random.normal(0, 3, len(rng)),
        "relative_humidity_2m_mean": 60 + np.random.normal(0, 10, len(rng)),
    })
    monkeypatch.setattr(bd.openmeteo_client, "fetch_history",
                        lambda lat, lon, s, e: fake.copy())

    prov = pd.DataFrame([{"id": 1, "code": "BKK", "name_th": "x", "name_en": "Bangkok",
                          "region": "Central", "lat": 13.75, "lon": 100.5}])
    ds, thr = bd.build_for_provinces(prov, start="1991-01-01", end="2025-12-31")
    assert {"province_id", "time", "swbgt_max", "heatwave"}.issubset(ds.columns)
    assert {"province_id", "doy", "p95"}.issubset(thr.columns)
    assert ds["heatwave"].isin([0, 1]).all()
    assert 0 < ds["heatwave"].mean() < 0.3
