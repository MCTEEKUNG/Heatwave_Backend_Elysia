"""
pipelines/training_pipeline.py
Orchestrates the full training run: load → preprocess → split → train all models
→ evaluate → save results → update leaderboard.
"""
import os
import sys
import logging
import yaml
import joblib
from colorama import init, Fore, Style

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import ERA5DataLoader
from utils.preprocessing import HeatwavePreprocessor
from models.balanced_random_forest import BalancedRandomForestModel
from models.xgboost_model import XGBoostModel
from models.lightgbm_model import LightGBMModel
from models.mlp_model import MLPModel
from models.kan_model import KANModel
from training.trainer import Trainer
from evaluation.benchmark import Benchmark
from utils.gpu_utils import log_device_info, get_mixed_precision_flag

init(autoreset=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Full end-to-end training pipeline for all configured models."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        self.preprocessor = HeatwavePreprocessor(config_path)

    # ------------------------------------------------------------------
    def run(self, selected_models: list = None):
        """
        Execute the full pipeline.
        selected_models: list of model keys to train (e.g. ['xgboost', 'mlp']).
                         Pass None to train all 5 models.
        """
        self._print_banner()
        device_msg = log_device_info(self.config_path)
        amp_enabled = get_mixed_precision_flag(self.config_path)
        training_cfg = self.cfg.get("training", {})
        batch_size = training_cfg.get("batch_size", 512)
        print(f"  {device_msg}")
        print(f"  Mixed Precision (AMP): {'✓ Enabled (FP16)' if amp_enabled else '✗ Disabled (FP32)'}")
        print(f"  Batch Size: {batch_size}")

        # ── Step 1: Load data ──────────────────────────────────────────
        print(f"\n{Fore.CYAN}[Step 1/4] Loading ERA5 data...{Style.RESET_ALL}")
        loader = ERA5DataLoader(self.config_path)
        df = loader.load()
        print(f"  ✓ Loaded {len(df):,} samples")

        # ── Step 2: Preprocess ─────────────────────────────────────────
        print(f"\n{Fore.CYAN}[Step 2/4] Preprocessing...{Style.RESET_ALL}")
        X_train, X_val, X_test, y_train, y_val, y_test, feature_names = \
            self.preprocessor.fit_transform(df)
        print(f"  ✓ Features: {feature_names}")
        print(f"  ✓ Train={len(X_train):,} | Val={len(X_val):,} | Test={len(X_test):,}")
        print(f"  ✓ Heatwave rate: train={y_train.mean():.2%} | test={y_test.mean():.2%}")

        # Save scaler for prediction use
        scaler_path = os.path.join(self.cfg["experiments"]["models_dir"], "scaler.pkl")
        self.preprocessor.save_scaler(scaler_path)

        # Save feature names
        feature_path = os.path.join(self.cfg["experiments"]["models_dir"], "feature_names.pkl")
        joblib.dump(feature_names, feature_path)

        # ── Step 3: Train each model ───────────────────────────────────
        print(f"\n{Fore.CYAN}[Step 3/4] Training models...{Style.RESET_ALL}")
        models = self._get_models(selected_models)
        if selected_models:
            print(f"  Selected: {[m.get_model_name() for m in models]}")
        all_results = []

        for model in models:
            name = model.get_model_name()
            print(f"\n  {Fore.YELLOW}▶ {name}{Style.RESET_ALL}")
            try:
                trainer = Trainer(model, self.config_path)
                metrics = trainer.run(X_train, y_train, X_val, y_val, X_test, y_test)
                all_results.append(metrics)
                print(f"  {Fore.GREEN}✓ F1={metrics['f1_score']:.4f} | "
                      f"Acc={metrics['accuracy']:.4f} | "
                      f"Precision={metrics['precision']:.4f} | "
                      f"Recall={metrics['recall']:.4f}{Style.RESET_ALL}")
            except Exception as e:
                logger.error("Failed training %s: %s", name, e)
                print(f"  {Fore.RED}✗ {name} failed: {e}{Style.RESET_ALL}")

        # ── Step 4: Update leaderboard ─────────────────────────────────
        print(f"\n{Fore.CYAN}[Step 4/4] Updating leaderboard...{Style.RESET_ALL}")
        bench = Benchmark(self.cfg["experiments"]["results_dir"])
        bench.save_leaderboard(self.cfg["experiments"]["leaderboard_file"])
        bench.print_leaderboard()

        print(f"\n{Fore.GREEN}{'=' * 60}")
        print(f"  Pipeline complete! {len(all_results)}/{len(models)} models trained.")
        print(f"{'=' * 60}{Style.RESET_ALL}\n")

        return all_results

    # ------------------------------------------------------------------
    # Model registry — key = CLI name, value = class
    MODEL_REGISTRY = {
        "balanced_rf":  BalancedRandomForestModel,
        "xgboost":      XGBoostModel,
        "lightgbm":     LightGBMModel,
        "mlp":          MLPModel,
        "kan":          KANModel,
    }

    def _get_models(self, selected: list = None):
        """
        Return model instances.
        selected: list of model keys (e.g. ['xgboost', 'mlp']).
                  If None or empty, return all 5 models.
        """
        registry = self.MODEL_REGISTRY
        if selected:
            # Normalise input
            keys = [s.lower().strip() for s in selected]
            unknown = [k for k in keys if k not in registry]
            if unknown:
                logger.warning("Unknown model(s) ignored: %s. Valid: %s", unknown, list(registry))
            keys = [k for k in keys if k in registry]
        else:
            keys = list(registry.keys())
        return [registry[k](self.config_path) for k in keys]

    def _print_banner(self):
        print(f"\n{Fore.MAGENTA}{'=' * 60}")
        print("  HEATWAVE-AI  |  Training Pipeline")
        print(f"  Project: {self.cfg['project']['name']}")
        print(f"{'=' * 60}{Style.RESET_ALL}")


# ------------------------------------------------------------------
if __name__ == "__main__":
    pipeline = TrainingPipeline()
    pipeline.run()
