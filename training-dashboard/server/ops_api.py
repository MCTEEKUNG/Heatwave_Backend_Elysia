"""Ops API — model promotion and run history.

Exposes a module-level ``router`` that the controller wires in via::

    app.include_router(ops_api.router)

All path constants are module-level so tests can monkeypatch them cleanly
without touching the real ``models/heatwave_model.pkl``.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.run_log import read_runs

router = APIRouter()

# ---------------------------------------------------------------------------
# Monkeypatchable path constants (tests repoint these to tmp_path)
# ---------------------------------------------------------------------------
DASHBOARD_DIR: str = os.path.join("models", "dashboard")
PRODUCTION_MODEL_PATH: str = os.path.join("models", "heatwave_model.pkl")
MODEL_CARD_PATH: str = os.path.join("models", "model_card.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json_safe(path: str) -> dict[str, Any] | None:
    """Return parsed JSON or None on any error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def _dashboard_model_names() -> list[str]:
    """List names (stem) of .json sidecars inside DASHBOARD_DIR."""
    try:
        entries = os.listdir(DASHBOARD_DIR)
    except OSError:
        return []
    return sorted(
        os.path.splitext(e)[0]
        for e in entries
        if e.endswith(".json") and not e.startswith(".")
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/ops/models")
async def list_models() -> dict[str, Any]:
    """List all dashboard models + the current production model card."""
    models = []
    for name in _dashboard_model_names():
        json_path = os.path.join(DASHBOARD_DIR, f"{name}.json")
        pkl_path = os.path.join(DASHBOARD_DIR, f"{name}.pkl")
        sidecar = _read_json_safe(json_path) or {}
        file_exists = os.path.exists(pkl_path)
        size_mb: float | None = None
        if file_exists:
            try:
                size_mb = round(os.path.getsize(pkl_path) / (1024 * 1024), 3)
            except OSError:
                pass
        models.append(
            {
                "name": name,
                "metrics": sidecar,
                "file_exists": file_exists,
                "size_mb": size_mb,
            }
        )

    production: dict[str, Any] | None = _read_json_safe(MODEL_CARD_PATH)
    return {"models": models, "production": production}


class PromoteBody(BaseModel):
    name: str


@router.post("/api/ops/promote")
async def promote_model(body: PromoteBody) -> dict[str, Any]:
    """Copy a dashboard model to the production slot.

    ``name`` is validated against the set of existing dashboard .pkl files
    (strict whitelist) before any path is constructed from it.
    """
    # Build whitelist from what actually exists on disk — never trust raw input.
    allowed = {n for n in _dashboard_model_names()
               if os.path.exists(os.path.join(DASHBOARD_DIR, f"{n}.pkl"))}
    if body.name not in allowed:
        raise HTTPException(status_code=404, detail=f"unknown model: {body.name!r}")

    src_path = os.path.join(DASHBOARD_DIR, f"{body.name}.pkl")
    shutil.copy2(src_path, PRODUCTION_MODEL_PATH)

    # Write / update the model card with promotion provenance.
    sidecar = _read_json_safe(os.path.join(DASHBOARD_DIR, f"{body.name}.json")) or {}
    card: dict[str, Any] = {
        "promoted_from": body.name,
        "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_metrics": sidecar,
    }
    os.makedirs(os.path.dirname(MODEL_CARD_PATH) or ".", exist_ok=True)
    with open(MODEL_CARD_PATH, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)

    return {"promoted": True, "name": body.name, "target": PRODUCTION_MODEL_PATH}


@router.get("/api/ops/runs")
async def ops_runs() -> dict[str, Any]:
    """Most-recent-first run history (last 50 entries)."""
    return {"runs": list(reversed(read_runs()))[:50]}
