import pandas as pd
from src.labels import label_heatwave


def _thr():
    return pd.DataFrame({"doy": range(1, 367), "p95": [30] * 366})


def test_isolated_hot_day_not_heatwave():
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-03"]),
        "swbgt_max": [31, 25, 31],   # hot-cool-hot (not consecutive)
    })
    out = label_heatwave(df, _thr(), value_col="swbgt_max", min_run=2)
    assert out["heatwave"].tolist() == [0, 0, 0]


def test_run_of_two_is_heatwave():
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-03"]),
        "swbgt_max": [31, 31, 25],   # two consecutive hot days
    })
    out = label_heatwave(df, _thr(), value_col="swbgt_max", min_run=2)
    assert out["heatwave"].tolist() == [1, 1, 0]
