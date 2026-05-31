"""Pipeline-status REST endpoint for the Heatwave Cockpit Pipeline tab.

The controller does ``app.include_router(pipeline_api.router)`` — this module
must NOT import or modify server.app.

All paths are relative to the repo root (the server's working directory).
Every branch must return 200; never raise.
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

DATASET_PATH = "data/processed/dataset.parquet"
MODEL_PATH = "models/heatwave_model.pkl"
RUNS_PATH = "experiments/runs.jsonl"


def _fmt_mtime(path: str) -> str:
    """Return a human-readable mtime string, or empty string if file missing."""
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def _dataset_stage() -> dict:
    """Derive real status of the processed dataset."""
    exists = os.path.exists(DATASET_PATH)
    if not exists:
        return {
            "key": "data",
            "label": "Build dataset",
            "status": "missing",
            "detail": "dataset.parquet not found",
            "runnable": True,
            "stage": "build_dataset",
        }
    detail = f"updated {_fmt_mtime(DATASET_PATH)}"
    # Try to get row count cheaply via pyarrow metadata (no full load)
    try:
        import pyarrow.parquet as pq  # type: ignore[import-untyped]
        meta = pq.read_metadata(DATASET_PATH)
        nrows = meta.num_rows
        detail = f"{nrows:,} rows · {detail}"
    except Exception:  # noqa: BLE001 — pyarrow missing or file locked
        pass
    return {
        "key": "data",
        "label": "Build dataset",
        "status": "ready",
        "detail": detail,
        "runnable": True,
        "stage": "build_dataset",
    }


def _gefs_stage() -> dict:
    """Read GEFS store status without launching anything."""
    try:
        from server.gefs_status import gefs_status  # noqa: PLC0415
        gs = gefs_status()
        detail = f"{gs['inits']}/{gs['target']} inits · {gs['rows']:,} rows"
    except Exception:  # noqa: BLE001
        detail = "unavailable"
    return {
        "key": "gefs",
        "label": "GEFS pull",
        "detail": detail,
        "link": "lab",
    }


def _train_stage() -> dict:
    """Status of the most-recently-trained model."""
    exists = os.path.exists(MODEL_PATH)
    if not exists:
        return {
            "key": "train",
            "label": "Train model",
            "status": "missing",
            "detail": "heatwave_model.pkl not found",
            "link": "train",
        }
    return {
        "key": "train",
        "label": "Train model",
        "status": "ready",
        "detail": f"model present · updated {_fmt_mtime(MODEL_PATH)}",
        "link": "train",
    }


def _forecast_stage() -> dict:
    """Detail from the last run in experiments/runs.jsonl."""
    try:
        from pipeline.run_log import read_runs  # noqa: PLC0415
        runs = read_runs()
        if runs:
            last = runs[-1]
            ts = last.get("ts", "")
            trainer = last.get("trainer", "")
            detail = f"last: {trainer} @ {ts}" if trainer else f"last run @ {ts}"
        else:
            detail = "no runs yet"
    except Exception:  # noqa: BLE001
        detail = "unavailable"
    return {
        "key": "forecast",
        "label": "Daily forecast",
        "detail": detail,
        "link": "ops",
    }


def _deploy_stage() -> dict:
    """Whether the production model artifact is present."""
    exists = os.path.exists(MODEL_PATH)
    return {
        "key": "deploy",
        "label": "Promote",
        "status": "ready" if exists else "missing",
        "detail": f"heatwave_model.pkl {'present' if exists else 'absent'}" + (
            f" · {_fmt_mtime(MODEL_PATH)}" if exists else ""
        ),
        "link": "ops",
    }


@router.get("/api/pipeline/status")
async def pipeline_status() -> dict:
    """Return a snapshot of every pipeline stage derived from the filesystem."""
    stages = [
        _dataset_stage(),
        _gefs_stage(),
        _train_stage(),
        _forecast_stage(),
        _deploy_stage(),
    ]
    return {"stages": stages}
