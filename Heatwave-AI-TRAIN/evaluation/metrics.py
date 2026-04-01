"""
evaluation/metrics.py
Standard evaluation metrics for binary classification.
"""
import logging
import numpy as np
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
)

logger = logging.getLogger(__name__)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                    y_proba: np.ndarray = None,
                    model_name: str = "Unknown") -> dict:
    """
    Compute classification metrics and return as a result dict.

    Parameters
    ----------
    y_true   : Ground truth labels
    y_pred   : Predicted labels
    y_proba  : Predicted positive class probabilities (optional, for ROC-AUC)
    model_name : Human-readable model name

    Returns
    -------
    dict with keys: model, accuracy, precision, recall, f1_score, roc_auc, timestamp
    """
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    roc_auc = None
    if y_proba is not None:
        try:
            roc_auc = float(roc_auc_score(y_true, y_proba))
        except Exception:
            roc_auc = None

    result = {
        "model": model_name,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    logger.info(
        "[%s] Acc=%.4f | Prec=%.4f | Rec=%.4f | F1=%.4f | ROC-AUC=%s",
        model_name, acc, prec, rec, f1, f"{roc_auc:.4f}" if roc_auc else "N/A"
    )
    return result
