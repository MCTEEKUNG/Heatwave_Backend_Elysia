"""
models/kan_model.py
Kolmogorov-Arnold Network (KAN) approximated with learnable B-spline activations in PyTorch.

The KAN concept replaces fixed nonlinear activations with learnable spline functions
on each edge/connection, allowing the network to learn its own activation shapes.
This is a practical lightweight implementation suitable for tabular classification.

Enhancements:
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


class KANLayer(nn.Module):
    """
    A single KAN layer: learnable B-spline activation per input dimension,
    followed by a linear combination to output dimension.
    """

    def __init__(self, in_dim: int, out_dim: int, grid_size: int = 5, spline_order: int = 3):
        super().__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.grid_size = grid_size
        self.spline_order = spline_order

        # Learnable spline control points: (in_dim, grid_size)
        self.spline_weights = nn.Parameter(torch.randn(in_dim, grid_size) * 0.1)
        # Linear mixing: (in_dim * grid_size, out_dim)
        self.linear = nn.Linear(in_dim * grid_size, out_dim)
        # Residual scaling
        self.base_weight = nn.Parameter(torch.randn(in_dim, out_dim) * 0.1)
        self.base_activation = nn.SiLU()

    def _b_spline_basis(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute B-spline basis values for input x.
        x: (batch, in_dim)
        Returns: (batch, in_dim, grid_size)
        """
        # Normalise input to [0, 1] via sigmoid
        x_norm = torch.sigmoid(x)  # (batch, in_dim)
        # Uniform knots in [0, 1]
        knots = torch.linspace(0.0, 1.0, self.grid_size, device=x.device)  # (G,)
        # Gaussian-like basis around each knot
        width = 1.0 / (self.grid_size - 1 + 1e-6)
        basis = torch.exp(-0.5 * ((x_norm.unsqueeze(-1) - knots) / width) ** 2)  # (B, D, G)
        return basis

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # B-spline path
        basis = self._b_spline_basis(x)                          # (B, D, G)
        spline_out = basis * self.spline_weights.unsqueeze(0)    # (B, D, G)
        spline_flat = spline_out.reshape(x.shape[0], -1)         # (B, D*G)
        out = self.linear(spline_flat)                           # (B, out_dim)

        # Residual base path (SiLU activation applied per input neuron)
        base_out = self.base_activation(x) @ self.base_weight   # (B, out_dim)
        return out + base_out


class _KANNet(nn.Module):
    def __init__(self, input_dim: int, hidden_layers: list,
                 grid_size: int = 5, spline_order: int = 3):
        super().__init__()
        dims = [input_dim] + hidden_layers
        self.kan_layers = nn.ModuleList([
            KANLayer(dims[i], dims[i + 1], grid_size, spline_order)
            for i in range(len(dims) - 1)
        ])
        self.head = nn.Linear(dims[-1], 1)
        self.norm_layers = nn.ModuleList([nn.LayerNorm(d) for d in dims[1:]])

    def forward(self, x):
        for kan, norm in zip(self.kan_layers, self.norm_layers):
            x = norm(torch.relu(kan(x)))
        return self.head(x).squeeze(-1)


class KANModel(BaseModel):
    """KAN (Kolmogorov-Arnold Network) Classifier."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        params = cfg["models"]["kan"]

        self.hidden_layers = params.get("hidden_layers", [64, 32])
        self.grid_size = params.get("grid_size", 5)
        self.spline_order = params.get("spline_order", 3)
        self.lr = params.get("learning_rate", 0.001)
        training_cfg = cfg.get("training", {})
        self.batch_size = training_cfg.get("batch_size", params.get("batch_size", 512))
        self.max_epochs = params.get("max_epochs", 50)
        self.patience = params.get("patience", 8)
        torch.manual_seed(params.get("random_state", 42))

        use_gpu = get_use_gpu_flag(config_path)
        self.device = get_device(use_gpu)
        self.use_amp = get_mixed_precision_flag(config_path)
        self._amp_device = "cuda" if self.device.type == "cuda" else "cpu"
        self.net = None
        self.input_dim = None

        logger.info(
            "KANModel init — device=%s | AMP=%s | batch_size=%d",
            self.device, self.use_amp, self.batch_size
        )

    def get_model_name(self) -> str:
        return "KAN"

    def train(self, X_train, y_train, X_val=None, y_val=None):
        logger.info("Training %s on %s (AMP=%s) ...", self.get_model_name(), self.device, self.use_amp)
        self.input_dim = X_train.shape[1]
        self.net = _KANNet(
            self.input_dim, self.hidden_layers,
            self.grid_size, self.spline_order
        ).to(self.device)

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
            num_workers=0,
        )

        best_val_loss = float("inf")
        wait = 0
        best_state = None

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

            # Periodic GPU cache clear
            if self.device.type == "cuda" and (epoch + 1) % 10 == 0:
                torch.cuda.empty_cache()

            if X_val is not None:
                self.net.eval()
                with torch.no_grad():
                    xv = torch.FloatTensor(X_val).to(self.device)
                    yv = torch.FloatTensor(y_val).to(self.device)
                    with autocast(device_type=self._amp_device, enabled=self.use_amp):
                        val_loss = criterion(self.net(xv), yv).item()
                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    wait = 0
                    best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
                else:
                    wait += 1
                    if wait >= self.patience:
                        logger.info("Early stopping at epoch %d", epoch + 1)
                        break

        if best_state:
            self.net.load_state_dict(best_state)

        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        logger.info("Training complete.")

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
            "grid_size": self.grid_size,
            "spline_order": self.spline_order,
        }
        joblib.dump(payload, path)
        logger.info("Model saved: %s", path)

    def load_model(self, path: str):
        payload = joblib.load(path)
        self.input_dim = payload["input_dim"]
        self.hidden_layers = payload["hidden_layers"]
        self.grid_size = payload["grid_size"]
        self.spline_order = payload["spline_order"]
        self.net = _KANNet(
            self.input_dim, self.hidden_layers,
            self.grid_size, self.spline_order
        ).to(self.device)
        self.net.load_state_dict(payload["state_dict"])
        self.net.eval()
        logger.info("Model loaded: %s", path)
