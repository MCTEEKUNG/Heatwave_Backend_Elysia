"""
models/mlp_model.py
Multi-Layer Perceptron using PyTorch with:
  - GPU acceleration (auto-detected)
  - Mixed Precision Training (FP16 AMP via torch.cuda.amp)
  - Batch training via DataLoader (pin_memory for faster GPU transfers)
  - Early stopping
"""
import os
import logging
import numpy as np
import joblib
import yaml
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from torch.amp import GradScaler, autocast
from models.base_model import BaseModel
from evaluation.metrics import compute_metrics
from utils.gpu_utils import get_device, get_use_gpu_flag, get_mixed_precision_flag

logger = logging.getLogger(__name__)


class _MLPNet(nn.Module):
    def __init__(self, input_dim: int, hidden_layers: list, dropout: float):
        super().__init__()
        layers = []
        prev = input_dim
        for h in hidden_layers:
            layers += [nn.Linear(prev, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


class MLPModel(BaseModel):
    """PyTorch MLP with GPU acceleration, AMP mixed precision, and early stopping."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        params = cfg["models"]["mlp"]
        training_cfg = cfg.get("training", {})

        self.hidden_layers = params.get("hidden_layers", [256, 128, 64])
        self.dropout = params.get("dropout", 0.3)
        self.lr = params.get("learning_rate", 0.001)
        # batch_size: prefer training-level override, then model-level
        self.batch_size = training_cfg.get("batch_size", params.get("batch_size", 512))
        self.max_epochs = params.get("max_epochs", 100)
        self.patience = params.get("patience", 10)
        torch.manual_seed(params.get("random_state", 42))

        use_gpu = get_use_gpu_flag(config_path)
        self.device = get_device(use_gpu)
        self.use_amp = get_mixed_precision_flag(config_path)
        self._amp_device = "cuda" if self.device.type == "cuda" else "cpu"
        self.net = None
        self.input_dim = None

        logger.info(
            "MLPModel init — device=%s | AMP=%s | batch_size=%d",
            self.device, self.use_amp, self.batch_size
        )

    def get_model_name(self) -> str:
        return "MLP Neural Network"

    def train(self, X_train, y_train, X_val=None, y_val=None):
        logger.info("Training %s on %s (AMP=%s) ...", self.get_model_name(), self.device, self.use_amp)
        self.input_dim = X_train.shape[1]
        self.net = _MLPNet(self.input_dim, self.hidden_layers, self.dropout).to(self.device)

        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr)

        # Weight positive class inversely to its frequency (handles imbalance)
        neg = int((y_train == 0).sum())
        pos = int((y_train == 1).sum())
        pw  = torch.tensor([neg / max(pos, 1)], dtype=torch.float32).to(self.device)
        logger.info("pos_weight=%.1f  (neg=%d pos=%d)", pw.item(), neg, pos)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pw)
        scaler = GradScaler(device=self._amp_device, enabled=self.use_amp)

        # Build DataLoader — pin_memory speeds up CPU→GPU transfers
        pin = self.device.type == "cuda"
        X_t = torch.FloatTensor(X_train)
        y_t = torch.FloatTensor(y_train)
        loader = DataLoader(
            TensorDataset(X_t, y_t),
            batch_size=self.batch_size,
            shuffle=True,
            pin_memory=pin,
            num_workers=0,  # 0 = main process (safe on Windows)
        )

        best_val_loss = float("inf")
        wait = 0

        for epoch in range(self.max_epochs):
            self.net.train()
            for xb, yb in loader:
                xb = xb.to(self.device, non_blocking=pin)
                yb = yb.to(self.device, non_blocking=pin)

                optimizer.zero_grad()
                with autocast(device_type=self._amp_device, enabled=self.use_amp):
                    loss = criterion(self.net(xb), yb)

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            # Periodic GPU cache clear to avoid fragmentation
            if self.device.type == "cuda" and (epoch + 1) % 10 == 0:
                torch.cuda.empty_cache()

            if X_val is not None:
                val_loss = self._val_loss(X_val, y_val, criterion)
                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    wait = 0
                    self._best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
                else:
                    wait += 1
                    if wait >= self.patience:
                        logger.info("Early stopping at epoch %d", epoch + 1)
                        break

        if hasattr(self, "_best_state"):
            self.net.load_state_dict(self._best_state)

        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        logger.info("Training complete.")

    def _val_loss(self, X_val, y_val, criterion):
        self.net.eval()
        with torch.no_grad():
            xv = torch.FloatTensor(X_val).to(self.device)
            yv = torch.FloatTensor(y_val).to(self.device)
            with autocast(device_type=self._amp_device, enabled=self.use_amp):
                loss = criterion(self.net(xv), yv)
            return loss.item()

    def predict(self, X) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            xt = torch.FloatTensor(X).to(self.device)
            with autocast(device_type=self._amp_device, enabled=self.use_amp):
                logits = self.net(xt)
            return (torch.sigmoid(logits) >= 0.5).long().cpu().numpy()

    def predict_proba(self, X) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            xt = torch.FloatTensor(X).to(self.device)
            with autocast(device_type=self._amp_device, enabled=self.use_amp):
                logits = self.net(xt)
            return torch.sigmoid(logits).cpu().numpy()

    def evaluate(self, X_test, y_test) -> dict:
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)
        return compute_metrics(y_test, y_pred, y_proba, self.get_model_name())

    def save_model(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "state_dict": self.net.state_dict(),
            "input_dim": self.input_dim,
            "hidden_layers": self.hidden_layers,
            "dropout": self.dropout,
        }
        joblib.dump(payload, path)
        logger.info("Model saved: %s", path)

    def load_model(self, path: str):
        payload = joblib.load(path)
        self.input_dim = payload["input_dim"]
        self.hidden_layers = payload["hidden_layers"]
        self.dropout = payload["dropout"]
        self.net = _MLPNet(self.input_dim, self.hidden_layers, self.dropout).to(self.device)
        self.net.load_state_dict(payload["state_dict"])
        self.net.eval()
        logger.info("Model loaded: %s", path)
