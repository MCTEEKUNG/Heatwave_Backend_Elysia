"""CLI for the safe-promote core (src.promote).

Promote a dashboard model (models/dashboard/<name>.pkl) to the production slot
(models/heatwave_model.pkl) with a province-coverage guard + automatic backup,
or roll back to the previous artifact. Shares ONE implementation with the
dashboard OpsPanel (src/promote.py) — no duplicated logic.

Usage:
  python scripts/promote_model.py --model lgbm --dry-run
  python scripts/promote_model.py --model lgbm
  python scripts/promote_model.py --model lgbm --force     # override coverage guard
  python scripts/promote_model.py --rollback               # restore last backup

Regenerating live Supabase after a promote is a separate, deliberate step
(scripts/run_daily_forecast.py) — this CLI never touches the database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.promote import promote, rollback


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="lgbm",
                    help="dashboard model name under models/dashboard/ (default: lgbm)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; change nothing")
    ap.add_argument("--force", action="store_true", help="override the coverage guard")
    ap.add_argument("--rollback", action="store_true",
                    help="restore the most recent production backup instead of promoting")
    args = ap.parse_args(argv)

    if args.rollback:
        r = rollback()
        print(json.dumps(r, indent=2))
        return 0 if r["ok"] else 1

    r = promote(args.model, force=args.force, dry_run=args.dry_run)
    print(json.dumps(r, indent=2, default=str))
    if not r["ok"]:
        print(f"REFUSED: {r['reason']}")
        return 1
    for w in r.get("warnings", []):
        print(f"WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
