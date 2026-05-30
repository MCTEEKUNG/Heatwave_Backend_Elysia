# src/splits.py
"""Temporal (year-based) split. Replaces random stratified split to kill temporal leakage."""
import pandas as pd


def temporal_split(df: pd.DataFrame, time_col: str = "time",
                   train_end: int = 2023, val_year: int = 2024, test_year: int = 2025):
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col])
    y = d[time_col].dt.year
    train = d[y <= train_end]
    val = d[y == val_year]
    test = d[y == test_year]
    return train, val, test
