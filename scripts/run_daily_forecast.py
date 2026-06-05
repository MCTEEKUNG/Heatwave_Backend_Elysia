"""Resumable, rate-limit-batched daily forecast runner for all 77 provinces.

Usage examples
--------------
Dry run (print schedule, no forecast or sleep):
    python scripts/run_daily_forecast.py --dry-run

Full run with defaults (batch_size=5, sleep=HEATWAVE_SLEEP env or 20s):
    python scripts/run_daily_forecast.py

Resume from a previous run (skip already-done province IDs):
    python scripts/run_daily_forecast.py --state-file state.json

Custom batch size:
    python scripts/run_daily_forecast.py --batch-size 10 --state-file state.json

Environment variables
---------------------
HEATWAVE_SLEEP : seconds to sleep between batches (default: 20).

Design notes
------------
Orchestration logic lives in three pure, unit-testable helpers (provinces_to_run,
batches, plan_schedule) that carry no side effects — no network, no DB, no I/O.

main() wires real fetch + model + DB by calling pipeline.run_forecast's
build_forecast_rows per batch-subset, mirroring what run_forecast.main() does
for the full set.  The integration path is guarded by --dry-run so unit tests
and CI never hit the network.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is importable whether this script is run directly from the
# scripts/ subdirectory or from the repo root (e.g. `python scripts/run_daily_forecast.py`).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Pure helpers (no network / no DB — fully unit-testable)
# ---------------------------------------------------------------------------

def provinces_to_run(all_ids: list, already_done_ids) -> list:
    """Return ids in all_ids not in already_done_ids, preserving input order.

    Parameters
    ----------
    all_ids : sequence of province IDs (any comparable type).
    already_done_ids : iterable of IDs to exclude.

    Returns
    -------
    list preserving the order of all_ids with done IDs removed.
    """
    done_set = set(already_done_ids)
    return [pid for pid in all_ids if pid not in done_set]


def batches(items: list, size: int) -> list[list]:
    """Split *items* into consecutive sub-lists of at most *size* elements.

    The last batch may be shorter.  Returns an empty list for empty input.
    Raises ValueError if size < 1.

    Parameters
    ----------
    items : flat list to partition.
    size  : maximum number of elements per batch (>= 1).
    """
    if size < 1:
        raise ValueError(f"batch size must be >= 1, got {size}")
    if not items:
        return []
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def plan_schedule(n_provinces: int, batch_size: int, sleep_s: float) -> dict:
    """Return a schedule summary dict (pure arithmetic, no side effects).

    Parameters
    ----------
    n_provinces : total number of provinces to process.
    batch_size  : max provinces per batch.
    sleep_s     : seconds to sleep *between* batches (not after the last one).

    Returns
    -------
    dict with keys:
      - n_batches   (int) : ceil(n_provinces / batch_size), or 0 if n_provinces=0.
      - est_seconds (float) : (n_batches - 1) * sleep_s (sleep only between batches).
    """
    if n_provinces <= 0:
        return {"n_batches": 0, "est_seconds": 0}
    n_batches = math.ceil(n_provinces / batch_size)
    est_seconds = (n_batches - 1) * sleep_s
    return {"n_batches": n_batches, "est_seconds": est_seconds}


# ---------------------------------------------------------------------------
# State-file helpers (I/O, not pure — not unit-tested directly)
# ---------------------------------------------------------------------------

def _load_done_ids(state_file: str | None) -> list:
    """Load already-done province IDs from the JSON state file.

    Returns an empty list if state_file is None or doesn't exist.
    """
    if state_file is None:
        return []
    path = Path(state_file)
    if not path.exists():
        return []
    with path.open() as fh:
        data = json.load(fh)
    return list(data.get("done_ids", []))


def _save_done_ids(state_file: str | None, done_ids: list) -> None:
    """Persist done IDs to the JSON state file (atomic-ish: write then replace)."""
    if state_file is None:
        return
    path = Path(state_file)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as fh:
        json.dump({"done_ids": done_ids}, fh)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    """CLI entry point — wire pure helpers with real forecast + DB."""
    parser = argparse.ArgumentParser(
        description="Run the daily heatwave forecast for all 77 Thai provinces "
                    "in rate-limit-friendly batches, with resume support.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        metavar="N",
        help="Number of provinces per batch (default: 5).",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        metavar="PATH",
        help="JSON file for resumable state (done province IDs). "
             "Created/updated after each batch. Omit to start fresh each run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print schedule via plan_schedule and exit without running any "
             "forecasts or sleeping.",
    )
    args = parser.parse_args(argv)

    # Load .env so a bare local run picks up DATABASE_URL (the DB write happens
    # only after the first Open-Meteo fetch, so without this the job fetches
    # fine and then crashes at the first upsert with "DATABASE_URL is not set").
    # In CI the variable is injected directly and there is no .env, so this is a
    # harmless no-op. Imported lazily so --dry-run / unit tests never need it.
    if not args.dry_run:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

    # Read sleep duration from env (allows CI override without code change)
    sleep_s = float(os.environ.get("HEATWAVE_SLEEP", "20"))
    batch_size = args.batch_size
    state_file = args.state_file

    # Load province list (always, so dry-run shows the real remaining count)
    from src.provinces import load_provinces
    provinces_df = load_provinces()
    all_ids = provinces_df["id"].tolist()

    done_ids = _load_done_ids(state_file)
    remaining_ids = provinces_to_run(all_ids, done_ids)
    province_batches = batches(remaining_ids, batch_size)
    schedule = plan_schedule(len(remaining_ids), batch_size, sleep_s)

    if args.dry_run:
        print("=== Dry-run schedule ===")
        print(f"Total provinces     : {len(all_ids)}")
        print(f"Already done        : {len(done_ids)}")
        print(f"Remaining           : {len(remaining_ids)}")
        print(f"Batch size          : {batch_size}")
        print(f"Sleep between batches: {sleep_s}s (HEATWAVE_SLEEP env)")
        print(f"Number of batches   : {schedule['n_batches']}")
        print(f"Estimated runtime   : {schedule['est_seconds']}s "
              f"(~{schedule['est_seconds'] / 60:.1f} min)")
        for i, batch_ids in enumerate(province_batches, start=1):
            print(f"  Batch {i:02d}: province IDs {batch_ids}")
        print("(dry-run: no forecasts run, no sleeping)")
        return

    # --- Real run (network + DB) ---
    # Import here so tests that only test pure helpers never trigger network imports
    import pandas as pd
    import joblib

    from pipeline.run_forecast import (
        build_forecast_rows,
        _real_frame_builder,
        _bangkok_today,
        DEFAULT_MODEL_VERSION,
        LABEL_THRESHOLD,
        MODEL_PATH,
    )
    from src.db_write import upsert_forecasts

    # Load model once (expensive).
    # SECURITY: joblib.load deserialises a pickle-based format.  This is safe
    # here because MODEL_PATH is a fixed local path pointing to a first-party
    # artefact produced by our own training pipeline — it is never user-supplied
    # or fetched from an untrusted remote.  (Same rationale as the comment in
    # pipeline/run_forecast.py.)
    print(f"Loading model from {MODEL_PATH} ...")
    model = joblib.load(MODEL_PATH)

    # Load province-level p95 thresholds if available
    thresholds = None
    try:
        thresholds = pd.read_parquet("data/processed/province_thresholds.parquet")
        print("Loaded province_thresholds.parquet")
    except Exception:
        print("WARNING: province_thresholds.parquet not found; p95 features "
              "will be missing — prediction may fail on feature mismatch.")

    horizons = range(1, 8)
    generated_at = datetime.now(timezone.utc)
    origin = _bangkok_today()
    forecast_days = max(horizons) + 1

    # Build the Open-Meteo-backed frame builder (reuses run_forecast private helper)
    builder = _real_frame_builder(
        origin,
        history_days=40,
        forecast_days=forecast_days,
        thresholds=thresholds,
    )

    total_upserted = 0
    done_ids_set = set(done_ids)

    print(
        f"Starting forecast run: {len(remaining_ids)} provinces, "
        f"{schedule['n_batches']} batches, sleep={sleep_s}s between batches."
    )

    for batch_num, batch_ids in enumerate(province_batches, start=1):
        batch_df = provinces_df[provinces_df["id"].isin(batch_ids)]
        print(
            f"[{batch_num}/{schedule['n_batches']}] "
            f"Processing provinces: {batch_ids} ..."
        )
        rows = build_forecast_rows(
            batch_df,
            model,
            generated_at,
            history_days=40,
            horizons=horizons,
            frame_builder=builder,
            model_version=DEFAULT_MODEL_VERSION,
            label_threshold=LABEL_THRESHOLD,
            origin_date=origin,
        )
        n = upsert_forecasts(rows)
        total_upserted += n
        print(f"  Upserted {n} rows for batch {batch_num}.")

        # Record progress immediately so a crash mid-run can be resumed
        done_ids_set.update(batch_ids)
        _save_done_ids(state_file, sorted(done_ids_set))

        # Sleep between batches (not after the last one)
        if batch_num < schedule["n_batches"]:
            print(f"  Sleeping {sleep_s}s to respect Open-Meteo rate limit ...")
            time.sleep(sleep_s)

    print(
        f"Done. Upserted {total_upserted} forecast rows total "
        f"({len(done_ids_set)} provinces processed) generated_at={generated_at}"
    )
    if state_file:
        print(f"State saved to: {state_file}")


if __name__ == "__main__":
    main()
