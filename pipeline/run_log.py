# pipeline/run_log.py
"""Append-only run history (one JSON object per line)."""
import json
import os
from datetime import datetime, timezone

DEFAULT_PATH = "experiments/runs.jsonl"


def append_run(entry: dict, path: str = DEFAULT_PATH) -> dict:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read_runs(path: str = DEFAULT_PATH) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
