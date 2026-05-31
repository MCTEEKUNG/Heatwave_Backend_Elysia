"""Read-only summary of the detached GEFS reforecast pull for the Lab tab.

Pure function over the store parquet + build log; never launches anything.
"""
from __future__ import annotations

import os

import pandas as pd

STORE_PATH = "data/processed/gefs_forecast_store.parquet"
LOG_PATH = "data/processed/gefs_build_log.txt"
TARGET_INITS = 124  # 2016-2019 Mar-May, stride 3 (season_inits)


def gefs_status(store_path: str = STORE_PATH, log_path: str = LOG_PATH,
                target_inits: int = TARGET_INITS) -> dict:
    out = {"inits": 0, "rows": 0, "by_year": {}, "fc_spfh_pct": 0.0,
           "target": target_inits, "log_tail": ""}
    if os.path.exists(store_path):
        s = pd.read_parquet(store_path)
        out["rows"] = int(len(s))
        if len(s):
            out["inits"] = int(s["issue_date"].nunique())
            yr = pd.to_datetime(s["issue_date"]).drop_duplicates().dt.year
            out["by_year"] = {str(int(y)): int(n) for y, n in yr.value_counts().sort_index().items()}
            if "fc_spfh" in s.columns:
                out["fc_spfh_pct"] = round(float(s["fc_spfh"].notna().mean()) * 100, 1)
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        out["log_tail"] = "".join(lines[-12:]).strip()
    return out
