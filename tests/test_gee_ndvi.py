import pandas as pd

from src.gee_ndvi import _parse_province_ndvi, attach_ndvi


def test_parse_province_ndvi_scales_and_drops_null():
    feats = [
        {"properties": {"t": "2024-03", "ndvi": 6000}},
        {"properties": {"t": "2024-04", "ndvi": None}},   # dropped
        {"properties": {"t": "2024-05", "ndvi": 4000}},
    ]
    rows = _parse_province_ndvi(feats, province_id=7)
    assert len(rows) == 2
    assert rows[0] == {"province_id": 7, "year": 2024, "month": 3, "ndvi": 0.6}
    assert abs(rows[1]["ndvi"] - 0.4) < 1e-9


def test_attach_ndvi_uses_previous_month_per_province():
    daily = pd.DataFrame({
        "time": pd.to_datetime(["2024-04-10", "2024-04-11", "2024-04-10"]),
        "province_id": [1, 1, 2],
    })
    ndvi = pd.DataFrame({"province_id": [1, 2], "year": [2024, 2024],
                         "month": [3, 3], "ndvi": [0.6, 0.4]})
    out = attach_ndvi(daily, ndvi)
    # April rows -> previous month March: province 1 -> 0.6, province 2 -> 0.4
    assert list(out["ndvi"]) == [0.6, 0.6, 0.4]
