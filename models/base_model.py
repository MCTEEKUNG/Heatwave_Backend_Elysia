"""
models/base_model.py
Abstract base class that all models must inherit from.
"""
from abc import ABC, abstractmethod
from typing import Any
import numpy as np


class BaseModel(ABC):
    """
    Shared interface for all heatwave prediction models.
    Subclasses must implement every abstract method.
    """

    @abstractmethod
    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              X_val: np.ndarray = None, y_val: np.ndarray = None) -> None:
        """Fit the model on training data."""
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return class predictions (0 or 1) for input array."""
        ...

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return probability estimates (default: same as predict cast to float)."""
        return self.predict(X).astype(float)

    @abstractmethod
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> dict:
        """Evaluate on test data and return metrics dict."""
        ...

    @abstractmethod
    def save_model(self, path: str) -> None:
        """Persist model to disk."""
        ...

    @abstractmethod
    def load_model(self, path: str) -> None:
        """Load model from disk."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return human-readable model name."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.get_model_name()}>"
