"""
models/xgboost_model.py
XGBoost Classifier wrapped in the BaseModel interface.
GPU acceleration is automatically enabled when CUDA is available and
training.use_gpu=true in config.yaml.
"""
import os
import logging
import numpy as np
import joblib
import yaml
from models.base_model import BaseModel
from evaluation.metrics import compute_metrics
from utils.gpu_utils import xgboost_device_params

logger = logging.getLogger(__name__)


class XGBoostModel(BaseModel):
    """XGBoost Gradient Boosting Classifier with GPU/CPU auto-selection."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        params = cfg["models"]["xgboost"]
        self._config_path = config_path

        # GPU / CPU device params resolved at construction time
        device_params = xgboost_device_params(config_path)

        from xgboost import XGBClassifier
        self.model = XGBClassifier(
            n_estimators=params.get("n_estimators", 300),
            max_depth=params.get("max_depth", 6),
            learning_rate=params.get("learning_rate", 0.1),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            random_state=params.get("random_state", 42),
            n_jobs=params.get("n_jobs", -1),
            eval_metric=params.get("eval_metric", "logloss"),
            verbosity=0,
            **device_params,
        )
        self._is_fitted = False

    def get_model_name(self) -> str:
        return "XGBoost"

    def train(self, X_train, y_train, X_val=None, y_val=None):
        logger.info("Training %s ...", self.get_model_name())

        # Set scale_pos_weight from actual label distribution (handles imbalance)
        neg = int((y_train == 0).sum())
        pos = int((y_train == 1).sum())
        spw = neg / max(pos, 1)
        self.model.set_params(scale_pos_weight=spw)
        logger.info("scale_pos_weight=%.1f  (neg=%d pos=%d)", spw, neg, pos)

        eval_set = [(X_val, y_val)] if X_val is not None else None
        try:
            self.model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
        except Exception as e:
            # GPU might not be supported in this XGBoost build — fall back to CPU
            if "gpu" in str(e).lower() or "cuda" in str(e).lower():
                logger.warning("GPU training failed (%s) — retrying on CPU", e)
                from xgboost import XGBClassifier
                with open(self._config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                p = cfg["models"]["xgboost"]
                self.model = XGBClassifier(
                    n_estimators=p.get("n_estimators", 300),
                    max_depth=p.get("max_depth", 6),
                    learning_rate=p.get("learning_rate", 0.1),
                    subsample=p.get("subsample", 0.8),
                    colsample_bytree=p.get("colsample_bytree", 0.8),
                    random_state=p.get("random_state", 42),
                    n_jobs=p.get("n_jobs", -1),
                    eval_metric=p.get("eval_metric", "logloss"),
                    verbosity=0,
                    tree_method="hist",
                    device="cpu",
                )
                self.model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
            else:
                raise
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
