"""Forecast API routes for the Heatwave Cockpit dashboard.

Exposes a module-level ``router`` (APIRouter) that the controller mounts with::

    from server import forecast_api
    app.include_router(forecast_api.router)

All routes use full paths (/api/forecast/...) so they are addressable without
an additional prefix.

DB contract:  heatwave.forecasts columns:
  province_id, target_date, generated_at, horizon_days,
  probability, predicted_label, swbgt_pred, risk_level, model_version

The DB may be unreachable.  Every route that touches the DB returns
  {"available": false, "reason": "<short>", ...}
and NEVER raises a 500 or fabricates cell values.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the repo root regardless of cwd.

    This file lives at  <repo>/training-dashboard/server/forecast_api.py
    so  .parents[2]  is the repo root.
    """
    return Path(__file__).resolve().parents[2]


def _get_database_url() -> str | None:
    """Return DATABASE_URL from the environment or the repo-root .env file."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return None
    try:
        with env_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    value = line[len("DATABASE_URL="):]
                    # Strip surrounding quotes if present
                    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                        value = value[1:-1]
                    return value or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _provinces_path() -> Path:
    return _repo_root() / "data" / "provinces.csv"


def _load_provinces() -> list[dict[str, Any]]:
    path = _provinces_path()
    provinces: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            provinces.append({
                "id": int(row["id"]),
                "code": row["code"],
                "name_en": row["name_en"],
                "name_th": row["name_th"],
                "region": row["region"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            })
    return provinces


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/forecast/provinces")
async def get_provinces() -> list[dict[str, Any]]:
    """Return all 77 provinces from the local CSV.  Always available."""
    return _load_provinces()


@router.get("/api/forecast/map")
async def get_forecast_map(lead: int = 1) -> dict[str, Any]:
    """Return risk/probability cells for each province at a given lead day.

    On any failure (no DB URL, auth error, no rows) returns::

        {"available": false, "reason": "...", "cells": {}}

    Never 500, never fabricates cells.
    """
    db_url = _get_database_url()
    if not db_url:
        return {"available": False, "reason": "DATABASE_URL not configured", "cells": {}}

    try:
        import psycopg  # lazy import; psycopg v3

        with psycopg.connect(db_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                # Identify the latest generated_at snapshot
                cur.execute(
                    "SELECT MAX(generated_at) FROM heatwave.forecasts"
                )
                row = cur.fetchone()
                if row is None or row[0] is None:
                    return {
                        "available": False,
                        "reason": "No forecast rows in DB",
                        "cells": {},
                    }
                latest_ts = row[0]

                cur.execute(
                    """
                    SELECT province_id, probability, risk_level
                    FROM heatwave.forecasts
                    WHERE generated_at = %s AND horizon_days = %s
                    """,
                    (latest_ts, lead),
                )
                rows = cur.fetchall()

        if not rows:
            return {
                "available": False,
                "reason": f"No rows for horizon_days={lead} in latest snapshot",
                "generated_at": latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts),
                "cells": {},
            }

        cells: dict[str, dict[str, Any]] = {}
        for province_id, probability, risk_level in rows:
            cells[str(province_id)] = {
                "probability": float(probability) if probability is not None else None,
                "risk_level": risk_level,
            }

        return {
            "available": True,
            "generated_at": latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts),
            "cells": cells,
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": str(exc)[:200],
            "cells": {},
        }


@router.get("/api/forecast/province/{pid}")
async def get_province_series(pid: int) -> dict[str, Any]:
    """Return per-horizon forecast series for one province (latest generated_at).

    Returns::

        {
          "available": bool,
          "series": [{"horizon_days": k, "target_date": ..., "probability": ...,
                      "risk_level": ..., "swbgt_pred": ...}]
        }

    On failure: available=false, series=[].
    """
    db_url = _get_database_url()
    if not db_url:
        return {"available": False, "reason": "DATABASE_URL not configured", "series": []}

    try:
        import psycopg  # lazy import; psycopg v3

        with psycopg.connect(db_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MAX(generated_at) FROM heatwave.forecasts"
                )
                row = cur.fetchone()
                if row is None or row[0] is None:
                    return {"available": False, "reason": "No forecast rows in DB", "series": []}
                latest_ts = row[0]

                cur.execute(
                    """
                    SELECT horizon_days, target_date, probability, risk_level, swbgt_pred
                    FROM heatwave.forecasts
                    WHERE generated_at = %s AND province_id = %s
                    ORDER BY horizon_days
                    """,
                    (latest_ts, pid),
                )
                rows = cur.fetchall()

        if not rows:
            return {
                "available": False,
                "reason": f"No rows for province_id={pid} in latest snapshot",
                "series": [],
            }

        series = []
        for horizon_days, target_date, probability, risk_level, swbgt_pred in rows:
            series.append({
                "horizon_days": horizon_days,
                "target_date": target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date),
                "probability": float(probability) if probability is not None else None,
                "risk_level": risk_level,
                "swbgt_pred": float(swbgt_pred) if swbgt_pred is not None else None,
            })

        return {"available": True, "series": series}

    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": str(exc)[:200],
            "series": [],
        }
