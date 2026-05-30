# pipeline/leaderboard.py
"""Upsert one model's row into the bake-off leaderboard so a dashboard training
run keeps the leaderboard as the single source of truth (latest result per
model). Re-sorts by F2 then PR-AUC, matching scripts/bakeoff.py.
"""
import json
import os

LEADERBOARD_PATH = "experiments/results/leaderboard.json"
# dashboard trainer name -> leaderboard model name (bake-off calls it 'lightgbm')
_ALIAS = {"lgbm": "lightgbm"}
_ROW_KEYS = ("f2", "pr_auc", "mcc", "roc_auc", "brier", "threshold",
             "n", "n_pos", "base_rate", "brier_skill_score", "fit_seconds")


def upsert_model(name, metrics, *, n_provinces=None, path=LEADERBOARD_PATH):
    lb_name = _ALIAS.get(name, name)
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    m = dict(metrics)
    # derive Brier skill score if the run didn't include it (lgbm's nested test
    # metrics don't) so the BSS column stays populated.
    if m.get("brier_skill_score") is None and m.get("base_rate") and m.get("brier") is not None:
        base = m["base_rate"]; clim = base * (1 - base)
        if clim:
            m["brier_skill_score"] = 1 - m["brier"] / clim

    results = [r for r in data.get("results", []) if r.get("model") != lb_name]
    results.append({"model": lb_name, **{k: m.get(k) for k in _ROW_KEYS}})
    results.sort(key=lambda r: (r.get("f2") or 0, r.get("pr_auc") or 0), reverse=True)

    data["results"] = results
    data.setdefault("ranked_by", "f2 then pr_auc")
    data.setdefault("split", {"train": "<=2023", "val": "2024", "test": "2025"})
    data.setdefault("dataset", "data/processed/dataset.parquet")
    if n_provinces is not None:
        data["n_provinces"] = n_provinces
    if m.get("n") is not None:
        data["n_test"] = m["n"]
    if m.get("base_rate") is not None:
        data["test_base_rate"] = m["base_rate"]

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return results
