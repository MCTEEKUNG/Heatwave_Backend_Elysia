"""
train_split.py
Two-session training: CPU for Balanced Random Forest, GPU for the rest.

Workflow:
  Session 1 — CPU runtime in Colab
    Step 1: python train_split.py --phase preprocess   (saves cache to Drive)
    Step 2: python train_split.py --phase brf          (trains BRF from cache)

  Session 2 — H100 GPU runtime in Colab (reconnect, re-run setup cells)
    Step 3: python train_split.py --phase gpu          (trains XGBoost/LightGBM/MLP/KAN)
    Step 4: python train_split.py --phase save         (copies .pkl to Drive)

Cache is saved to Google Drive so it survives the runtime switch.
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

# ── Google Drive paths ────────────────────────────────────────────────────────
DRIVE_BASE  = "/content/drive/MyDrive/Heatwave-AI"
CACHE_DIR   = f"{DRIVE_BASE}/cache"          # preprocessed numpy arrays live here
MODELS_DIR  = f"{DRIVE_BASE}/trained_models" # .pkl files saved here after training


def _banner(title: str, color=Fore.MAGENTA):
    print(f"\n{color}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Style.RESET_ALL}")


def _check_drive():
    if not os.path.isdir("/content/drive/MyDrive"):
        print(f"{Fore.RED}❌ Google Drive not mounted.")
        print(f"   Run:  from google.colab import drive; drive.mount('/content/drive'){Style.RESET_ALL}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Phase: preprocess
# ─────────────────────────────────────────────────────────────────────────────

def phase_preprocess(config_path: str):
    """Load ERA5 + NDVI → preprocess → save numpy arrays to Google Drive."""

    _check_drive()
    _banner("PREPROCESS  —  Load · Feature Engineering · Split · Cache to Drive")

    from utils.data_loader import ERA5DataLoader
    from utils.preprocessing import HeatwavePreprocessor

    os.makedirs(CACHE_DIR, exist_ok=True)

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}[1/3] Loading ERA5 + NDVI data...{Style.RESET_ALL}")
    loader = ERA5DataLoader(config_path)
    df = loader.load()
    print(f"  ✓ {len(df):,} samples loaded")

    # ── Preprocess ────────────────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}[2/3] Feature engineering + split...{Style.RESET_ALL}")
    prep = HeatwavePreprocessor(config_path)
    X_train, X_val, X_test, y_train, y_val, y_test, feature_names = \
        prep.fit_transform(df)

    print(f"  ✓ Features : {feature_names}")
    print(f"  ✓ Samples  : train={len(X_train):,} | val={len(X_val):,} | test={len(X_test):,}")
    print(f"  ✓ Heatwave : train={y_train.mean():.2%} | test={y_test.mean():.2%}")

    # ── Save cache to Drive ───────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}[3/3] Saving cache to Google Drive...{Style.RESET_ALL}")
    np.save(f"{CACHE_DIR}/X_train.npy", X_train)
    np.save(f"{CACHE_DIR}/X_val.npy",   X_val)
    np.save(f"{CACHE_DIR}/X_test.npy",  X_test)
    np.save(f"{CACHE_DIR}/y_train.npy", y_train)
    np.save(f"{CACHE_DIR}/y_val.npy",   y_val)
    np.save(f"{CACHE_DIR}/y_test.npy",  y_test)

    # Save scaler + feature names into Drive cache too
    prep.save_scaler(f"{CACHE_DIR}/scaler.pkl")
    joblib.dump(feature_names, f"{CACHE_DIR}/feature_names.pkl")

    meta = {
        "feature_names":         feature_names,
        "n_train":               len(X_train),
        "n_val":                 len(X_val),
        "n_test":                len(X_test),
        "heatwave_rate_train":   float(y_train.mean()),
        "heatwave_rate_test":    float(y_test.mean()),
        "X_train_shape":         list(X_train.shape),
    }
    with open(f"{CACHE_DIR}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{Fore.GREEN}✅ Cache saved to {CACHE_DIR}")
    for fname in ["X_train.npy","X_val.npy","X_test.npy",
                  "y_train.npy","y_val.npy","y_test.npy","scaler.pkl","feature_names.pkl"]:
        path = f"{CACHE_DIR}/{fname}"
        mb = os.path.getsize(path) / 1e6
        print(f"   {fname:<25} {mb:>8.1f} MB")

    print(f"\n  Next step (still on CPU session):")
    print(f"  {Fore.YELLOW}python train_split.py --phase brf{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Shared: load cache from Drive
# ─────────────────────────────────────────────────────────────────────────────

def load_cache():
    _check_drive()

    required = [
        "X_train.npy", "X_val.npy", "X_test.npy",
        "y_train.npy", "y_val.npy", "y_test.npy", "meta.json"
    ]
    missing = [f for f in required if not os.path.isfile(f"{CACHE_DIR}/{f}")]
    if missing:
        print(f"{Fore.RED}❌ Cache files missing: {missing}")
        print(f"   Run first:  python train_split.py --phase preprocess{Style.RESET_ALL}")
        sys.exit(1)

    print(f"{Fore.CYAN}  Loading cache from Drive...{Style.RESET_ALL}")
    X_train = np.load(f"{CACHE_DIR}/X_train.npy")
    X_val   = np.load(f"{CACHE_DIR}/X_val.npy")
    X_test  = np.load(f"{CACHE_DIR}/X_test.npy")
    y_train = np.load(f"{CACHE_DIR}/y_train.npy")
    y_val   = np.load(f"{CACHE_DIR}/y_val.npy")
    y_test  = np.load(f"{CACHE_DIR}/y_test.npy")

    with open(f"{CACHE_DIR}/meta.json") as f:
        meta = json.load(f)

    print(f"  ✓ Features  : {meta['feature_names']}")
    print(f"  ✓ Samples   : train={meta['n_train']:,} | val={meta['n_val']:,} | test={meta['n_test']:,}")
    print(f"  ✓ Heatwave  : train={meta['heatwave_rate_train']:.2%} | test={meta['heatwave_rate_test']:.2%}")

    return X_train, X_val, X_test, y_train, y_val, y_test


# ─────────────────────────────────────────────────────────────────────────────
# Shared: train one model
# ─────────────────────────────────────────────────────────────────────────────

def train_one(model_key: str, config_path: str,
              X_train, y_train, X_val, y_val, X_test, y_test):

    from training.trainer import Trainer
    from pipelines.training_pipeline import TrainingPipeline

    model_cls = TrainingPipeline.MODEL_REGISTRY.get(model_key)
    if model_cls is None:
        print(f"{Fore.RED}  ✗ Unknown model: {model_key}{Style.RESET_ALL}")
        return None

    model   = model_cls(config_path)
    trainer = Trainer(model, config_path)
    name    = model.get_model_name()

    print(f"\n  {Fore.YELLOW}▶ {name}{Style.RESET_ALL}")
    t0 = time.time()
    try:
        metrics = trainer.run(X_train, y_train, X_val, y_val, X_test, y_test)
        elapsed = time.time() - t0
        print(f"  {Fore.GREEN}✓ Done in {elapsed/60:.1f} min")
        print(f"    F1={metrics['f1_score']:.4f} | "
              f"Precision={metrics['precision']:.4f} | "
              f"Recall={metrics['recall']:.4f} | "
              f"ROC-AUC={metrics['roc_auc']:.4f}{Style.RESET_ALL}")
        return metrics
    except Exception as e:
        logger.error("Training %s failed: %s", name, e, exc_info=True)
        print(f"  {Fore.RED}✗ {name} failed: {e}{Style.RESET_ALL}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase: brf  (CPU session)
# ─────────────────────────────────────────────────────────────────────────────

def phase_brf(config_path: str):
    """Train Balanced Random Forest from cached arrays. Run on CPU session."""

    _banner("BRF  —  Balanced Random Forest  [CPU]", Fore.CYAN)

    X_train, X_val, X_test, y_train, y_val, y_test = load_cache()

    t0 = time.time()
    metrics = train_one(
        "balanced_rf", config_path,
        X_train, y_train, X_val, y_val, X_test, y_test
    )

    if metrics:
        print(f"\n{Fore.GREEN}✅ BRF complete in {(time.time()-t0)/60:.1f} min")
        print(f"\n  Now:")
        print(f"  1. Switch Colab runtime → H100 GPU")
        print(f"  2. Re-run your setup cells (mount Drive, git pull, pip install)")
        print(f"  3. Run:  {Fore.YELLOW}python train_split.py --phase gpu{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Phase: gpu  (H100 session)
# ─────────────────────────────────────────────────────────────────────────────

def phase_gpu(config_path: str):
    """Train XGBoost, LightGBM, MLP, KAN from cached arrays. Run on H100 session."""

    _banner("GPU  —  XGBoost · LightGBM · MLP · KAN  [H100]", Fore.YELLOW)

    import torch
    if torch.cuda.is_available():
        print(f"  {Fore.GREEN}GPU : {torch.cuda.get_device_name(0)}{Style.RESET_ALL}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print(f"  {Fore.RED}⚠ No GPU detected — switch runtime to H100 GPU{Style.RESET_ALL}")
        sys.exit(1)

    X_train, X_val, X_test, y_train, y_val, y_test = load_cache()

    gpu_models = ["xgboost", "lightgbm", "mlp", "kan"]
    results = []
    t0 = time.time()

    for key in gpu_models:
        m = train_one(key, config_path, X_train, y_train, X_val, y_val, X_test, y_test)
        if m:
            results.append((key, m))

    total = time.time() - t0

    # Summary table
    print(f"\n{Fore.CYAN}{'─'*60}")
    print(f"  {'Model':<20} {'F1':>8} {'Prec':>8} {'Recall':>8} {'AUC':>8}")
    print(f"{'─'*60}{Style.RESET_ALL}")
    for key, m in results:
        print(f"  {key:<20} {m['f1_score']:>8.4f} {m['precision']:>8.4f} "
              f"{m['recall']:>8.4f} {m['roc_auc']:>8.4f}")

    print(f"\n{Fore.GREEN}✅ GPU training complete in {total/60:.1f} min")
    print(f"  Next step:  {Fore.YELLOW}python train_split.py --phase save{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Phase: save  (copy .pkl → Drive)
# ─────────────────────────────────────────────────────────────────────────────

def phase_save(config_path: str):
    """Copy all trained .pkl files to Google Drive."""

    _check_drive()
    _banner("SAVE  —  Copy models to Google Drive", Fore.GREEN)

    import shutil
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    local_models_dir = cfg["experiments"]["models_dir"]
    os.makedirs(MODELS_DIR, exist_ok=True)

    saved = []
    for fname in sorted(os.listdir(local_models_dir)):
        src = os.path.join(local_models_dir, fname)
        dst = os.path.join(MODELS_DIR, fname)
        shutil.copy2(src, dst)
        mb = os.path.getsize(dst) / 1e6
        print(f"  ✓ {fname:<45} {mb:>8.1f} MB")
        saved.append(fname)

    print(f"\n{Fore.GREEN}✅ {len(saved)} files saved to {MODELS_DIR}")
    print(f"\n  Upload .pkl files to HuggingFace, then redeploy Render.{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Heatwave-AI Split Trainer (CPU session → GPU session)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  preprocess  Load ERA5+NDVI, preprocess, save numpy cache to Drive  [CPU session]
  brf         Train Balanced Random Forest from cache                 [CPU session]
  gpu         Train XGBoost / LightGBM / MLP / KAN from cache        [H100 session]
  save        Copy all .pkl model files to Google Drive               [any session]
        """
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=["preprocess", "brf", "gpu", "save"],
    )
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    dispatch = {
        "preprocess": phase_preprocess,
        "brf":        phase_brf,
        "gpu":        phase_gpu,
        "save":       phase_save,
    }
    dispatch[args.phase](args.config)


if __name__ == "__main__":
    main()
