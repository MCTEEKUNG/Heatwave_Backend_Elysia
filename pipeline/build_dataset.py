# pipeline/build_dataset.py
"""Build training dataset + per-province thresholds from Open-Meteo.

Real runs need `pip install pyarrow` for parquet output. Tests exercise
`build_for_provinces` with mocked fetch and do not touch disk.
"""
import os
import pandas as pd

from src import openmeteo_client
from src.swbgt import swbgt
from src.climatology import compute_doy_percentiles
from src.labels import label_heatwave
from src.provinces import load_provinces


# Only these daily variables are needed to derive sWBGT and the heatwave label;
# requesting just these (instead of the full DAILY_VARS) cuts Open-Meteo request
# weight ~3x for bulk historical builds.
BUILD_DAILY_VARS = ["temperature_2m_max", "relative_humidity_2m_mean"]


def hourly_to_daily_swbgt(hourly: pd.DataFrame) -> pd.DataFrame:
    """Collapse hourly temp+RH into a daily frame with a PHYSICALLY CORRECT
    daily-max sWBGT: compute sWBGT each hour, then take the daily max. This
    avoids the daily-Tmax + daily-mean-RH bias (max temp coincides with min RH).
    Returns columns: time, temperature_2m_max, relative_humidity_2m_mean, swbgt_max.
    """
    d = hourly.copy()
    d["swbgt"] = swbgt(d["temperature_2m"], d["relative_humidity_2m"])
    d["date"] = pd.to_datetime(d["time"]).dt.floor("D")
    out = d.groupby("date").agg(
        temperature_2m_max=("temperature_2m", "max"),
        relative_humidity_2m_mean=("relative_humidity_2m", "mean"),
        swbgt_max=("swbgt", "max"),
    ).reset_index().rename(columns={"date": "time"})
    return out


def build_for_provinces(provinces: pd.DataFrame, start: str, end: str,
                        daily_vars: list | None = None, hourly: bool = False):
    """Build per-province labeled frames + thresholds.

    ``hourly=True`` uses the heavier hourly endpoint to derive a correct
    daily-max sWBGT (higher label accuracy, ~24x the request weight).
    """
    all_rows, all_thr = [], []
    for _, p in provinces.iterrows():
        if hourly:
            raw = hourly_to_daily_swbgt(
                openmeteo_client.fetch_history_hourly(p["lat"], p["lon"], start, end))
        else:
            raw = openmeteo_client.fetch_history(
                p["lat"], p["lon"], start, end, daily_vars=daily_vars or BUILD_DAILY_VARS)
            raw["swbgt_max"] = swbgt(raw["temperature_2m_max"],
                                     raw["relative_humidity_2m_mean"])
        thr = compute_doy_percentiles(raw, value_col="swbgt_max",
                                      window=7, baseline=(1991, 2020))
        labeled = label_heatwave(raw, thr, value_col="swbgt_max", min_run=2)
        labeled["province_id"] = p["id"]
        thr["province_id"] = p["id"]
        all_rows.append(labeled)
        all_thr.append(thr)
    return (pd.concat(all_rows, ignore_index=True),
            pd.concat(all_thr, ignore_index=True))


def main():
    provinces = load_provinces("data/provinces.csv")
    ds, thr = build_for_provinces(provinces, "1991-01-01", "2025-12-31")
    os.makedirs("data/processed", exist_ok=True)
    ds.to_parquet("data/processed/dataset.parquet", index=False)
    thr.to_parquet("data/processed/province_thresholds.parquet", index=False)
    print(f"dataset rows={len(ds)} provinces={ds['province_id'].nunique()} "
          f"heatwave_rate={ds['heatwave'].mean():.4f}")


if __name__ == "__main__":
    main()
