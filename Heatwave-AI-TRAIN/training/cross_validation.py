"""
training/cross_validation.py
K-Fold cross-validation helper for any BaseModel subclass.
"""
import logging
import numpy as np
from sklearn.model_selection import StratifiedKFold
from evaluation.metrics import compute_metrics

logger = logging.getLogger(__name__)


def cross_validate(model_factory, X: np.ndarray, y: np.ndarray,
                   folds: int = 5, config_path: str = "config/config.yaml") -> dict:
    """
    Perform stratified K-Fold CV on a model.

    Parameters
    ----------
    model_factory : callable that returns a fresh BaseModel instance
    X, y          : full dataset
    folds         : number of CV folds

    Returns
    -------
    dict with mean and std for each metric
    """
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    fold_metrics = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X, y), 1):
        model = model_factory(config_path)
        X_tr, X_vl = X[train_idx], X[val_idx]
        y_tr, y_vl = y[train_idx], y[val_idx]
        model.train(X_tr, y_tr)
        y_pred = model.predict(X_vl)
        y_proba = model.predict_proba(X_vl)
        m = compute_metrics(y_vl, y_pred, y_proba, f"CV-{model.get_model_name()}")
        fold_metrics.append(m)
        logger.info("Fold %d/%d — F1=%.4f", fold, folds, m["f1_score"])

    # Aggregate
    keys = ["accuracy", "precision", "recall", "f1_score", "roc_auc"]
    agg = {}
    for k in keys:
        vals = [m[k] for m in fold_metrics if m.get(k) is not None]
        if vals:
            agg[f"{k}_mean"] = round(float(np.mean(vals)), 4)
            agg[f"{k}_std"] = round(float(np.std(vals)), 4)

    logger.info("CV complete — F1 mean=%.4f ± %.4f",
                agg.get("f1_score_mean", 0), agg.get("f1_score_std", 0))
    return agg
