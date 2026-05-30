# src/model_zoo.py
"""Single source of truth for the non-LightGBM model families.

`make_model(name, scale_pos_weight)` returns an UNFITTED estimator exposing
`predict_proba`. Centralized so the bake-off (`scripts/bakeoff.py`) and the
dashboard trainers (`training-dashboard/server/trainers/sklearn_models.py`)
cannot drift on hyperparameters. LightGBM is intentionally NOT here -- it has
its own production training in `src.model.train`.

Imports are lazy (inside `make_model`) so importing this module is cheap and
does not require xgboost/catboost/etc. unless a model is actually built.
"""
from __future__ import annotations

SUPPORTED = ("balanced_rf", "random_forest", "xgboost", "catboost", "mlp")


def make_model(name: str, scale_pos_weight: float = 1.0):
    """Build an unfitted classifier for ``name`` (see ``SUPPORTED``)."""
    if name == "balanced_rf":
        from imblearn.ensemble import BalancedRandomForestClassifier
        return BalancedRandomForestClassifier(
            n_estimators=200, max_depth=15, random_state=42, n_jobs=-1,
            replacement=True, sampling_strategy="auto", bootstrap=True)
    if name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=200, max_depth=15, class_weight="balanced",
            random_state=42, n_jobs=-1)
    if name == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, random_state=42, n_jobs=-1,
            eval_metric="logloss", tree_method="hist",
            scale_pos_weight=scale_pos_weight)
    if name == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(
            iterations=300, depth=6, learning_rate=0.1, random_seed=42,
            auto_class_weights="Balanced", verbose=0, allow_writing_files=False)
    if name == "mlp":
        from sklearn.neural_network import MLPClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), MLPClassifier(
            hidden_layer_sizes=(256, 128, 64), alpha=1e-4, learning_rate_init=1e-3,
            max_iter=60, early_stopping=True, n_iter_no_change=8, random_state=42))
    raise ValueError(f"unsupported model: {name!r}")
