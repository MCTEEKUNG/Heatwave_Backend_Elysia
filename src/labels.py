# src/labels.py
"""Region-specific percentile + persistence heatwave label.

A day is a heatwave day iff its value >= the location's p95 for that day-of-year
AND it belongs to a run of >= `min_run` consecutive exceedance days.
"""
import pandas as pd


def label_heatwave(df: pd.DataFrame, thresholds: pd.DataFrame,
                   value_col: str = "swbgt_max", min_run: int = 2) -> pd.DataFrame:
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d["doy"] = d["time"].dt.dayofyear
    d = d.merge(thresholds[["doy", "p95"]], on="doy", how="left")
    d["is_hot"] = (d[value_col] >= d["p95"]).astype(int)

    d = d.sort_values("time").reset_index(drop=True)
    # group consecutive equal is_hot values into runs, measure run length
    grp = (d["is_hot"] != d["is_hot"].shift()).cumsum()
    run_len = d.groupby(grp)["is_hot"].transform("size")
    d["heatwave"] = ((d["is_hot"] == 1) & (run_len >= min_run)).astype(int)
    return d.drop(columns=["doy"])


def label_absolute(df, value_col="heat_index_max", threshold=41.0):
    """Absolute-threshold label (backend's heat-index mode), forecasting-safe:
    this only labels each day; the forecasting frame shifts it to t+k later."""
    out = df.copy()
    hot = (out[value_col] >= threshold).astype(int)
    out["is_hot"] = hot
    out["heatwave"] = hot
    return out
