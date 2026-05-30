# src/calibration.py
"""Probability calibration (isotonic) + decision-threshold tuning.

The app shows probabilities and uses them to decide whether to push an alert,
so raw classifier scores must be calibrated on a held-out validation split.
The decision threshold is tuned for F2 (recall-leaning) off the PR curve, NOT
fixed at 0.5.
"""
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import precision_recall_curve


def fit_calibrator(probs, y):
    """Fit an isotonic calibrator mapping raw scores -> calibrated probabilities.

    Validation scores ``probs`` against validation labels ``y``.
    """
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=float)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(probs, y)
    return iso


def calibrate(calibrator, probs):
    """Apply a fitted calibrator to raw scores -> calibrated probabilities."""
    probs = np.asarray(probs, dtype=float)
    return calibrator.predict(probs)


def _fbeta(precision, recall, beta=2.0):
    b2 = beta * beta
    denom = b2 * precision + recall
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (1 + b2) * precision * recall / denom
    return np.nan_to_num(f, nan=0.0)


def tune_threshold(probs, y, beta=2.0):
    """Pick the probability threshold maximizing F-beta (default F2) via PR curve.

    Returns the best threshold in (0, 1].
    """
    probs = np.asarray(probs, dtype=float)
    y = np.asarray(y, dtype=int)
    if y.sum() == 0:
        # no positives: nothing to optimize, default to a high threshold
        return 1.0

    precision, recall, thresholds = precision_recall_curve(y, probs)
    # precision/recall have length n+1; thresholds has length n (drop last point)
    f = _fbeta(precision[:-1], recall[:-1], beta=beta)
    if len(f) == 0:
        return 0.5
    best = int(np.argmax(f))
    return float(thresholds[best])
