"""
training/trainer.py
Executes the train → evaluate → save → log cycle for a single model.
"""
import os
import json
import logging
import time
import yaml

logger = logging.getLogger(__name__)


class Trainer:
    """Orchestrates training, evaluation, and persistence for one model."""

    def __init__(self, model, config_path: str = "config/config.yaml"):
        self.model = model
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.results_dir = cfg["experiments"]["results_dir"]
        self.models_dir = cfg["experiments"]["models_dir"]
        self.logs_dir = cfg["experiments"]["logs_dir"]
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def run(self, X_train, y_train, X_val, y_val, X_test, y_test) -> dict:
        """
        Full training cycle: train → evaluate → save model → save result JSON.
        Returns the metrics dict.
        """
        name = self.model.get_model_name()
        logger.info("=" * 60)
        logger.info("Starting experiment: %s", name)
        logger.info("=" * 60)

        t0 = time.time()
        self.model.train(X_train, y_train, X_val, y_val)
        train_time = time.time() - t0
        logger.info("Trained in %.1f seconds", train_time)

        metrics = self.model.evaluate(X_test, y_test)
        metrics["train_time_seconds"] = round(train_time, 2)

        # Save result JSON
        safe_name = name.lower().replace(" ", "_")
        result_path = os.path.join(self.results_dir, f"{safe_name}_result.json")
        with open(result_path, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info("Result saved: %s", result_path)

        # Save model
        model_path = os.path.join(self.models_dir, f"{safe_name}_model.pkl")
        self.model.save_model(model_path)

        return metrics
