"""
models/lightgbm_model.py
LightGBM Classifier wrapped in the BaseModel interface.
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
from utils.gpu_utils import lightgbm_device_params

logger = logging.getLogger(__name__)


class LightGBMModel(BaseModel):
    """LightGBM Gradient Boosting Classifier with GPU/CPU auto-selection."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        params = cfg["models"]["lightgbm"]
        self._config_path = config_path

        # GPU / CPU device params resolved at construction time
        device_params = lightgbm_device_params(config_path)

        import lightgbm as lgb
        self.model = lgb.LGBMClassifier(
            n_estimators=params.get("n_estimators", 300),
            max_depth=params.get("max_depth", 6),
            learning_rate=params.get("learning_rate", 0.1),
            num_leaves=params.get("num_leaves", 63),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            random_state=params.get("random_state", 42),
            n_jobs=params.get("n_jobs", -1),
            verbose=params.get("verbose", -1),
            is_unbalance=True,   # handle class imbalance natively
            **device_params,
        )
        self._is_fitted = False

    def get_model_name(self) -> str:
        return "LightGBM"

    def train(self, X_train, y_train, X_val=None, y_val=None):
        logger.info("Training %s ...", self.get_model_name())
        callbacks = []
        try:
            import lightgbm as lgb
            callbacks.append(lgb.early_stopping(20, verbose=False))
            callbacks.append(lgb.log_evaluation(period=-1))
        except Exception:
            pass

        eval_set = [(X_val, y_val)] if X_val is not None else None
        try:
            self.model.fit(X_train, y_train, eval_set=eval_set, callbacks=callbacks)
        except Exception as e:
            err_str = str(e).lower()
            # Fallback to CPU on GPU errors OR LightGBM split errors (imbalanced data on GPU)
            is_gpu_err = "gpu" in err_str or "cuda" in err_str or "opencl" in err_str
            is_split_err = "best_split_info" in err_str or "right_count" in err_str
            if is_gpu_err or is_split_err:
                logger.warning("LightGBM GPU training failed (%s) — retrying on CPU with imbalance handling", e)
                import lightgbm as lgb
                with open(self._config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                p = cfg["models"]["lightgbm"]
                self.model = lgb.LGBMClassifier(
                    n_estimators=p.get("n_estimators", 300),
                    max_depth=p.get("max_depth", 6),
                    learning_rate=p.get("learning_rate", 0.1),
                    num_leaves=p.get("num_leaves", 63),
                    subsample=p.get("subsample", 0.8),
                    colsample_bytree=p.get("colsample_bytree", 0.8),
                    random_state=p.get("random_state", 42),
                    n_jobs=p.get("n_jobs", -1),
                    verbose=-1,
                    is_unbalance=True,       # handle class imbalance
                    min_child_samples=20,    # prevent overly small leaves
                )
                self.model.fit(X_train, y_train, eval_set=eval_set, callbacks=callbacks)
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
