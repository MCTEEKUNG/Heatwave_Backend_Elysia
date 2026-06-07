"""Single promotion core — shared by the dashboard OpsPanel and the CLI.

Promote a dashboard model (`models/dashboard/<name>.pkl`) into the production slot
(`models/heatwave_model.pkl`) with three production-grade safeguards:
  * COVERAGE GUARD — block a *known* province-coverage regression (e.g. replacing a
    77-province model with a 20-province one). Unknown coverage on either side is
    allowed but warned (never silently shrink coverage; never block on missing info).
  * BACKUP — every replace first copies the existing artifact + card to `*.bak-<ts>`.
  * ROLLBACK — restore the most recent backup.

Pure file + JSON operations (provenance comes from the sidecar, so no model load
is needed). All paths are parameters so the dashboard, CLI, and tests inject theirs.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
from datetime import datetime, timezone

DASHBOARD_DIR = os.path.join("models", "dashboard")
PROD_MODEL_PATH = os.path.join("models", "heatwave_model.pkl")
MODEL_CARD_PATH = os.path.join("models", "model_card.json")


def _read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _n_provinces(sidecar_or_card: dict | None) -> int | None:
    """Pull n_provinces from a dashboard sidecar (metrics.n_provinces) or a
    production card (data.n_provinces / top-level)."""
    if not sidecar_or_card:
        return None
    for container in (sidecar_or_card.get("metrics"), sidecar_or_card.get("data"),
                      sidecar_or_card):
        if isinstance(container, dict) and isinstance(
                container.get("n_provinces"), (int, float)):
            return int(container["n_provinces"])
    return None


def latest_backup(path: str) -> str | None:
    """Most recent `<path>.bak-<stamp>` (lexical sort works: ISO-ish UTC stamps)."""
    baks = sorted(glob.glob(f"{path}.bak-*"))
    return baks[-1] if baks else None


def promote(name: str, *, dashboard_dir: str = DASHBOARD_DIR,
            prod_model_path: str = PROD_MODEL_PATH,
            model_card_path: str = MODEL_CARD_PATH,
            force: bool = False, dry_run: bool = False) -> dict:
    """Promote dashboard model ``name`` to production. Returns a result dict with
    ``ok`` and (on success) ``warnings``/``backups``, or (on refusal) ``reason``."""
    cand_pkl = os.path.join(dashboard_dir, f"{name}.pkl")
    if not os.path.isfile(cand_pkl):
        return {"ok": False, "reason": f"unknown model: {name!r}"}

    sidecar = _read_json(os.path.join(dashboard_dir, f"{name}.json")) or {}
    cand_prov = _n_provinces(sidecar)
    prod_card = _read_json(model_card_path)
    prod_prov = _n_provinces(prod_card)

    warnings: list[str] = []
    # COVERAGE GUARD: block only a *known* regression.
    if cand_prov is not None and prod_prov is not None and cand_prov < prod_prov:
        if not force:
            return {"ok": False, "reason": (
                f"coverage regression: candidate covers {cand_prov} provinces < "
                f"production {prod_prov}. Pass force=True to override.")}
        warnings.append(f"forced coverage regression {prod_prov} -> {cand_prov}")
    elif cand_prov is None or prod_prov is None:
        warnings.append("province coverage could not be verified from metadata")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new_card = {
        "promoted_from": name,
        "promoted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": sidecar.get("model_version", name),
        "class": sidecar.get("class"),
        "source_metrics": sidecar.get("metrics", {}),
        "data": {"n_provinces": cand_prov},
    }

    if dry_run:
        return {"ok": True, "dry_run": True, "name": name,
                "card": new_card, "warnings": warnings}

    backups: list[str] = []
    for path in (prod_model_path, model_card_path):
        if os.path.isfile(path):
            bak = f"{path}.bak-{stamp}"
            shutil.copy2(path, bak)
            backups.append(bak)

    os.makedirs(os.path.dirname(prod_model_path) or ".", exist_ok=True)
    shutil.copy2(cand_pkl, prod_model_path)
    with open(model_card_path, "w", encoding="utf-8") as f:
        json.dump(new_card, f, indent=2)

    return {"ok": True, "name": name, "target": prod_model_path,
            "backups": backups, "warnings": warnings}


def rollback(*, prod_model_path: str = PROD_MODEL_PATH,
             model_card_path: str = MODEL_CARD_PATH) -> dict:
    """Restore the most recent backup of the production model + card."""
    restored = []
    for path in (prod_model_path, model_card_path):
        bak = latest_backup(path)
        if bak:
            shutil.copy2(bak, path)
            restored.append({"path": path, "from": bak})
    if not restored:
        return {"ok": False, "reason": "no backup found"}
    return {"ok": True, "restored": restored}
