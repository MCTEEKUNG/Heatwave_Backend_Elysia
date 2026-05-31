# pipeline/build_dataset.py
"""Build training dataset + per-province thresholds from Open-Meteo.

Real runs need `pip install pyarrow` for parquet output. Tests exercise
`build_for_provinces` with mocked fetch and do not touch disk.
"""
import os
import time

import pandas as pd

from src import openmeteo_client
from src.swbgt import swbgt
from src.climatology import compute_doy_percentiles
from src.labels import label_heatwave
from src.provinces import load_provinces
from src.enso import load_enso, attach_nino34


def build_for_provinces(provinces: pd.DataFrame, start: str, end: str,
                        request_delay: float = 1.5):
    """Fetch + label every province. ``request_delay`` seconds are slept between
    Open-Meteo calls to respect free-tier rate limits (the client also retries
    on HTTP 429)."""
    all_rows, all_thr = [], []
    n = len(provinces)
    for i, (_, p) in enumerate(provinces.iterrows()):
        raw = openmeteo_client.fetch_history(p["lat"], p["lon"], start, end)
        raw["swbgt_max"] = swbgt(raw["temperature_2m_max"],
                                 raw["relative_humidity_2m_mean"])
        thr = compute_doy_percentiles(raw, value_col="swbgt_max",
                                      window=7, baseline=(1991, 2020))
        labeled = label_heatwave(raw, thr, value_col="swbgt_max", min_run=2)
        labeled["province_id"] = p["id"]
        thr["province_id"] = p["id"]
        all_rows.append(labeled)
        all_thr.append(thr)
        if request_delay and i < n - 1:
            time.sleep(request_delay)
    return (pd.concat(all_rows, ignore_index=True),
            pd.concat(all_thr, ignore_index=True))


def main():
    # Open-Meteo free tier is volume-limited (~10k weighted calls/day). The
    # default range fits comfortably; the climatology auto-uses whatever years
    # are fetched. For the full WMO 30-yr baseline (1991-2020), set an
    # OPENMETEO_API_KEY (paid) and OPENMETEO_START_YEAR=1991.
    start_year = int(os.environ.get("OPENMETEO_START_YEAR", "2010"))
    end_year = int(os.environ.get("OPENMETEO_END_YEAR", "2025"))
    delay = float(os.environ.get("OPENMETEO_REQUEST_DELAY", "3.0"))

    provinces = load_provinces("data/provinces.csv")
    print(f"Fetching {len(provinces)} provinces, {start_year}-{end_year}, "
          f"delay={delay}s, api_key={'yes' if os.environ.get('OPENMETEO_API_KEY') else 'no'} ...")
    ds, thr = build_for_provinces(
        provinces, f"{start_year}-01-01", f"{end_year}-12-31", request_delay=delay)

    # teleconnection predictor: attach previous-month Nino-3.4 (ENSO)
    try:
        enso = load_enso()
        ds = attach_nino34(ds, enso)
        print(f"attached ENSO Nino-3.4 ({int(enso['year'].min())}-{int(enso['year'].max())})")
    except Exception as exc:
        print(f"WARNING: ENSO attach skipped ({exc}); nino34 feature absent")

    # data-quality: report any column with >1% missing values
    na = ds.isna().mean()
    bad = {c: round(float(v), 4) for c, v in na.items() if v > 0.01}
    print("data-quality: columns >1% missing:", bad or "none")

    os.makedirs("data/processed", exist_ok=True)
    ds.to_parquet("data/processed/dataset.parquet", index=False)
    thr.to_parquet("data/processed/province_thresholds.parquet", index=False)
    print(f"dataset rows={len(ds)} provinces={ds['province_id'].nunique()} "
          f"years={start_year}-{end_year} heatwave_rate={ds['heatwave'].mean():.4f}")


if __name__ == "__main__":
    main()
