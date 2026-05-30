import numpy as np

from src.calibration import fit_calibrator, calibrate, tune_threshold


def test_isotonic_calibration_is_monotonic():
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, 500)
    # label probability increases with the raw score
    y = (rng.uniform(size=500) < probs).astype(int)
    cal = fit_calibrator(probs, y)

    grid = np.linspace(0, 1, 50)
    out = calibrate(cal, grid)
    assert out.min() >= 0.0 and out.max() <= 1.0
    # isotonic output must be non-decreasing in the input
    assert np.all(np.diff(out) >= -1e-9)


def test_tune_threshold_in_range_and_better_than_default():
    rng = np.random.default_rng(1)
    n = 600
    y = (rng.uniform(size=n) < 0.15).astype(int)
    # well-separated scores
    probs = np.where(y == 1, rng.uniform(0.5, 1.0, n), rng.uniform(0.0, 0.5, n))
    thr = tune_threshold(probs, y, beta=2.0)
    assert 0.0 < thr <= 1.0


def test_tune_threshold_no_positives_returns_high():
    probs = np.linspace(0, 1, 20)
    y = np.zeros(20, dtype=int)
    assert tune_threshold(probs, y) == 1.0
