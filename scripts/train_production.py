"""Train the production-CANDIDATE model, save it with provenance, and verify the
real consumption path actually runs.

Why "candidate": trained on the currently-built provinces (20/77), so it is a
documented, reproducible artifact -- not the full-coverage production model.

Steps:
  1. train_model on data/processed/dataset.parquet -> CalibratedModel bundle
  2. joblib.dump -> models/heatwave_model.pkl  (gitignored; reproducible)
  3. write models/model_card.json provenance (data version, n_provinces, git
     sha, date, test metrics, threshold)
  4. VERIFY: joblib.load(...) -> build_forecast_rows(stub frame_builder) so a
     pickle / class-resolution / feature-column mismatch is caught HERE, not in
     production.

Run from repo root:
  .venv\\Scripts\\python.exe scripts\\train_production.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.train import train_model, MODEL_PATH
from pipeline.run_forecast import build_forecast_rows
from src.swbgt import swbgt

DATASET = "data/processed/dataset.parquet"
PROVINCES = "data/provinces.csv"
CARD_PATH = "models/model_card.json"


def _git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return None


def _synthetic_daily(province_id, lat, lon, end, n_history=45, n_forecast=7, seed=0):
    """A per-province daily frame ending at `end` + a forecast tail, mirroring the
    real schema -- enough to exercise build_forecast_rows with no network."""
    rng = np.random.default_rng(seed)
    total = n_history + n_forecast + 1
    times = pd.date_range(end - pd.Timedelta(days=n_history), periods=total, freq="D")
    tmax = 34 + 3 * np.sin(np.arange(total) / 5.0) + rng.normal(0, 0.3, total)
    rh = 60 + 5 * np.cos(np.arange(total) / 4.0)
    df = pd.DataFrame({
        "province_id": province_id, "time": times, "swbgt_max": swbgt(tmax, rh),
        "p95": 31.0, "temperature_2m_max": tmax, "relative_humidity_2m_mean": rh,
        "lat": lat, "lon": lon,
    })
    df["is_hot"] = (df["swbgt_max"] >= df["p95"]).astype(int)
    grp = (df["is_hot"] != df["is_hot"].shift()).cumsum()
    df["heatwave"] = ((df["is_hot"] == 1) & (df.groupby(grp)["is_hot"].transform("size") >= 2)).astype(int)
    return df


def main():
    if not os.path.exists(DATASET):
        print(f"missing {DATASET} -- run scripts/build_full_dataset.py first")
        return 1

    ds = pd.read_parquet(DATASET)
    if "lat" not in ds.columns:
        prov = pd.read_csv(PROVINCES)[["id", "lat", "lon"]]
        ds = ds.merge(prov, left_on="province_id", right_on="id", how="left").drop(columns=["id"])
    n_prov = int(ds["province_id"].nunique())

    print(f"training on {n_prov} provinces, {len(ds)} rows ...", flush=True)
    bundle, report = train_model(ds)

    os.makedirs("models", exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    size_kb = round(os.path.getsize(MODEL_PATH) / 1024, 1)
    print(f"saved {MODEL_PATH} ({size_kb} KB)", flush=True)

    card = {
        "model": "heatwave-lgbm",
        "stage": "production-candidate",
        "model_version": bundle.model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "data": {"source": "open-meteo-archive (ERA5)", "n_provinces": n_prov,
                 "coverage": f"{n_prov}/77", "period": "1991-2025",
                 "label": "sWBGT>=p95(doy) & >=2-day run (daily-aggregate, see DATA.md)"},
        "split": {"train": "<=2023", "val": "2024", "test": "2025",
                  "n_train": report["n_train"], "n_val": report["n_val"], "n_test": report["n_test"]},
        "operating_point": {"threshold": round(float(report["threshold"]), 4), "selected_on": "validation(2024)"},
        "test_metrics": {k: round(float(v), 4) for k, v in report.get("test", {}).items()
                         if isinstance(v, (int, float))},
        "n_features": len(report["features"]),
        "artifact": {"path": MODEL_PATH, "format": "joblib", "size_kb": size_kb,
                     "class": "src.model.CalibratedModel"},
    }
    with open(CARD_PATH, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"wrote {CARD_PATH}", flush=True)

    # ---- VERIFY the real consumption path with the SAVED bundle ----
    print("\nverifying consumption path (load -> predict -> build_forecast_rows) ...", flush=True)
    # Safe: loading the artifact we just wrote above (our own trusted, local
    # joblib bundle -- the project's standard model format, same as run_forecast).
    loaded = joblib.load(MODEL_PATH)
    provinces = pd.read_csv(PROVINCES)[["id", "lat", "lon"]].head(3)
    end = pd.Timestamp("2025-06-01")
    gen_at = datetime(2025, 6, 1, 6, 0, tzinfo=timezone.utc)

    def builder(p):
        return _synthetic_daily(int(p["id"]), p["lat"], p["lon"], end, seed=int(p["id"]))

    rows = build_forecast_rows(provinces, loaded, gen_at,
                               frame_builder=builder, origin_date=end.date())
    assert rows, "consumption FAILED: no forecast rows produced"
    assert len(rows) == 3 * 7, f"expected 21 rows, got {len(rows)}"
    for r in rows:
        assert 0.0 <= r["probability"] <= 1.0
        assert r["risk_level"] and r["model_version"]
    sample = rows[0]
    print(f"  OK: {len(rows)} rows; sample prob={sample['probability']:.3f} "
          f"risk={sample['risk_level']} label={sample['predicted_label']}")
    print("\nPRODUCTION CANDIDATE READY: artifact saved + consumption path verified")
    print(f"  test F2={card['test_metrics'].get('f2')}  threshold={card['operating_point']['threshold']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
