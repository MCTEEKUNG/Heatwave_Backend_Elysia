import numpy as np

from evaluation.heatwave_metrics import compute_metrics, reliability_table


def test_compute_metrics_keys_and_ranges():
    rng = np.random.default_rng(0)
    y = (rng.uniform(size=400) < 0.2).astype(int)
    probs = np.where(y == 1, rng.uniform(0.4, 1.0, 400),
                     rng.uniform(0.0, 0.6, 400))
    m = compute_metrics(y, probs, threshold=0.5)
    for key in ("pr_auc", "mcc", "f2", "roc_auc", "brier", "reliability",
                "base_rate", "n", "n_pos"):
        assert key in m
    assert 0.0 <= m["pr_auc"] <= 1.0
    assert 0.0 <= m["roc_auc"] <= 1.0
    assert -1.0 <= m["mcc"] <= 1.0
    assert 0.0 <= m["f2"] <= 1.0
    assert 0.0 <= m["brier"] <= 1.0


def test_perfect_prediction_scores_high():
    y = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    probs = np.array([0.01, 0.02, 0.99, 0.98, 0.03, 0.97, 0.04, 0.96])
    m = compute_metrics(y, probs, threshold=0.5)
    assert m["pr_auc"] > 0.99
    assert m["roc_auc"] > 0.99
    assert m["mcc"] > 0.99
    assert m["f2"] > 0.99
    assert m["brier"] < 0.01


def test_single_class_truth_returns_none_for_auc():
    y = np.zeros(10, dtype=int)
    probs = np.linspace(0, 1, 10)
    m = compute_metrics(y, probs, threshold=0.5)
    assert m["pr_auc"] is None
    assert m["roc_auc"] is None
    # mcc/f2/brier still computable
    assert m["mcc"] is not None
    assert m["brier"] is not None


def test_reliability_table_bins_and_counts():
    y = np.array([0, 1, 0, 1, 1])
    probs = np.array([0.05, 0.95, 0.15, 0.85, 0.92])
    table = reliability_table(y, probs, n_bins=10)
    assert len(table) == 10
    assert sum(row["count"] for row in table) == len(y)
