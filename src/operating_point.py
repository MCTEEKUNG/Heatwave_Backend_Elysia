# src/operating_point.py
"""Operating-point selection helpers for calibrated probability scores.

Pure numpy/pandas math — no I/O, no model training.
All threshold comparisons use ``>=`` (predict_positive = probs >= threshold).
Candidate thresholds are swept from ``np.unique(probs)``.

Functions
---------
precision_leaning_threshold  — lowest threshold achieving a precision floor
two_tier_thresholds          — watch (high-recall) + warning (high-precision) pair
per_horizon_thresholds       — per-lead-time threshold optimised for recall
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "precision_leaning_threshold",
    "two_tier_thresholds",
    "per_horizon_thresholds",
]

_DEFAULT_THR = 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prepare(probs, y):
    """Convert array-likes to numpy float / int arrays.  Returns (probs, y)."""
    probs = np.asarray(probs, dtype=float).ravel()
    y = np.asarray(y, dtype=int).ravel()
    return probs, y


def _precision_recall_at(probs: np.ndarray, y: np.ndarray, thr: float):
    """Return (precision, recall) for threshold *thr* using ``>=`` convention."""
    preds = probs >= thr
    tp = int(np.sum(preds & (y == 1)))
    fp = int(np.sum(preds & (y == 0)))
    fn = int(np.sum(~preds & (y == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def _largest_thr_for_recall(
    probs: np.ndarray, y: np.ndarray, min_recall: float
) -> float:
    """Return the LARGEST unique-prob threshold that achieves recall >= min_recall.

    Sweeps candidates from ``np.unique(probs)`` (ascending) and keeps track of
    the highest one that still meets the recall floor.  Returns ``_DEFAULT_THR``
    when no positives exist in *y*.
    """
    if len(probs) == 0 or y.sum() == 0:
        return _DEFAULT_THR

    candidates = np.unique(probs)  # ascending
    best: float | None = None
    for thr in candidates:
        _, rec = _precision_recall_at(probs, y, thr)
        if rec >= min_recall - 1e-12:
            best = float(thr)
    # 'best' is the largest qualifying because we iterate ascending and keep overwriting
    return best if best is not None else _DEFAULT_THR


def _lowest_thr_for_precision(
    probs: np.ndarray, y: np.ndarray, min_precision: float
) -> float:
    """Return the LOWEST unique-prob threshold that achieves precision >= min_precision.

    If no threshold qualifies, return the threshold with the maximum precision.
    Returns ``_DEFAULT_THR`` when no positives exist.
    """
    if len(probs) == 0 or y.sum() == 0:
        return _DEFAULT_THR

    candidates = np.unique(probs)  # ascending
    best_thr: float | None = None
    max_prec: float = -1.0
    max_prec_thr: float = float(candidates[-1])

    for thr in candidates:
        prec, _ = _precision_recall_at(probs, y, thr)
        # Track global max-precision threshold (for the fallback)
        if prec > max_prec:
            max_prec = prec
            max_prec_thr = float(thr)
        # First qualifying (lowest, because we go ascending) — stop early
        if best_thr is None and prec >= min_precision - 1e-12:
            best_thr = float(thr)

    return best_thr if best_thr is not None else max_prec_thr


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def precision_leaning_threshold(
    probs,
    y,
    min_precision: float = 0.5,
) -> float:
    """Return the lowest threshold whose precision on (probs, y) is >= min_precision.

    This maximises recall subject to the precision floor, giving the product
    team a lever to reduce false-alarm rate without over-sacrificing coverage.

    If no threshold reaches ``min_precision``, return the threshold with the
    maximum achievable precision.  Edge cases (empty input, all-negative *y*)
    return 0.5.

    Parameters
    ----------
    probs : array-like of float
        Calibrated probabilities, shape (n,).
    y : array-like of int
        Binary true labels, shape (n,).
    min_precision : float
        Precision floor (default 0.5).

    Returns
    -------
    float
        Selected decision threshold.
    """
    probs, y = _prepare(probs, y)
    return _lowest_thr_for_precision(probs, y, min_precision)


def two_tier_thresholds(
    probs,
    y,
    watch_recall: float = 0.90,
    warning_min_precision: float = 0.50,
) -> dict:
    """Return a two-tier operating-point dictionary.

    ``watch``   — high-sensitivity early alert: largest threshold achieving
                  recall >= *watch_recall*.
    ``warning`` — high-confidence alert: ``precision_leaning_threshold`` with
                  *warning_min_precision*.

    The guarantee ``watch <= warning`` is enforced by clamping.

    Parameters
    ----------
    probs, y : array-likes
        Calibrated probabilities and binary labels.
    watch_recall : float
        Minimum recall for the *watch* tier (default 0.90).
    warning_min_precision : float
        Minimum precision for the *warning* tier (default 0.50).

    Returns
    -------
    dict with keys ``"watch"`` and ``"warning"``.
    """
    probs, y = _prepare(probs, y)

    if len(probs) == 0 or y.sum() == 0:
        return {"watch": _DEFAULT_THR, "warning": _DEFAULT_THR}

    watch = _largest_thr_for_recall(probs, y, watch_recall)
    warning = _lowest_thr_for_precision(probs, y, warning_min_precision)

    # Guarantee: watch <= warning
    watch = min(watch, warning)

    return {"watch": float(watch), "warning": float(warning)}


def per_horizon_thresholds(
    df: pd.DataFrame,
    prob_col: str = "prob",
    y_col: str = "y",
    horizon_col: str = "horizon_k",
    target_recall: float = 0.80,
) -> dict:
    """Return a per-horizon threshold dict optimised for recall.

    For each horizon value, find the largest threshold achieving recall >=
    *target_recall* on that horizon's rows.  Lead time decays forecast skill,
    so one global threshold is suboptimal — near horizons can afford a higher
    (stricter) threshold while far horizons need a lower one.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns *prob_col*, *y_col*, *horizon_col*.
    prob_col, y_col, horizon_col : str
        Column names (defaults match standard pipeline output).
    target_recall : float
        Minimum recall per horizon (default 0.80).

    Returns
    -------
    dict
        ``{horizon_value (int): threshold (float)}``.
    """
    result: dict = {}
    for horizon, group in df.groupby(horizon_col, sort=True):
        probs_h = np.asarray(group[prob_col].values, dtype=float)
        y_h = np.asarray(group[y_col].values, dtype=int)
        thr = _largest_thr_for_recall(probs_h, y_h, target_recall)
        result[int(horizon)] = float(thr)
    return result
