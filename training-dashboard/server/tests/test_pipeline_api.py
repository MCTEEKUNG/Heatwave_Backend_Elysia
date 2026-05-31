"""Tests for server/pipeline_api.py.

Uses a local FastAPI app rather than importing server.app (which is a
forbidden file), following the same pattern as other server tests.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.pipeline_api import router
from server.stages import parse_last_line

# ---------------------------------------------------------------------------
# Unit tests for parse_last_line
# ---------------------------------------------------------------------------

def test_parse_last_line_returns_last_nonempty():
    result = parse_last_line(["first line\n", "  \n", "last line\n"])
    assert result == {"summary": "last line"}


def test_parse_last_line_strips_whitespace():
    result = parse_last_line(["  trimmed  \n"])
    assert result == {"summary": "trimmed"}


def test_parse_last_line_empty_input():
    result = parse_last_line([])
    assert result == {}


def test_parse_last_line_only_blank_lines():
    result = parse_last_line(["  \n", "\n", "   \n"])
    assert result == {}


# ---------------------------------------------------------------------------
# Integration tests for /api/pipeline/status
# ---------------------------------------------------------------------------

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app)


def test_pipeline_status_returns_200():
    r = _client.get("/api/pipeline/status")
    assert r.status_code == 200


def test_pipeline_status_has_stages_list():
    r = _client.get("/api/pipeline/status")
    body = r.json()
    assert "stages" in body
    assert isinstance(body["stages"], list)


def test_pipeline_status_stages_are_dicts():
    r = _client.get("/api/pipeline/status")
    stages = r.json()["stages"]
    for stage in stages:
        assert isinstance(stage, dict)


def test_pipeline_status_has_expected_keys():
    """Every stage must have at least 'key' and 'label'."""
    r = _client.get("/api/pipeline/status")
    stages = r.json()["stages"]
    # Must have at least the 5 defined stages
    assert len(stages) >= 5
    for stage in stages:
        assert "key" in stage, f"missing 'key' in {stage}"
        assert "label" in stage, f"missing 'label' in {stage}"


def test_pipeline_status_has_data_stage():
    r = _client.get("/api/pipeline/status")
    stages = r.json()["stages"]
    keys = [s["key"] for s in stages]
    assert "data" in keys


def test_pipeline_status_runnable_stage_has_stage_field():
    """The build_dataset stage card must expose a 'stage' field for Run dispatch."""
    r = _client.get("/api/pipeline/status")
    stages = r.json()["stages"]
    runnable = [s for s in stages if s.get("runnable")]
    assert len(runnable) >= 1
    for s in runnable:
        assert "stage" in s, f"runnable stage missing 'stage': {s}"


def test_pipeline_status_always_200_when_files_missing(tmp_path, monkeypatch):
    """Endpoint must return 200 even when dataset and model files don't exist."""
    import server.pipeline_api as pa
    monkeypatch.setattr(pa, "DATASET_PATH", str(tmp_path / "nonexistent.parquet"))
    monkeypatch.setattr(pa, "MODEL_PATH", str(tmp_path / "no_model.pkl"))
    # Rebuild a fresh client with patched module state
    from fastapi import FastAPI as FA
    from fastapi.testclient import TestClient as TC
    local_app = FA()
    local_app.include_router(router)
    with TC(local_app) as c:
        r = c.get("/api/pipeline/status")
    assert r.status_code == 200
    body = r.json()
    assert "stages" in body
    data_stage = next(s for s in body["stages"] if s["key"] == "data")
    assert data_stage["status"] == "missing"
