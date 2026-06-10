"""Two-way sync between the local P0 forecast store and heatwave.forecast_store.

Up:   local parquet rows are pushed to Supabase (ON CONFLICT DO NOTHING) — this
      both seeds the table from the pre-cloud collection and backfills any day
      the laptop collected while CI was down.
Down: the full cloud table is fetched and unioned into the parquet, so training
      sees every issue_date regardless of which side collected it.

Idempotent in both directions; run any time before training:
    .venv\\Scripts\\python.exe scripts\\sync_forecast_store.py
"""
import os
import sys

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

STORE = os.path.join(REPO, "data", "processed", "forecast_store.parquet")
KEY = ["province_id", "issue_date", "target_date"]


def merge_stores(local: pd.DataFrame, db: pd.DataFrame) -> pd.DataFrame:
    """Pure: union of both stores, deduped on KEY (local wins), sorted by KEY."""
    frames = [f for f in (local, db) if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=KEY, keep="first")
    return out.sort_values(KEY).reset_index(drop=True)


def _load_env():
    path = os.path.join(REPO, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_env()
    from src.forecast_store_db import fetch_df, rows_for_upsert, upsert_rows

    local = pd.read_parquet(STORE) if os.path.exists(STORE) else pd.DataFrame()
    uploaded = upsert_rows(rows_for_upsert(local))
    db = fetch_df()
    merged = merge_stores(local, db)
    merged.to_parquet(STORE, index=False)
    print(f"up: {uploaded} rows uploaded ({len(local)} local) | "
          f"down: {len(db)} rows in DB | "
          f"store now {len(merged)} rows, {merged['issue_date'].nunique()} issue dates",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
