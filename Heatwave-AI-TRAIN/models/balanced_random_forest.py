"""
models/balanced_random_forest.py
Balanced Random Forest using imbalanced-learn.
"""
import os
import logging
import numpy as np
import joblib
import yaml
from models.base_model import BaseModel
from evaluation.metrics import compute_metrics

logger = logging.getLogger(__name__)


class BalancedRandomForestModel(BaseModel):
    """Balanced Random Forest Classifier (handles class imbalance natively)."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        params = cfg["models"]["balanced_rf"]

        from imblearn.ensemble import BalancedRandomForestClassifier
        self.model = BalancedRandomForestClassifier(
            n_estimators=params.get("n_estimators", 200),
            max_depth=params.get("max_depth", 15),
            random_state=params.get("random_state", 42),
            n_jobs=params.get("n_jobs", -1),
            replacement=True,
            sampling_strategy="auto",
        )
        self._is_fitted = False

    def get_model_name(self) -> str:
        return "Balanced Random Forest"

    def train(self, X_train, y_train, X_val=None, y_val=None):
        logger.info("Training %s ...", self.get_model_name())
        self.model.fit(X_train, y_train)
        self._is_fitted = True
        logger.info("Training complete.")

    def predict(self, X) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test, y_test) -> dict:
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)
        return compute_metrics(y_test, y_pred, y_proba, self.get_model_name())

    def save_model(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        logger.info("Model saved: %s", path)

    def load_model(self, path: str):
        self.model = joblib.load(path)
        self._is_fitted = True
        logger.info("Model loaded: %s", path)
