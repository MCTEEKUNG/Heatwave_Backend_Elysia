"""Prove the LIVE production write path on a small province subset:
load the trained model -> fetch real Open-Meteo data -> build forecast rows ->
upsert into heatwave.forecasts (Supabase). Rate-limit-friendly (few provinces).

Uses DATABASE_URL from .env. Province ids default to a few that exist in the
built province_thresholds.parquet (so p95 features are present).

  .venv\\Scripts\\python.exe scripts\\run_forecast_live.py [id1 id2 ...]
"""
import os
import sys
import warnings
from datetime import datetime, timezone

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def load_env():
    p = os.path.join(REPO, ".env")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    import joblib
    from src.provinces import load_provinces
    from src.db_write import upsert_forecasts
    from pipeline.run_forecast import _real_frame_builder, build_forecast_rows, MODEL_PATH

    ids = [int(a) for a in sys.argv[1:]] or [1, 29, 77]  # Bangkok, Chiang Rai, Narathiwat
    provinces = load_provinces("data/provinces.csv")
    provinces = provinces[provinces["id"].isin(ids)].reset_index(drop=True)
    print(f"provinces: {list(provinces['name_en'])}", flush=True)

    model = joblib.load(MODEL_PATH)  # our own trained artifact (trusted, local)
    thresholds = pd.read_parquet("data/processed/province_thresholds.parquet")

    horizons = range(1, 8)
    generated_at = datetime.now(timezone.utc)
    from pipeline.run_forecast import _bangkok_today
    origin = _bangkok_today()
    builder = _real_frame_builder(origin, history_days=40,
                                  forecast_days=max(horizons) + 1, thresholds=thresholds)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rows = build_forecast_rows(provinces, model, generated_at,
                                   frame_builder=builder, horizons=horizons,
                                   origin_date=origin)
    for w in caught:
        print(f"  [warn] {w.message}", flush=True)

    print(f"built {len(rows)} forecast rows (origin {origin})", flush=True)
    if not rows:
        print("NO ROWS — likely archive/forecast date gap at origin; see warnings", flush=True)
        return 1
    n = upsert_forecasts(rows)
    print(f"upserted {n} rows into heatwave.forecasts", flush=True)
    s = rows[0]
    print(f"  sample: province {s['province_id']} target {s['target_date']} "
          f"p={s['probability']:.3f} risk={s['risk_level']} label={s['predicted_label']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
