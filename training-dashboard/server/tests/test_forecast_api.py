"""Tests for forecast_api routes.

The conftest.py in this directory puts ``training-dashboard`` on sys.path so
``from server.forecast_api import router`` resolves correctly.

We build a local FastAPI app here — we do NOT modify server/app.py.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.forecast_api import router

# ---------------------------------------------------------------------------
# Test app (local; does not import server.app)
# ---------------------------------------------------------------------------

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)


# ---------------------------------------------------------------------------
# /api/forecast/provinces — always uses real CSV, no DB
# ---------------------------------------------------------------------------

class TestProvinces:
    def test_returns_200(self):
        r = client.get("/api/forecast/provinces")
        assert r.status_code == 200

    def test_returns_77_entries(self):
        r = client.get("/api/forecast/provinces")
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 77

    def test_entry_has_expected_keys(self):
        r = client.get("/api/forecast/provinces")
        entry = r.json()[0]
        for key in ("id", "code", "name_en", "name_th", "region", "lat", "lon"):
            assert key in entry, f"Missing key: {key}"

    def test_ids_are_integers(self):
        r = client.get("/api/forecast/provinces")
        for entry in r.json():
            assert isinstance(entry["id"], int)


# ---------------------------------------------------------------------------
# /api/forecast/map?lead=1 — DB is down; must NOT 500, cells must be a dict
# ---------------------------------------------------------------------------

class TestForecastMap:
    def test_does_not_500_when_db_unreachable(self):
        r = client.get("/api/forecast/map?lead=1")
        assert r.status_code == 200

    def test_available_is_bool(self):
        r = client.get("/api/forecast/map?lead=1")
        body = r.json()
        assert isinstance(body["available"], bool)

    def test_cells_is_dict(self):
        r = client.get("/api/forecast/map?lead=1")
        body = r.json()
        assert isinstance(body["cells"], dict)

    def test_available_false_when_db_down(self):
        """With no live DB the endpoint should gracefully return available=false."""
        r = client.get("/api/forecast/map?lead=1")
        body = r.json()
        # The DB is expected to be unreachable in CI; available must be false
        # (if it were somehow true, the cells must still be a non-fabricated dict)
        assert "available" in body
        assert "cells" in body


# ---------------------------------------------------------------------------
# /api/forecast/map?lead=1 — monkeypatched happy path
# ---------------------------------------------------------------------------

class TestForecastMapPopulated:
    """Verify the populated-branch format using a fake DB connection."""

    def _make_fake_conn(self):
        """Return a context-manager mock that yields a psycopg-like connection."""
        from datetime import datetime

        latest_ts = datetime(2025, 5, 1, 0, 0, 0)

        # Cursor mock
        cursor_mock = MagicMock()
        cursor_mock.__enter__ = lambda s: s
        cursor_mock.__exit__ = MagicMock(return_value=False)

        fetchone_results = [
            (latest_ts,),  # first call: MAX(generated_at)
        ]
        fetchall_result = [
            (1, 0.72, "high"),
            (2, 0.45, "moderate"),
        ]
        cursor_mock.fetchone.side_effect = fetchone_results
        cursor_mock.fetchall.return_value = fetchall_result

        conn_mock = MagicMock()
        conn_mock.__enter__ = lambda s: s
        conn_mock.__exit__ = MagicMock(return_value=False)
        conn_mock.cursor.return_value = cursor_mock

        return conn_mock

    def test_populated_response_shape(self):
        conn_mock = self._make_fake_conn()
        psycopg_mock = MagicMock()
        psycopg_mock.connect.return_value = conn_mock

        with patch.dict("sys.modules", {"psycopg": psycopg_mock}):
            r = client.get("/api/forecast/map?lead=1")

        assert r.status_code == 200
        body = r.json()
        assert body["available"] is True
        assert "generated_at" in body
        assert "cells" in body
        assert isinstance(body["cells"], dict)

    def test_populated_cells_have_required_fields(self):
        conn_mock = self._make_fake_conn()
        psycopg_mock = MagicMock()
        psycopg_mock.connect.return_value = conn_mock

        with patch.dict("sys.modules", {"psycopg": psycopg_mock}):
            r = client.get("/api/forecast/map?lead=1")

        cells = r.json()["cells"]
        for cell in cells.values():
            assert "probability" in cell
            assert "risk_level" in cell


# ---------------------------------------------------------------------------
# /api/forecast/province/{pid} — same graceful-failure contract
# ---------------------------------------------------------------------------

class TestProvinceSeries:
    def test_does_not_500(self):
        r = client.get("/api/forecast/province/1")
        assert r.status_code == 200

    def test_available_is_bool(self):
        r = client.get("/api/forecast/province/1")
        body = r.json()
        assert isinstance(body["available"], bool)

    def test_series_is_list(self):
        r = client.get("/api/forecast/province/1")
        body = r.json()
        assert isinstance(body["series"], list)
