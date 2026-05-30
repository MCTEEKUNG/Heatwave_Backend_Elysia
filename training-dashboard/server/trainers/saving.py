"""Persist a dashboard-trained model.

Saves to ``models/dashboard/<name>.pkl`` -- DELIBERATELY separate from the
curated production artifact ``models/heatwave_model.pkl`` (written by
scripts/train_production.py), so a casual dashboard run never clobbers the
model that feeds run_forecast. Bundles are always ``src.model.CalibratedModel``
so they load + predict through the same path production uses.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

DASHBOARD_DIR = "models/dashboard"


def save_dashboard_model(name: str, bundle, metrics: dict) -> dict:
    """joblib-dump ``bundle`` to models/dashboard/<name>.pkl + a <name>.json
    sidecar (scalar metrics + provenance). Returns a small dict for the report."""
    import joblib

    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    pkl = os.path.join(DASHBOARD_DIR, f"{name}.pkl")
    joblib.dump(bundle, pkl)

    scalars = {k: v for k, v in (metrics or {}).items() if isinstance(v, (int, float, bool))}
    meta = {
        "trainer": name,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": getattr(bundle, "model_version", name),
        "class": type(bundle).__name__,
        "metrics": scalars,
    }
    with open(os.path.join(DASHBOARD_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return {"name": name, "file": f"{name}.pkl",
            "path": pkl.replace("\\", "/"),
            "size_kb": round(os.path.getsize(pkl) / 1024, 1)}
