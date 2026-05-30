import pandas as pd
from scripts.train_era5 import year_split

def test_year_split_is_temporal():
    df = pd.DataFrame({"origin_time": pd.to_datetime(
        ["2017-06-01", "2022-06-01", "2024-06-01"])})
    tr, va, te = year_split(df)
    assert len(tr) == 1 and len(va) == 1 and len(te) == 1
    assert tr["origin_time"].dt.year.iloc[0] <= 2021
    assert te["origin_time"].dt.year.iloc[0] >= 2024
