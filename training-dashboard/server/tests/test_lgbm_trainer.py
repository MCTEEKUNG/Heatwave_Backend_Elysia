"""The lgbm trainer raises a friendly error when the dataset is absent."""
import pytest

from server.trainers import get_trainer
from server.trainers import lgbm as lgbm_mod


def test_lgbm_missing_dataset_raises_friendly(monkeypatch):
    # Point at a guaranteed-missing path so the test is deterministic whether or
    # not a real data/processed/dataset.parquet exists on disk.
    missing = "data/processed/__nonexistent_for_test__.parquet"
    monkeypatch.setattr(lgbm_mod, "DATASET_PATH", missing)

    trainer = get_trainer("lgbm")
    with pytest.raises(FileNotFoundError) as exc:
        trainer.run({}, lambda s, t, m: None, lambda: False)
    msg = str(exc.value)
    assert "dataset not found" in msg
    assert missing in msg
    assert "build_dataset" in msg


def test_registry_lists_all_trainers():
    from server.trainers import available
    assert available() == [
        "balanced_rf", "catboost", "lgbm", "mlp",
        "random_forest", "simulated", "xgboost",
    ]


def test_sklearn_trainer_missing_dataset_raises(monkeypatch):
    from server.trainers import sklearn_models as sk
    monkeypatch.setattr(sk, "DATASET_PATH", "data/processed/__nonexistent__.parquet")
    trainer = get_trainer("xgboost")
    with pytest.raises(FileNotFoundError):
        trainer.run({}, lambda s, t, m: None, lambda: False)
