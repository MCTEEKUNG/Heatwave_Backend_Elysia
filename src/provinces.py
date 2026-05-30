# src/provinces.py
"""Load Thai province centroids (id, code, name, region, lat/lon)."""
import pandas as pd

REQUIRED = {"id", "code", "name_th", "name_en", "region", "lat", "lon"}


def load_provinces(path: str = "data/provinces.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"provinces.csv missing columns: {missing}")
    return df
