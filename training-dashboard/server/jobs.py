"""Resolve a job by (name, kind): a Trainer or a pipeline StageJob.

Both expose run(config, progress_cb, should_stop) -> dict, so the runner is
agnostic to which kind it drives.
"""
from __future__ import annotations

from .stages import get_stage
from .trainers import get_trainer


def resolve_job(name: str, kind: str = "trainer"):
    if kind == "stage":
        return get_stage(name)
    return get_trainer(name)
