"""Trainer registry: name -> Trainer instance factory."""
from __future__ import annotations

from .base import Trainer
from .lgbm import LgbmTrainer
from .simulated import SimulatedTrainer

# Factories so each run gets a fresh, stateless trainer instance.
_REGISTRY = {
    "simulated": SimulatedTrainer,
    "lgbm": LgbmTrainer,
}


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
