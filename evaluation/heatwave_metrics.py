# evaluation/heatwave_metrics.py
"""Imbalance-aware metrics for heatwave forecasting.

Accuracy is NOT the headline (it is misleading when positives are rare). The
headline metrics are PR-AUC (average precision), MCC, and F2; we also report
ROC-AUC, Brier score, and a reliability (calibration) table.
"""
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    matthews_corrcoef,
    fbeta_score,
    roc_auc_score,
    brier_score_loss,
)


def reliability_table(y_true, y_prob, n_bins=10):
    """Bin predicted probabilities and report observed frequency per bin.

    Returns a list of dicts: bin_lower, bin_upper, count, mean_pred, frac_pos.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        count = int(mask.sum())
        rows.append({
            "bin_lower": float(lo),
            "bin_upper": float(hi),
            "count": count,
            "mean_pred": float(y_prob[mask].mean()) if count else None,
            "frac_pos": float(y_true[mask].mean()) if count else None,
        })
    return rows


def skill_scores(y_true, y_pred):
    """Threshold-dependent imbalance-aware skill scores (Kala 2024, Ahmadzadeh 2021).

    Returns recall (POD), specificity, TSS (= Peirce Skill Score), HSS (Heidke),
    balanced_accuracy, g_mean. All None on single-class truth (undefined).
    """
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    pos, neg = (y_true == 1), (y_true == 0)
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    none = {k: None for k in ("recall", "specificity", "tss", "hss",
                              "balanced_accuracy", "g_mean")}
    if n_pos == 0 or n_neg == 0:
        return none
    tp = int((y_pred[pos] == 1).sum()); fn = n_pos - tp
    tn = int((y_pred[neg] == 0).sum()); fp = n_neg - tn
    recall = tp / (tp + fn)            # POD / true positive rate
    specificity = tn / (tn + fp)       # true negative rate
    denom = (tp + fn) * (fn + tn) + (tp + fp) * (fp + tn)  # Heidke denominator
    return {
        "recall": float(recall),
        "specificity": float(specificity),
        "tss": float(recall + specificity - 1),            # Peirce / True Skill Statistic
        "hss": float(2 * (tp * tn - fp * fn) / denom) if denom else None,
        "balanced_accuracy": float((recall + specificity) / 2),
        "g_mean": float(np.sqrt(recall * specificity)),
    }


def compute_metrics(y_true, y_prob, threshold=0.5):
    """Compute the headline forecasting metrics + a reliability table.

    Returns a dict with: pr_auc, mcc, f2, roc_auc, brier, threshold,
    n, n_pos, base_rate, reliability.
    Metrics undefined on single-class truth are returned as None.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)

    n = int(len(y_true))
    n_pos = int(y_true.sum())
    both_classes = 0 < n_pos < n

    pr_auc = float(average_precision_score(y_true, y_prob)) if both_classes else None
    roc_auc = float(roc_auc_score(y_true, y_prob)) if both_classes else None
    mcc = float(matthews_corrcoef(y_true, y_pred))
    f2 = float(fbeta_score(y_true, y_pred, beta=2.0, zero_division=0))
    brier = float(brier_score_loss(y_true, y_prob))

    return {
        "pr_auc": pr_auc,
        "mcc": mcc,
        "f2": f2,
        "roc_auc": roc_auc,
        "brier": brier,
        "threshold": float(threshold),
        "n": n,
        "n_pos": n_pos,
        "base_rate": float(n_pos / n) if n else None,
        **skill_scores(y_true, y_pred),
        "reliability": reliability_table(y_true, y_prob),
    }
