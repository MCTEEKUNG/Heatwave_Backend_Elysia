"""Real LightGBM trainer wrapping ``pipeline.train.train_model``.

Reads ``data/processed/dataset.parquet`` (the same source as
``pipeline/train.main``), runs the real train/calibrate/evaluate pipeline, and
reports progress once per boosting round. Cooperative stop is implemented by
raising a private sentinel from inside the progress callback, which we catch
around ``train_model``.
"""
from __future__ import annotations

import os

from .base import ProgressCb, ShouldStop, Trainer
from pipeline.run_log import append_run
from pipeline.leaderboard import upsert_model

DATASET_PATH = "data/processed/dataset.parquet"


class _StopTraining(Exception):
    """Internal sentinel raised to abort a LightGBM run cooperatively."""


class LgbmTrainer(Trainer):
    name = "lgbm"

    def run(self, config: dict, progress_cb: ProgressCb, should_stop: ShouldStop) -> dict:
        # Imported lazily so the server (and its tests) can import this module
        # without pulling in pandas / lightgbm unless a real run is requested.
        import pandas as pd
        from pipeline.train import train_model
        from pipeline.frame_cache import cached_build_frames
        from .saving import save_dashboard_model

        if not os.path.exists(DATASET_PATH):
            raise FileNotFoundError(
                f"dataset not found: {DATASET_PATH} -- run build_dataset first"
            )

        def _check_stop() -> None:
            if should_stop():
                raise _StopTraining()

        def _progress(step: int, total: int, message: str) -> None:
            # Abort promptly if asked to stop -- raised through LightGBM's
            # callback and caught below.
            _check_stop()
            progress_cb(step, total, message)

        # The load/preprocess phases below can each take many seconds and are
        # not interruptible mid-call; check stop at every phase boundary so a
        # stop issued before the first boosting round still halts promptly
        # instead of leaving a zombie thread running to completion.
        try:
            _check_stop()
            progress_cb(0, 1, "loading dataset")
            dataset = pd.read_parquet(DATASET_PATH)
            _check_stop()
            frame = cached_build_frames(DATASET_PATH, horizons=range(1, 8))
            _check_stop()
            bundle, report = train_model(dataset, progress_cb=_progress, frame=frame)
        except _StopTraining:
            return {"trainer": "lgbm", "stopped": True}

        report = dict(report)
        report["trainer"] = "lgbm"
        # Persist the calibrated bundle to the dashboard models dir (separate
        # from the curated production artifact models/heatwave_model.pkl).
        report["saved"] = save_dashboard_model("lgbm", bundle, report)
        _t = report.get("test") or {}
        upsert_model("lgbm", {**_t, "threshold": report.get("threshold")},
                     n_provinces=int(frame["province_id"].nunique()))
        append_run({"trainer": "lgbm", "f2": _t.get("f2"), "pr_auc": _t.get("pr_auc"),
                    "brier_skill_score": _t.get("brier_skill_score"),
                    "threshold": report.get("threshold"),
                    "saved": (report.get("saved") or {}).get("path"),
                    "config": config or {}})
        return report
