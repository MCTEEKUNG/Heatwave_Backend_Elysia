"""The lgbm trainer raises a friendly error when the dataset is absent."""
import os

import pytest

from server.trainers import get_trainer
from server.trainers.lgbm import DATASET_PATH


def test_lgbm_missing_dataset_raises_friendly():
    # This suite is intended to run in an environment without the parquet.
    if os.path.exists(DATASET_PATH):
        pytest.skip("dataset present; cannot test the missing-file path")

    trainer = get_trainer("lgbm")
    with pytest.raises(FileNotFoundError) as exc:
        trainer.run({}, lambda s, t, m: None, lambda: False)
    msg = str(exc.value)
    assert "dataset not found" in msg
    assert DATASET_PATH in msg
    assert "build_dataset" in msg


def test_registry_lists_both():
    from server.trainers import available
    assert available() == ["lgbm", "simulated"]
