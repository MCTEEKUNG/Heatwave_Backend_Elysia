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

DATASET_PATH = "data/processed/dataset.parquet"
PROVINCES_PATH = "data/provinces.csv"


class _StopTraining(Exception):
    """Internal sentinel raised to abort a LightGBM run cooperatively."""


class LgbmTrainer(Trainer):
    name = "lgbm"

    def run(self, config: dict, progress_cb: ProgressCb, should_stop: ShouldStop) -> dict:
        # Imported lazily so the server (and its tests) can import this module
        # without pulling in pandas / lightgbm unless a real run is requested.
        import pandas as pd
        from pipeline.train import train_model

        if not os.path.exists(DATASET_PATH):
            raise FileNotFoundError(
                f"dataset not found: {DATASET_PATH} -- run build_dataset first"
            )

        progress_cb(0, 1, "loading dataset")
        dataset = pd.read_parquet(DATASET_PATH)
        if "lat" not in dataset.columns:
            prov = pd.read_csv(PROVINCES_PATH)[["id", "lat", "lon"]]
            dataset = dataset.merge(
                prov, left_on="province_id", right_on="id", how="left"
            ).drop(columns=["id"])

        def _progress(step: int, total: int, message: str) -> None:
            # Abort promptly if asked to stop -- raised through LightGBM's
            # callback and caught below.
            if should_stop():
                raise _StopTraining()
            progress_cb(step, total, message)

        try:
            bundle, report = train_model(dataset, progress_cb=_progress)
        except _StopTraining:
            return {"trainer": "lgbm", "stopped": True}

        report = dict(report)
        report["trainer"] = "lgbm"
        return report
