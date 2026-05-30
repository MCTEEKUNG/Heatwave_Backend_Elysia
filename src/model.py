# src/model.py
"""LightGBM binary classifier for heatwave forecasting with imbalance handling.

Heatwave-positive days are rare, so we lean on ``is_unbalance`` / ``scale_pos_weight``
rather than resampling (resampling distorts calibration -- see spec section 9).
"""
import numpy as np
import lightgbm as lgb


def train(X, y, scale_pos_weight=None, random_state=42, **kwargs):
    """Train a LightGBM classifier with class-imbalance handling.

    If ``scale_pos_weight`` is None it is derived as neg/pos; if there are no
    positives we fall back to ``is_unbalance=True``.
    """
    y = np.asarray(y)
    pos = int((y == 1).sum())
    neg = int((y == 0).sum())

    params = dict(
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=5,
        random_state=random_state,
        n_jobs=1,
        verbose=-1,
    )
    if scale_pos_weight is None and pos > 0:
        scale_pos_weight = neg / pos
    if scale_pos_weight is not None and pos > 0:
        params["scale_pos_weight"] = scale_pos_weight
    else:
        params["is_unbalance"] = True
    params.update(kwargs)

    model = lgb.LGBMClassifier(**params)
    model.fit(X, y)
    return model


def predict_proba(model, X):
    """Return P(heatwave) as a 1-D array in [0, 1]."""
    proba = model.predict_proba(X)
    return np.asarray(proba)[:, 1]


class CalibratedModel:
    """Serializable bundle: LightGBM model + isotonic calibrator + tuned threshold.

    Exposes ``predict_proba(X) -> ndarray[:, 2]`` returning CALIBRATED
    probabilities in column 1, so callers using ``predict_proba(model, X)``
    (which slices ``[:, 1]``) get calibrated P(heatwave) transparently. Defined
    in this module (not the training script) so ``joblib.load`` can resolve the
    class at inference time.
    """

    def __init__(self, model, calibrator=None, threshold=0.5,
                 feature_cols=None, model_version="lgbm-v1"):
        self.model = model
        self.calibrator = calibrator
        self.threshold = threshold
        self.feature_cols = feature_cols
        self.model_version = model_version

    def predict_proba(self, X):
        raw = np.asarray(self.model.predict_proba(X))[:, 1]
        cal = self.calibrator.predict(raw.astype(float)) if self.calibrator is not None else raw
        cal = np.clip(np.asarray(cal, dtype=float), 0.0, 1.0)
        return np.column_stack([1.0 - cal, cal])
