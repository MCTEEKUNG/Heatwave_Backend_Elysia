"""Promote a dashboard-trained model to the production artifact.

The training dashboard saves experiments to ``models/dashboard/<name>.pkl``
(a sandbox -- see training-dashboard/server/trainers/saving.py). Production
serves ``models/heatwave_model.pkl`` (loaded by scripts/run_daily_forecast.py
-> Supabase -> /api/forecast/map). There was no link between the two; this is
that link, with a guard so a narrow experiment can't silently shrink coverage.

What it does:
  1. Loads the candidate bundle ``models/dashboard/<name>.pkl`` (must be a
     src.model.CalibratedModel, the same class production uses).
  2. COVERAGE GUARD: refuses to promote if the candidate was trained on fewer
     provinces than the current production model (prevents the 77 -> 20
     regression). Override with --force.
  3. Backs up the current artifact + model_card, then copies the candidate
     into place and writes a fresh models/model_card.json.
  4. Does NOT touch Supabase. It prints the exact follow-up command
     (scripts/run_daily_forecast.py) -- regenerating live forecasts is an
     explicit, separate step.

Usage:
  python scripts/promote_model.py --model lgbm --dry-run
  python scripts/promote_model.py --model lgbm
  python scripts/promote_model.py --model lgbm --force      # skip coverage guard
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# Make the repo root importable so joblib can resolve src.model.CalibratedModel
# when this is run directly as `python scripts/promote_model.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DASHBOARD_DIR = "models/dashboard"
PROD_MODEL = "models/heatwave_model.pkl"
PROD_CARD = "models/model_card.json"


def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _candidate_n_provinces(sidecar: dict) -> int | None:
    """Coverage of the candidate, if the sidecar recorded it."""
    m = sidecar.get("metrics") or {}
    v = m.get("n_provinces", sidecar.get("n_provinces"))
    return int(v) if isinstance(v, (int, float)) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="lgbm",
                    help="dashboard model name under models/dashboard/ (default: lgbm)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would happen; change nothing")
    ap.add_argument("--force", action="store_true",
                    help="promote even if it reduces province coverage")
    ap.add_argument("--regenerate", action="store_true",
                    help="after promoting, run run_daily_forecast.py (writes Supabase)")
    args = ap.parse_args()

    cand_pkl = os.path.join(DASHBOARD_DIR, f"{args.model}.pkl")
    cand_json = os.path.join(DASHBOARD_DIR, f"{args.model}.json")
    if not os.path.isfile(cand_pkl):
        print(f"ERROR: candidate not found: {cand_pkl}")
        return 2

    # Load + validate the candidate bundle.
    # SECURITY: joblib.load deserialises pickle. Safe here -- cand_pkl is a
    # first-party local artifact written by our own training pipeline
    # (models/dashboard/), never a remote/untrusted source. Same trust model as
    # scripts/run_daily_forecast.py.
    import joblib
    bundle = joblib.load(cand_pkl)
    cls = type(bundle).__name__
    if cls != "CalibratedModel":
        print(f"ERROR: candidate is {cls}, expected CalibratedModel -- refusing.")
        return 2

    sidecar = _load_json(cand_json)
    cand_prov = _candidate_n_provinces(sidecar)
    prod_card = _load_json(PROD_CARD)
    prod_prov = (prod_card.get("data") or {}).get("n_provinces")

    n_features = len(getattr(bundle, "feature_cols", []) or [])
    model_version = getattr(bundle, "model_version", args.model)
    threshold = float(getattr(bundle, "threshold", 0.5))

    print("=== promote_model ===")
    print(f"candidate : {cand_pkl}  (class={cls}, version={model_version}, "
          f"features={n_features}, threshold={threshold:.4f})")
    print(f"coverage  : candidate n_provinces={cand_prov}  |  production n_provinces={prod_prov}")

    # --- COVERAGE GUARD ---------------------------------------------------
    if not args.force:
        if cand_prov is None:
            print("REFUSED: candidate sidecar has no n_provinces -- cannot verify "
                  "coverage. Re-run training that records it, or pass --force.")
            return 1
        if isinstance(prod_prov, (int, float)) and cand_prov < prod_prov:
            print(f"REFUSED: candidate covers fewer provinces ({cand_prov}) than "
                  f"production ({prod_prov}). This would shrink coverage. "
                  f"Pass --force to override.")
            return 1
    print("guard     : OK" if not args.force else "guard     : SKIPPED (--force)")

    # Build the new model card.
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    size_kb = round(os.path.getsize(cand_pkl) / 1024, 1)
    new_card = {
        "model": prod_card.get("model", "heatwave-lgbm"),
        "stage": "production",
        "model_version": model_version,
        "trained_at": sidecar.get("saved_at", stamp),
        "promoted_at": stamp,
        "promoted_from": cand_pkl.replace("\\", "/"),
        "git_sha": _git_sha(),
        "data": {**(prod_card.get("data") or {}), "n_provinces": cand_prov},
        "operating_point": {"threshold": threshold, "selected_on": "validation"},
        "test_metrics": {k: v for k, v in (sidecar.get("metrics") or {}).items()},
        "n_features": n_features,
        "artifact": {"path": PROD_MODEL, "format": "joblib",
                     "size_kb": size_kb, "class": cls},
    }

    if args.dry_run:
        print("\n[dry-run] would back up + replace:")
        print(f"  {PROD_MODEL}  <- {cand_pkl}")
        print(f"  {PROD_CARD}   <- (regenerated)")
        print("\n[dry-run] new model_card.json would be:")
        print(json.dumps(new_card, indent=2))
        print("\n[dry-run] no files changed.")
        return 0

    # Back up current production artifact + card.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for path in (PROD_MODEL, PROD_CARD):
        if os.path.isfile(path):
            bak = f"{path}.bak-{ts}"
            shutil.copy2(path, bak)
            print(f"backup    : {path} -> {bak}")

    shutil.copy2(cand_pkl, PROD_MODEL)
    with open(PROD_CARD, "w", encoding="utf-8") as f:
        json.dump(new_card, f, indent=2)
    print(f"promoted  : {cand_pkl} -> {PROD_MODEL}")
    print(f"card      : wrote {PROD_CARD}")

    if args.regenerate:
        print("\nregenerate: running scripts/run_daily_forecast.py (writes Supabase)...")
        rc = subprocess.run(["python", "scripts/run_daily_forecast.py"]).returncode
        print(f"regenerate: exit {rc}")
        return rc

    print("\nNEXT: regenerate live forecasts in Supabase with:")
    print("  .\\.venv\\Scripts\\python.exe scripts\\run_daily_forecast.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
