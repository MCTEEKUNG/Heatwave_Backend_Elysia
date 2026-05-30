# src/climatology.py
"""Per-location day-of-year windowed percentiles over a WMO baseline period.

Vectorized: for each day-of-year, pool all baseline-year values within +/- `window`
days (circular around the year) and take percentiles. Matches Perkins & Alexander.
"""
import numpy as np
import pandas as pd


def compute_doy_percentiles(df: pd.DataFrame, value_col: str = "swbgt_max",
                            window: int = 7, baseline=(1991, 2020)) -> pd.DataFrame:
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d = d[(d["time"].dt.year >= baseline[0]) & (d["time"].dt.year <= baseline[1])]

    doy_arr = d["time"].dt.dayofyear.to_numpy()
    vals_arr = d[value_col].to_numpy(dtype=float)

    rows = []
    for doy in range(1, 367):
        # circular window of day-of-year values mapped onto 1..366
        offsets = [((doy - 1 + o) % 366) + 1 for o in range(-window, window + 1)]
        mask = np.isin(doy_arr, offsets)
        vals = vals_arr[mask]
        vals = vals[~np.isnan(vals)]
        if len(vals) == 0:
            continue
        rows.append({
            "doy": doy,
            "p90": float(np.percentile(vals, 90)),
            "p95": float(np.percentile(vals, 95)),
            "p975": float(np.percentile(vals, 97.5)),
        })
    return pd.DataFrame(rows)
