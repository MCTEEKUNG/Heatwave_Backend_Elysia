import pandas as pd
from pipeline.build_era5_dataset import attach_climatology_label

def test_attach_label_b_adds_required_columns():
    days = pd.date_range("2003-01-01", periods=400, freq="D")
    df = pd.DataFrame({"province_id": 1, "time": days,
                       "heat_index_max": 30 + 10*(days.dayofyear/365)})
    out = attach_climatology_label(df, mode="absolute", abs_threshold=35.0)
    for col in ["swbgt_max", "is_hot", "heatwave"]:
        assert col in out.columns
