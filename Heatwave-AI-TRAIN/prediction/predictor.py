"""
prediction/predictor.py
Loads a trained model + scaler and runs inference on new data.
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
import joblib
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.preprocessing import HeatwavePreprocessor

logger = logging.getLogger(__name__)

# Map CLI name → model class info
MODEL_REGISTRY = {
    "balanced_rf": {
        "file": "balanced_random_forest_model.pkl",
        "class_path": ("models.balanced_random_forest", "BalancedRandomForestModel"),
    },
    "xgboost": {
        "file": "xgboost_model.pkl",
        "class_path": ("models.xgboost_model", "XGBoostModel"),
    },
    "lightgbm": {
        "file": "lightgbm_model.pkl",
        "class_path": ("models.lightgbm_model", "LightGBMModel"),
    },
    "mlp": {
        "file": "mlp_neural_network_model.pkl",
        "class_path": ("models.mlp_model", "MLPModel"),
    },
    "kan": {
        "file": "kan_model.pkl",
        "class_path": ("models.kan_model", "KANModel"),
    },
}


class Predictor:
    """Loads a saved model and scaler, runs prediction on new input data."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.models_dir = self.cfg["experiments"]["models_dir"]
        self.config_path = config_path
        self.preprocessor = HeatwavePreprocessor(config_path)

        # Load scaler
        scaler_path = os.path.join(self.models_dir, "scaler.pkl")
        if os.path.isfile(scaler_path):
            self.preprocessor.load_scaler(scaler_path)
        else:
            logger.warning("Scaler not found at %s — raw features will not be normalised", scaler_path)

        # Load feature names
        feat_path = os.path.join(self.models_dir, "feature_names.pkl")
        self.feature_names = joblib.load(feat_path) if os.path.isfile(feat_path) else None

    # ------------------------------------------------------------------
    def predict(self, model_key: str, input_data: pd.DataFrame) -> np.ndarray:
        """
        Load model by key and predict on input DataFrame.
        Returns binary label array.
        """
        model = self._load_model(model_key)
        X = self._preprocess(input_data)
        predictions = model.predict(X)
        return predictions

    def predict_proba(self, model_key: str, input_data: pd.DataFrame) -> np.ndarray:
        model = self._load_model(model_key)
        X = self._preprocess(input_data)
        return model.predict_proba(X)

    # ------------------------------------------------------------------
    def _load_model(self, model_key: str):
        key = model_key.lower().strip()
        if key not in MODEL_REGISTRY:
            raise ValueError(
                f"Unknown model '{model_key}'. "
                f"Available: {list(MODEL_REGISTRY.keys())}"
            )
        info = MODEL_REGISTRY[key]
        model_path = os.path.join(self.models_dir, info["file"])

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                "Run training pipeline first: python main.py --mode train"
            )

        module_name, class_name = info["class_path"]
        import importlib
        module = importlib.import_module(module_name)
        model_cls = getattr(module, class_name)
        model = model_cls(self.config_path)
        model.load_model(model_path)
        logger.info("Loaded %s from %s", class_name, model_path)
        return model

    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        """Apply feature engineering and scaling to input DataFrame."""
        df = self.preprocessor._engineer_features(df)
        if self.feature_names:
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = 0.0
            X = df[self.feature_names].fillna(0).values
        else:
            X = df.select_dtypes(include=[np.number]).fillna(0).values

        try:
            X = self.preprocessor.scaler.transform(X)
        except Exception as e:
            logger.warning("Scaler transform failed: %s — using raw features", e)
        return X
