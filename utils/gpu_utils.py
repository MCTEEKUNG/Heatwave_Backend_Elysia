"""
utils/gpu_utils.py
Shared GPU/device detection utility used by all models and the pipeline.

Usage:
    from utils.gpu_utils import get_device, gpu_available, log_device_info

    device = get_device(use_gpu=True)   # returns torch.device
    avail  = gpu_available()            # bool
    log_device_info()                   # prints to logger
"""
import logging
import yaml

logger = logging.getLogger(__name__)

# ── PyTorch (optional, safe import) ──────────────────────────────
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


def gpu_available() -> bool:
    """True if a CUDA GPU is visible to PyTorch."""
    if not _TORCH_AVAILABLE:
        return False
    return torch.cuda.is_available()


def get_device(use_gpu: bool = True):
    """
    Return the best available torch.device respecting the use_gpu flag.

    Parameters
    ----------
    use_gpu : bool
        When True, prefer CUDA if available. When False, always CPU.

    Returns
    -------
    torch.device
    """
    if not _TORCH_AVAILABLE:
        return None
    if use_gpu and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_use_gpu_flag(config_path: str = "config/config.yaml") -> bool:
    """Read the training.use_gpu flag from config. Defaults to True."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return bool(cfg.get("training", {}).get("use_gpu", True))
    except Exception:
        return True


def get_mixed_precision_flag(config_path: str = "config/config.yaml") -> bool:
    """
    Read the training.mixed_precision flag from config.
    Returns True only when mixed_precision=true AND a CUDA GPU is available.
    Falls back to False on CPU-only environments.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        amp_cfg = bool(cfg.get("training", {}).get("mixed_precision", True))
    except Exception:
        amp_cfg = True
    # AMP only makes sense on CUDA
    return amp_cfg and gpu_available()


def log_device_info(config_path: str = "config/config.yaml") -> str:
    """
    Log detected training device and return device string for display.
    Call this at pipeline startup before training begins.
    """
    use_gpu = get_use_gpu_flag(config_path)

    if not _TORCH_AVAILABLE:
        msg = "Training device: CPU  (PyTorch not installed)"
        logger.info(msg)
        return msg

    if not use_gpu:
        msg = "Training device: CPU  (GPU disabled in config)"
        logger.info(msg)
        return msg

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        msg = f"Training device: GPU (CUDA) — {gpu_name} | {vram:.1f} GB VRAM"
        logger.info(msg)
        return msg
    else:
        msg = "Training device: CPU  (no CUDA GPU detected — falling back)"
        logger.warning(msg)
        return msg


def xgboost_device_params(config_path: str = "config/config.yaml") -> dict:
    """
    Return XGBoost constructor kwargs for GPU or CPU depending on config.
    Compatible with XGBoost >= 2.0 (uses device= parameter).
    Older XGBoost uses tree_method='gpu_hist', handled via try/except in caller.
    """
    use_gpu = get_use_gpu_flag(config_path)
    if use_gpu and gpu_available():
        logger.info("XGBoost will use: GPU (CUDA)")
        return {"tree_method": "hist", "device": "cuda"}
    else:
        logger.info("XGBoost will use: CPU")
        return {"tree_method": "hist", "device": "cpu"}


def lightgbm_device_params(config_path: str = "config/config.yaml") -> dict:
    """
    Return LightGBM constructor kwargs for GPU or CPU depending on config.
    """
    use_gpu = get_use_gpu_flag(config_path)
    if use_gpu and gpu_available():
        logger.info("LightGBM will use: GPU")
        return {"device_type": "gpu"}
    else:
        logger.info("LightGBM will use: CPU")
        return {}   # No device_type = defaults to CPU
