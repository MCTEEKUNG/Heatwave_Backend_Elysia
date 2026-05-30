import numpy as np
import pandas as pd

from src.model import train, predict_proba


def _xy(n=300, seed=0):
    """Synthetic imbalanced binary problem with signal."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({
        "f1": rng.normal(0, 1, n),
        "f2": rng.normal(0, 1, n),
        "horizon_k": rng.integers(1, 8, n),
    })
    # rare positive driven by f1
    logit = -2.5 + 1.8 * X["f1"]
    p = 1 / (1 + np.exp(-logit))
    y = (rng.uniform(size=n) < p).astype(int)
    return X, y.values


def test_train_and_predict_proba_shape_and_range():
    X, y = _xy()
    assert 0 < y.sum() < len(y)  # both classes present
    model = train(X, y, random_state=0)
    proba = predict_proba(model, X)
    assert proba.shape == (len(X),)
    assert proba.min() >= 0.0 and proba.max() <= 1.0


def test_imbalance_handled_no_crash_with_few_positives():
    X, y = _xy(seed=1)
    model = train(X, y)
    proba = predict_proba(model, X)
    # model should give higher mean prob to true positives than true negatives
    assert proba[y == 1].mean() > proba[y == 0].mean()


def test_all_negative_falls_back_to_is_unbalance():
    rng = np.random.default_rng(2)
    X = pd.DataFrame({"f1": rng.normal(0, 1, 50), "horizon_k": 1})
    y = np.zeros(50, dtype=int)
    model = train(X, y)  # must not raise even with zero positives
    proba = predict_proba(model, X)
    assert proba.shape == (50,)
    assert proba.min() >= 0.0 and proba.max() <= 1.0
