import pandas as pd
from src.splits import temporal_split


def test_temporal_split_no_year_overlap():
    df = pd.DataFrame({
        "time": pd.to_datetime(
            ["2022-06-01", "2023-06-01", "2024-06-01", "2025-06-01"]),
        "x": [1, 2, 3, 4],
    })
    tr, va, te = temporal_split(df, train_end=2023, val_year=2024, test_year=2025)
    assert tr["time"].dt.year.max() <= 2023
    assert (va["time"].dt.year == 2024).all()
    assert (te["time"].dt.year == 2025).all()
    assert set(tr["time"].dt.year) & set(va["time"].dt.year) == set()
    assert set(va["time"].dt.year) & set(te["time"].dt.year) == set()
