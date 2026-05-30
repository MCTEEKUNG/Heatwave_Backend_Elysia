import pandas as pd
from scripts.train_p0 import join_forecast


def test_join_attaches_forecast_on_matching_keys():
    frame = pd.DataFrame({
        "province_id": [1, 1, 2],
        "origin_time": pd.to_datetime(["2018-06-16", "2018-06-16", "2018-06-16"]),
        "target_time": pd.to_datetime(["2018-06-17", "2018-06-18", "2018-06-17"]),
        "horizon_k": [1, 2, 1],
        "y": [0, 1, 0],
    })
    store = pd.DataFrame({
        "province_id": [1, 1],
        "issue_date": ["2018-06-16", "2018-06-16"],
        "target_date": ["2018-06-17", "2018-06-18"],
        "lead_k": [1, 2],
        "fc_tmax": [35.0, 37.0],
    })
    merged = join_forecast(frame, store)
    # province 2 has no forecast -> dropped by inner join; province 1 keeps 2 rows
    assert len(merged) == 2
    assert set(merged["province_id"]) == {1}
    assert sorted(merged["fc_tmax"]) == [35.0, 37.0]
