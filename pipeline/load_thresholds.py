# pipeline/load_thresholds.py
"""Load per-province climatology percentiles into Supabase.

Reads ``data/processed/province_thresholds.parquet`` (produced by
``pipeline.build_dataset``) and upserts it into ``heatwave.province_thresholds``
so the API / forecast features can read per-doy p95 from the DB.
"""
import pandas as pd

from src.db_write import upsert_thresholds

THRESHOLDS_PATH = "data/processed/province_thresholds.parquet"


def thresholds_to_rows(df: pd.DataFrame, metric: str = "sWBGT",
                       baseline_period: str = "1991-2020") -> list:
    """Convert a thresholds dataframe to upsert row dicts (pure, no DB)."""
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "province_id": int(r["province_id"]),
            "doy": int(r["doy"]),
            "metric": metric,
            "p90": float(r["p90"]),
            "p95": float(r["p95"]),
            "p975": float(r["p975"]),
            "baseline_period": baseline_period,
        })
    return rows


def main():
    df = pd.read_parquet(THRESHOLDS_PATH)
    rows = thresholds_to_rows(df)
    n = upsert_thresholds(rows)
    print(f"upserted {n} threshold rows ({df['province_id'].nunique()} provinces)")


if __name__ == "__main__":
    main()
