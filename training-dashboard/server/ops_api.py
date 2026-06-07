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
    force: bool = False


@router.post("/api/ops/promote")
async def promote_model(body: PromoteBody) -> dict[str, Any]:
    """Promote a dashboard model to production via the shared safe-promote core
    (coverage guard + automatic backup). ``name`` is whitelisted against existing
    dashboard .pkl files before any path is constructed from it.
    """
    from src.promote import promote as _promote

    allowed = {n for n in _dashboard_model_names()
               if os.path.exists(os.path.join(DASHBOARD_DIR, f"{n}.pkl"))}
    if body.name not in allowed:
        raise HTTPException(status_code=404, detail=f"unknown model: {body.name!r}")

    result = _promote(body.name, dashboard_dir=DASHBOARD_DIR,
                      prod_model_path=PRODUCTION_MODEL_PATH,
                      model_card_path=MODEL_CARD_PATH, force=body.force)
    if not result["ok"]:
        # 409 Conflict: a known province-coverage regression blocked by the guard.
        raise HTTPException(status_code=409, detail=result["reason"])
    return {"promoted": True, "name": body.name,
            "warnings": result.get("warnings", []),
            "backups": result.get("backups", [])}


@router.post("/api/ops/rollback")
async def rollback_model() -> dict[str, Any]:
    """Restore the most recent production model + model-card backup."""
    from src.promote import rollback as _rollback

    result = _rollback(prod_model_path=PRODUCTION_MODEL_PATH,
                       model_card_path=MODEL_CARD_PATH)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result.get("reason", "no backup"))
    return result


@router.get("/api/ops/runs")
async def ops_runs() -> dict[str, Any]:
    """Most-recent-first run history (last 50 entries)."""
    return {"runs": list(reversed(read_runs()))[:50]}
