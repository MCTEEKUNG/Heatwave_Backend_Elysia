"""
train_split.py
Split training into CPU (Balanced Random Forest) and GPU (XGBoost, LightGBM, MLP, KAN).

Strategy:
  Phase 1 — Preprocess once, save numpy arrays to disk  (~3–5 min)
  Phase 2 — BRF   trains from cached arrays on CPU      (~5–8 min)
  Phase 3 — GPU   models train from cached arrays on GPU (~20–40 min total)
  Phases 2 & 3 run IN PARALLEL → overall wall time ≈ Phase 1 + Phase 3

Usage (Colab):
    !python train_split.py --phase preprocess
    !python train_split.py --phase brf &         # background (CPU)
    !python train_split.py --phase gpu            # foreground (GPU)

  Or run everything automatically:
    !python train_split.py --phase all
"""

import os
import sys
import argparse
import logging
import time
import json

import numpy as np
import joblib
import yaml
from colorama import init, Fore, Style

init(autoreset=True)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ── Where cached numpy arrays are stored ──────────────────────────────────────
CACHE_DIR = "experiments/cache"

GPU_MODELS  = ["xgboost", "lightgbm", "mlp", "kan"]
CPU_MODELS  = ["balanced_rf"]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Preprocess & cache
# ─────────────────────────────────────────────────────────────────────────────

def phase_preprocess(config_path: str):
    from utils.data_loader import ERA5DataLoader
    from utils.preprocessing import HeatwavePreprocessor

    print(f"\n{Fore.MAGENTA}{'='*60}")
    print("  PHASE 1 — Preprocessing (runs once for all models)")
    print(f"{'='*60}{Style.RESET_ALL}")

    os.makedirs(CACHE_DIR, exist_ok=True)

    # Load ERA5 + NDVI
    print(f"\n{Fore.CYAN}[1/2] Loading ERA5 data...{Style.RESET_ALL}")
    loader = ERA5DataLoader(config_path)
    df = loader.load()
    print(f"  ✓ {len(df):,} samples loaded")

    # Preprocess
    print(f"\n{Fore.CYAN}[2/2] Preprocessing + splitting...{Style.RESET_ALL}")
    prep = HeatwavePreprocessor(config_path)
    X_train, X_val, X_test, y_train, y_val, y_test, feature_names = prep.fit_transform(df)

    print(f"  ✓ Features  : {feature_names}")
    print(f"  ✓ Train={len(X_train):,} | Val={len(X_val):,} | Test={len(X_test):,}")
    print(f"  ✓ Heatwave  : train={y_train.mean():.2%} | test={y_test.mean():.2%}")

    # Save arrays
    np.save(f"{CACHE_DIR}/X_train.npy", X_train)
    np.save(f"{CACHE_DIR}/X_val.npy",   X_val)
    np.save(f"{CACHE_DIR}/X_test.npy",  X_test)
    np.save(f"{CACHE_DIR}/y_train.npy", y_train)
    np.save(f"{CACHE_DIR}/y_val.npy",   y_val)
    np.save(f"{CACHE_DIR}/y_test.npy",  y_test)

    # Save scaler + feature names (same as normal pipeline)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    models_dir = cfg["experiments"]["models_dir"]
    os.makedirs(models_dir, exist_ok=True)

    prep.save_scaler(os.path.join(models_dir, "scaler.pkl"))
    joblib.dump(feature_names, os.path.join(models_dir, "feature_names.pkl"))

    # Save metadata
    meta = {
        "feature_names": feature_names,
        "n_train": len(X_train),
        "n_val":   len(X_val),
        "n_test":  len(X_test),
        "heatwave_rate_train": float(y_train.mean()),
        "heatwave_rate_test":  float(y_test.mean()),
    }
    with open(f"{CACHE_DIR}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{Fore.GREEN}✅ Cache saved to {CACHE_DIR}/")
    print(f"   X_train : {X_train.shape}  ({X_train.nbytes/1e9:.2f} GB)")
    print(f"   Ready for BRF (CPU) and GPU models to train in parallel{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Shared — load cached arrays
# ─────────────────────────────────────────────────────────────────────────────

def load_cache():
    required = ["X_train.npy","X_val.npy","X_test.npy",
                "y_train.npy","y_val.npy","y_test.npy","meta.json"]
    missing = [f for f in required if not os.path.isfile(f"{CACHE_DIR}/{f}")]
    if missing:
        print(f"{Fore.RED}❌ Cache missing: {missing}")
        print(f"   Run first: python train_split.py --phase preprocess{Style.RESET_ALL}")
        sys.exit(1)

    X_train = np.load(f"{CACHE_DIR}/X_train.npy")
    X_val   = np.load(f"{CACHE_DIR}/X_val.npy")
    X_test  = np.load(f"{CACHE_DIR}/X_test.npy")
    y_train = np.load(f"{CACHE_DIR}/y_train.npy")
    y_val   = np.load(f"{CACHE_DIR}/y_val.npy")
    y_test  = np.load(f"{CACHE_DIR}/y_test.npy")

    with open(f"{CACHE_DIR}/meta.json") as f:
        meta = json.load(f)

    print(f"  ✓ Cache loaded — Train={len(X_train):,} | Val={len(X_val):,} | Test={len(X_test):,}")
    print(f"  ✓ Features    : {meta['feature_names']}")
    print(f"  ✓ Heatwave    : train={meta['heatwave_rate_train']:.2%} | test={meta['heatwave_rate_test']:.2%}")
    return X_train, X_val, X_test, y_train, y_val, y_test


# ─────────────────────────────────────────────────────────────────────────────
# Shared — train + evaluate + save one model
# ─────────────────────────────────────────────────────────────────────────────

def train_model(model_key: str, config_path: str,
                X_train, y_train, X_val, y_val, X_test, y_test):
    from training.trainer import Trainer
    from pipelines.training_pipeline import TrainingPipeline

    model_cls = TrainingPipeline.MODEL_REGISTRY.get(model_key)
    if model_cls is None:
        print(f"{Fore.RED}  ✗ Unknown model key: {model_key}{Style.RESET_ALL}")
        return None

    model   = model_cls(config_path)
    name    = model.get_model_name()
    trainer = Trainer(model, config_path)

    print(f"\n  {Fore.YELLOW}▶ {name}{Style.RESET_ALL}")
    try:
        metrics = trainer.run(X_train, y_train, X_val, y_val, X_test, y_test)
        print(f"  {Fore.GREEN}✓ F1={metrics['f1_score']:.4f} | "
              f"Prec={metrics['precision']:.4f} | "
              f"Rec={metrics['recall']:.4f} | "
              f"AUC={metrics['roc_auc']:.4f}{Style.RESET_ALL}")
        return metrics
    except Exception as e:
        logger.error("Failed training %s: %s", name, e, exc_info=True)
        print(f"  {Fore.RED}✗ {name} failed: {e}{Style.RESET_ALL}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — BRF on CPU
# ─────────────────────────────────────────────────────────────────────────────

def phase_brf(config_path: str):
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print("  PHASE 2 — Balanced Random Forest  [CPU]")
    print(f"{'='*60}{Style.RESET_ALL}")

    X_train, X_val, X_test, y_train, y_val, y_test = load_cache()

    t0 = time.time()
    train_model("balanced_rf", config_path, X_train, y_train, X_val, y_val, X_test, y_test)
    print(f"\n{Fore.GREEN}✅ BRF done in {(time.time()-t0)/60:.1f} min{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — GPU models
# ─────────────────────────────────────────────────────────────────────────────

def phase_gpu(config_path: str):
    import torch

    print(f"\n{Fore.MAGENTA}{'='*60}")
    print("  PHASE 3 — GPU Models  [XGBoost · LightGBM · MLP · KAN]")
    print(f"{'='*60}{Style.RESET_ALL}")

    gpu_available = torch.cuda.is_available()
    if gpu_available:
        print(f"  GPU : {Fore.GREEN}{torch.cuda.get_device_name(0)}{Style.RESET_ALL}")
    else:
        print(f"  {Fore.YELLOW}⚠ No GPU detected — falling back to CPU for MLP/KAN{Style.RESET_ALL}")
        print("  Tip: Runtime → Change runtime type → T4 GPU")

    X_train, X_val, X_test, y_train, y_val, y_test = load_cache()

    t0 = time.time()
    results = []
    for key in GPU_MODELS:
        m = train_model(key, config_path, X_train, y_train, X_val, y_val, X_test, y_test)
        if m:
            results.append(m)

    print(f"\n{Fore.GREEN}✅ GPU models done in {(time.time()-t0)/60:.1f} min{Style.RESET_ALL}\n")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Phase ALL — auto parallel (BRF background, GPU foreground)
# ─────────────────────────────────────────────────────────────────────────────

def phase_all(config_path: str):
    import subprocess
    import threading

    # Step 1: preprocess
    phase_preprocess(config_path)

    print(f"\n{Fore.CYAN}Launching BRF (CPU) in background and GPU models in foreground...{Style.RESET_ALL}")

    brf_done = {"success": False}

    def run_brf_subprocess():
        result = subprocess.run(
            [sys.executable, __file__, "--phase", "brf", "--config", config_path],
            text=True
        )
        brf_done["success"] = (result.returncode == 0)

    # BRF in background thread (runs as separate subprocess)
    brf_thread = threading.Thread(target=run_brf_subprocess, name="BRF-CPU", daemon=True)
    brf_thread.start()

    # GPU models in foreground (main process)
    phase_gpu(config_path)

    # Wait for BRF to finish
    print(f"\n{Fore.CYAN}Waiting for BRF to finish...{Style.RESET_ALL}")
    brf_thread.join()

    status = f"{Fore.GREEN}✅ success{Style.RESET_ALL}" if brf_done["success"] else f"{Fore.RED}❌ failed{Style.RESET_ALL}"
    print(f"  BRF status: {status}")

    # Update leaderboard
    print(f"\n{Fore.CYAN}Updating leaderboard...{Style.RESET_ALL}")
    from evaluation.benchmark import Benchmark
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    bench = Benchmark(cfg["experiments"]["results_dir"])
    bench.save_leaderboard(cfg["experiments"]["leaderboard_file"])
    bench.print_leaderboard()

    print(f"\n{Fore.GREEN}{'='*60}")
    print("  All models trained! Save to Drive:")
    print("  python train_split.py --phase save")
    print(f"{'='*60}{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Phase SAVE — copy .pkl files to Google Drive
# ─────────────────────────────────────────────────────────────────────────────

def phase_save(config_path: str):
    import shutil

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    models_dir = cfg["experiments"]["models_dir"]
    save_dir   = "/content/drive/MyDrive/Heatwave-AI/trained_models"
    os.makedirs(save_dir, exist_ok=True)

    print(f"\n{Fore.CYAN}Saving models to Google Drive...{Style.RESET_ALL}")
    saved = []
    for fname in os.listdir(models_dir):
        if fname.endswith(".pkl"):
            src = os.path.join(models_dir, fname)
            dst = os.path.join(save_dir, fname)
            shutil.copy2(src, dst)
            size = os.path.getsize(dst) / 1e6
            print(f"  ✓ {fname}  ({size:.1f} MB)")
            saved.append(fname)

    print(f"\n{Fore.GREEN}✅ {len(saved)} files saved → {save_dir}{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Heatwave-AI Split Trainer")
    parser.add_argument(
        "--phase",
        required=True,
        choices=["preprocess", "brf", "gpu", "all", "save"],
        help=(
            "preprocess — load ERA5+NDVI, save numpy cache\n"
            "brf        — train Balanced RF from cache (CPU)\n"
            "gpu        — train XGBoost/LightGBM/MLP/KAN from cache (GPU)\n"
            "all        — run preprocess → brf+gpu in parallel → save\n"
            "save       — copy .pkl files to Google Drive"
        )
    )
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    phases = {
        "preprocess": phase_preprocess,
        "brf":        phase_brf,
        "gpu":        phase_gpu,
        "all":        phase_all,
        "save":       phase_save,
    }
    phases[args.phase](args.config)


if __name__ == "__main__":
    main()
