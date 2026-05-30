"""Trainer registry: name -> Trainer instance factory."""
from __future__ import annotations

from functools import partial

from .base import Trainer
from .lgbm import LgbmTrainer
from .simulated import SimulatedTrainer
from .sklearn_models import SUPPORTED as _SKLEARN_SUPPORTED, ModelTrainer

# Factories so each run gets a fresh, stateless trainer instance.
_REGISTRY = {
    "simulated": SimulatedTrainer,
    "lgbm": LgbmTrainer,
}
# The non-LightGBM families share one parameterized trainer.
for _name in _SKLEARN_SUPPORTED:
    _REGISTRY[_name] = partial(ModelTrainer, _name)


def get_trainer(name: str) -> Trainer:
    """Return a fresh trainer instance for ``name``.

    Raises ``ValueError`` for an unknown trainer name.
    """
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown trainer: {name!r}")
    return factory()


def available() -> list[str]:
    return sorted(_REGISTRY)
