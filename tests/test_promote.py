"""Tests for src.promote — the single promotion core (guard + backup + rollback)
shared by the dashboard OpsPanel and the CLI."""
import json

import pytest

from src.promote import promote, rollback


def _setup(tmp_path, cand_prov=77, prod_prov=77, name="lgbm"):
    dash = tmp_path / "dashboard"
    dash.mkdir()
    (dash / f"{name}.pkl").write_bytes(b"CANDIDATE")
    sidecar = {"class": "CalibratedModel", "model_version": "lgbm-v1", "metrics": {}}
    if cand_prov is not None:
        sidecar["metrics"]["n_provinces"] = cand_prov
    (dash / f"{name}.json").write_text(json.dumps(sidecar))
    prod = tmp_path / "heatwave_model.pkl"
    prod.write_bytes(b"OLDPROD")
    card = tmp_path / "model_card.json"
    cardobj = {"data": {}}
    if prod_prov is not None:
        cardobj["data"]["n_provinces"] = prod_prov
    card.write_text(json.dumps(cardobj))
    return {"name": name, "dashboard_dir": str(dash),
            "prod_model_path": str(prod), "model_card_path": str(card)}


def test_promote_copies_candidate_and_writes_card(tmp_path):
    a = _setup(tmp_path)
    r = promote(**a)
    assert r["ok"] is True
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"CANDIDATE"
    card = json.loads((tmp_path / "model_card.json").read_text())
    assert card["promoted_from"] == "lgbm"
    assert card["data"]["n_provinces"] == 77


def test_guard_refuses_known_regression_and_leaves_prod_untouched(tmp_path):
    a = _setup(tmp_path, cand_prov=20, prod_prov=77)
    r = promote(**a)
    assert r["ok"] is False
    assert "coverage" in r["reason"].lower() or "province" in r["reason"].lower()
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"OLDPROD"  # untouched
    assert list(tmp_path.glob("heatwave_model.pkl.bak-*")) == []          # no backup


def test_force_overrides_guard(tmp_path):
    a = _setup(tmp_path, cand_prov=20, prod_prov=77)
    r = promote(force=True, **a)
    assert r["ok"] is True
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"CANDIDATE"


def test_guard_allows_with_warning_when_coverage_unknown(tmp_path):
    a = _setup(tmp_path, cand_prov=None, prod_prov=77)
    r = promote(**a)
    assert r["ok"] is True
    assert r["warnings"]  # warned that coverage couldn't be verified
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"CANDIDATE"


def test_backup_created_with_old_contents(tmp_path):
    a = _setup(tmp_path)
    promote(**a)
    baks = list(tmp_path.glob("heatwave_model.pkl.bak-*"))
    assert len(baks) == 1
    assert baks[0].read_bytes() == b"OLDPROD"


def test_dry_run_changes_nothing(tmp_path):
    a = _setup(tmp_path)
    r = promote(dry_run=True, **a)
    assert r["ok"] is True and r.get("dry_run") is True
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"OLDPROD"
    assert list(tmp_path.glob("heatwave_model.pkl.bak-*")) == []


def test_unknown_model_name_refused(tmp_path):
    a = _setup(tmp_path)
    a["name"] = "does_not_exist"
    r = promote(**a)
    assert r["ok"] is False
    assert "unknown" in r["reason"].lower()


def test_rollback_restores_latest_backup(tmp_path):
    a = _setup(tmp_path)
    promote(**a)
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"CANDIDATE"
    rb = rollback(prod_model_path=a["prod_model_path"],
                  model_card_path=a["model_card_path"])
    assert rb["ok"] is True
    assert (tmp_path / "heatwave_model.pkl").read_bytes() == b"OLDPROD"  # restored


def test_rollback_no_backup_returns_false(tmp_path):
    a = _setup(tmp_path)
    rb = rollback(prod_model_path=a["prod_model_path"],
                  model_card_path=a["model_card_path"])
    assert rb["ok"] is False
