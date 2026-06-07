"""Imbalance-aware skill scores recommended by the rare-event literature
(Peirce/True Skill Statistic, Heidke Skill Score, balanced accuracy, G-mean;
Kala 2024, Ahmadzadeh 2021). Threshold-dependent; undefined on single-class truth.
"""
import numpy as np
import pytest

from evaluation.heatwave_metrics import skill_scores, compute_metrics


def test_skill_scores_known_confusion_matrix():
    # TP=2, FN=1, TN=2, FP=1 -> recall=spec=2/3
    y_true = [1, 1, 0, 0, 1, 0]
    y_pred = [1, 0, 0, 1, 1, 0]
    s = skill_scores(y_true, y_pred)
    assert s["recall"] == pytest.approx(2 / 3)
    assert s["specificity"] == pytest.approx(2 / 3)
    assert s["tss"] == pytest.approx(1 / 3)          # recall + spec - 1
    assert s["balanced_accuracy"] == pytest.approx(2 / 3)
    assert s["g_mean"] == pytest.approx(2 / 3)
    assert s["hss"] == pytest.approx(1 / 3)


def test_skill_scores_perfect():
    s = skill_scores([1, 0, 1, 0], [1, 0, 1, 0])
    assert s["tss"] == pytest.approx(1.0)
    assert s["hss"] == pytest.approx(1.0)
    assert s["balanced_accuracy"] == pytest.approx(1.0)
    assert s["g_mean"] == pytest.approx(1.0)


def test_skill_scores_single_class_returns_none():
    s = skill_scores([0, 0, 0], [0, 1, 0])  # no positives in truth
    assert s["tss"] is None
    assert s["hss"] is None
    assert s["balanced_accuracy"] is None
    assert s["g_mean"] is None


def test_compute_metrics_includes_skill_scores():
    y_true = [0, 1, 0, 1, 0, 0, 1, 0]
    y_prob = [0.1, 0.8, 0.2, 0.6, 0.3, 0.05, 0.9, 0.4]
    m = compute_metrics(y_true, y_prob, threshold=0.5)
    for k in ("tss", "hss", "balanced_accuracy", "g_mean"):
        assert k in m
        assert m[k] is not None
