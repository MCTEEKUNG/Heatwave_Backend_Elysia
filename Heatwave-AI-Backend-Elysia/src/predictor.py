"""
prediction/predictor.py
Loads a trained model + scaler and runs inference on new data.
Self-contained version for deployment (no training code needed).
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import joblib
import yaml

logger = logging.getLogger(__name__)

# Map CLI name → model file
MODEL_REGISTRY = {
    "balanced_rf": "balanced_random_forest_model.pkl",
    "xgboost": "xgboost_model.pkl",
    "lightgbm": "lightgbm_model.pkl",
    "mlp": "mlp_neural_network_model.pkl",
    "kan": "kan_model.pkl",
}


class Predictor:
    """Loads a saved model and scaler, runs prediction on new input data."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        # Use local models directory
        self.models_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "models"
        )
        self.config_path = config_path

        # Load scaler
        scaler_path = os.path.join(self.models_dir, "scaler.pkl")
        if os.path.isfile(scaler_path):
            self.scaler = joblib.load(scaler_path)
        else:
            self.scaler = None
            logger.warning("Scaler not found — raw features will not be normalized")

        # Load feature names
        feat_path = os.path.join(self.models_dir, "feature_names.pkl")
        self.feature_names = (
            joblib.load(feat_path) if os.path.isfile(feat_path) else None
        )

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
                f"Unknown model '{model_key}'. Available: {list(MODEL_REGISTRY.keys())}"
            )
        model_file = MODEL_REGISTRY[key]
        model_path = os.path.join(self.models_dir, model_file)

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"Model file not found: {model_path}\n"
                f"Available files: {os.listdir(self.models_dir)}"
            )

        model = joblib.load(model_path)
        logger.info("Loaded model from %s", model_path)
        return model

    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        """Apply feature engineering and scaling to input DataFrame."""
        # Engineer features if raw data
        if "t2m" in df.columns and "t2m_c" not in df.columns:
            df = df.copy()
            df["t2m_c"] = df["t2m"] - 273.15
            df["d2m_c"] = df["d2m"] - 273.15
            df["rh"] = 100 * np.exp(
                (17.625 * df["d2m_c"]) / (243.04 + df["d2m_c"])
                - (17.625 * df["t2m_c"]) / (243.04 + df["t2m_c"])
            ).clip(0, 100)
            t_f = df["t2m_c"] * 9 / 5 + 32
            hi_f = (
                -42.379
                + 2.04901523 * t_f
                + 10.14333127 * df["rh"]
                - 0.22475541 * t_f * df["rh"]
                - 0.00683783 * t_f**2
                - 0.05481717 * df["rh"] ** 2
                + 0.00122874 * t_f**2 * df["rh"]
                + 0.00085282 * t_f * df["rh"] ** 2
                - 0.00000199 * t_f**2 * df["rh"] ** 2
            )
            df["heat_index"] = np.where(
                df["t2m_c"] >= 26.7, (hi_f - 32) * 5 / 9, df["t2m_c"]
            )
            df["wind_speed"] = np.sqrt(df.get("u10", 0) ** 2 + df.get("v10", 0) ** 2)

        if self.feature_names:
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = 0.0
            X = df[self.feature_names].fillna(0).values
        else:
            X = df.select_dtypes(include=[np.number]).fillna(0).values

        if self.scaler is not None:
            try:
                X = self.scaler.transform(X)
            except Exception as e:
                logger.warning("Scaler transform failed: %s — using raw features", e)
        return X
