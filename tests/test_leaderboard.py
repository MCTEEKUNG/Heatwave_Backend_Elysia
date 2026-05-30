import json
from pipeline.leaderboard import upsert_model


def test_upsert_replaces_and_resorts(tmp_path):
    p = str(tmp_path / "lb.json")
    upsert_model("xgboost", {"f2": 0.40, "pr_auc": 0.30, "brier": 0.10, "base_rate": 0.15}, n_provinces=20, path=p)
    upsert_model("catboost", {"f2": 0.55, "pr_auc": 0.33, "brier": 0.10, "base_rate": 0.15}, path=p)
    upsert_model("xgboost", {"f2": 0.50, "pr_auc": 0.31, "brier": 0.10, "base_rate": 0.15}, path=p)  # update
    data = json.load(open(p))
    assert [r["model"] for r in data["results"]] == ["catboost", "xgboost"]  # sorted, no dup
    xgb = next(r for r in data["results"] if r["model"] == "xgboost")
    assert xgb["f2"] == 0.50 and xgb["brier_skill_score"] is not None  # updated + BSS derived


def test_lgbm_aliases_to_lightgbm(tmp_path):
    p = str(tmp_path / "lb.json")
    upsert_model("lgbm", {"f2": 0.56, "pr_auc": 0.33, "brier": 0.11, "base_rate": 0.15}, path=p)
    data = json.load(open(p))
    assert data["results"][0]["model"] == "lightgbm"
