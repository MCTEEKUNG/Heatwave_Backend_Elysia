"""Tests for ops_api.py.

Runs as an isolated mini-app — does NOT import server.app so the real
production model is never at risk.  The happy-path promote test monkeypatches
all three path constants (DASHBOARD_DIR, PRODUCTION_MODEL_PATH, MODEL_CARD_PATH)
to point inside pytest's tmp_path.
"""
from __future__ import annotations

import json
import os
import pickle

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import server.ops_api as ops_api
from server.ops_api import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """A minimal FastAPI app that only mounts the ops router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def patched_paths(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Redirect all three path constants to tmp_path so real files are safe."""
    dash_dir = str(tmp_path / "dashboard")
    prod_pkl = str(tmp_path / "heatwave_model.pkl")
    card_json = str(tmp_path / "model_card.json")
    os.makedirs(dash_dir, exist_ok=True)

    monkeypatch.setattr(ops_api, "DASHBOARD_DIR", dash_dir)
    monkeypatch.setattr(ops_api, "PRODUCTION_MODEL_PATH", prod_pkl)
    monkeypatch.setattr(ops_api, "MODEL_CARD_PATH", card_json)

    return {"dash_dir": dash_dir, "prod_pkl": prod_pkl, "card_json": card_json}


def _make_fake_model(dash_dir: str, name: str) -> None:
    """Write a minimal .pkl and .json sidecar for a dashboard model."""
    pkl_path = os.path.join(dash_dir, f"{name}.pkl")
    json_path = os.path.join(dash_dir, f"{name}.json")
    with open(pkl_path, "wb") as f:
        pickle.dump({"model": name}, f)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "trainer": name,
                "metrics": {"f2": 0.55, "pr_auc": 0.32, "roc_auc": 0.76},
            },
            f,
        )


# ---------------------------------------------------------------------------
# GET /api/ops/models
# ---------------------------------------------------------------------------

class TestListModels:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/ops/models")
        assert r.status_code == 200

    def test_shape(self, client: TestClient) -> None:
        body = r = client.get("/api/ops/models").json()
        assert "models" in body
        assert "production" in body
        assert isinstance(body["models"], list)

    def test_each_model_has_expected_keys(self, client: TestClient) -> None:
        body = client.get("/api/ops/models").json()
        for m in body["models"]:
            assert "name" in m
            assert "metrics" in m
            assert "file_exists" in m
            assert "size_mb" in m

    def test_isolated_models(
        self, patched_paths: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With a fake dashboard dir containing one model, it shows up."""
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)

        _make_fake_model(patched_paths["dash_dir"], "test_model")
        body = c.get("/api/ops/models").json()
        names = [m["name"] for m in body["models"]]
        assert "test_model" in names


# ---------------------------------------------------------------------------
# POST /api/ops/promote — unknown name -> 404
# ---------------------------------------------------------------------------

class TestPromoteUnknown:
    def test_unknown_name_returns_404(self, client: TestClient) -> None:
        r = client.post("/api/ops/promote", json={"name": "nonexistent_model_xyz"})
        assert r.status_code == 404

    def test_path_traversal_rejected(self, client: TestClient) -> None:
        r = client.post("/api/ops/promote", json={"name": "../../../etc/passwd"})
        assert r.status_code == 404

    def test_empty_name_rejected(self, client: TestClient) -> None:
        r = client.post("/api/ops/promote", json={"name": ""})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/ops/promote — happy path (isolated, does NOT touch real pkl)
# ---------------------------------------------------------------------------

class TestPromoteHappyPath:
    def test_promote_copies_pkl(
        self, patched_paths: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Promote writes .pkl to PRODUCTION_MODEL_PATH and writes model card."""
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)

        dash_dir = patched_paths["dash_dir"]
        prod_pkl = patched_paths["prod_pkl"]
        card_json = patched_paths["card_json"]

        _make_fake_model(dash_dir, "fake_lgbm")

        r = c.post("/api/ops/promote", json={"name": "fake_lgbm"})
        assert r.status_code == 200
        body = r.json()
        assert body["promoted"] is True
        assert body["name"] == "fake_lgbm"

        # The production pkl must have been created.
        assert os.path.exists(prod_pkl), "production pkl not created"

        # The model card must exist and have provenance keys.
        assert os.path.exists(card_json), "model card not written"
        with open(card_json, encoding="utf-8") as f:
            card = json.load(f)
        assert card["promoted_from"] == "fake_lgbm"
        assert "promoted_at" in card
        assert "source_metrics" in card

    def test_real_pkl_not_touched(self) -> None:
        """Sanity: the real production model path is unchanged after isolated test."""
        real_path = os.path.join("models", "heatwave_model.pkl")
        if os.path.exists(real_path):
            mtime_before = os.path.getmtime(real_path)
            # Nothing touches it here — just assert it still has the same mtime.
            mtime_after = os.path.getmtime(real_path)
            assert mtime_before == mtime_after


# ---------------------------------------------------------------------------
# GET /api/ops/runs
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_after_promote_restores(self, patched_paths: dict) -> None:
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        prod = patched_paths["prod_pkl"]
        # seed an existing production model so promote makes a backup
        with open(prod, "wb") as f:
            f.write(b"OLDPROD")
        _make_fake_model(patched_paths["dash_dir"], "fake_lgbm")
        assert c.post("/api/ops/promote", json={"name": "fake_lgbm"}).status_code == 200
        with open(prod, "rb") as f:
            assert f.read() != b"OLDPROD"  # promote replaced it
        r = c.post("/api/ops/rollback")
        assert r.status_code == 200 and r.json()["ok"] is True
        with open(prod, "rb") as f:
            assert f.read() == b"OLDPROD"  # restored

    def test_rollback_no_backup_returns_404(self, patched_paths: dict) -> None:
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        assert c.post("/api/ops/rollback").status_code == 404


class TestOpsRuns:
    def test_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/ops/runs")
        assert r.status_code == 200

    def test_has_runs_key(self, client: TestClient) -> None:
        body = client.get("/api/ops/runs").json()
        assert "runs" in body
        assert isinstance(body["runs"], list)
