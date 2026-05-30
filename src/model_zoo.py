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


def make_model(name: str, scale_pos_weight: float = 1.0, **overrides):
    """Build an unfitted classifier for ``name`` (see ``SUPPORTED``).

    ``overrides`` are applied defensively: unknown parameters are silently
    skipped so that, e.g., RandomForest ignores ``learning_rate``.
    MLP is a Pipeline, so bare param names are prefixed with
    ``mlpclassifier__`` automatically; ``learning_rate`` is specially
    mapped to ``mlpclassifier__learning_rate_init`` (the float init value).
    """
    if name == "balanced_rf":
        from imblearn.ensemble import BalancedRandomForestClassifier
        est = BalancedRandomForestClassifier(
            n_estimators=200, max_depth=15, random_state=42, n_jobs=-1,
            replacement=True, sampling_strategy="auto", bootstrap=True)
    elif name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        est = RandomForestClassifier(
            n_estimators=200, max_depth=15, class_weight="balanced",
            random_state=42, n_jobs=-1)
    elif name == "xgboost":
        from xgboost import XGBClassifier
        est = XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, random_state=42, n_jobs=-1,
            eval_metric="logloss", tree_method="hist",
            scale_pos_weight=scale_pos_weight)
    elif name == "catboost":
        from catboost import CatBoostClassifier
        est = CatBoostClassifier(
            iterations=300, depth=6, learning_rate=0.1, random_seed=42,
            auto_class_weights="Balanced", verbose=0, allow_writing_files=False)
    elif name == "mlp":
        from sklearn.neural_network import MLPClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        est = make_pipeline(StandardScaler(), MLPClassifier(
            hidden_layer_sizes=(256, 128, 64), alpha=1e-4, learning_rate_init=1e-3,
            max_iter=60, early_stopping=True, n_iter_no_change=8, random_state=42))
    else:
        raise ValueError(f"unsupported model: {name!r}")

    if overrides:
        valid = est.get_params(deep=True)
        to_set = {}
        for k, v in overrides.items():
            if v is None:
                continue
            if k in valid:
                to_set[k] = v
            elif k == "learning_rate" and "mlpclassifier__learning_rate_init" in valid:
                # special-case: map the generic float 'learning_rate' to the
                # MLP init-rate param (learning_rate_init); checked BEFORE the
                # generic mlpclassifier__ prefix because MLPClassifier also has
                # a 'learning_rate' schedule-string param that we do NOT want.
                to_set["mlpclassifier__learning_rate_init"] = v
            elif f"mlpclassifier__{k}" in valid:
                to_set[f"mlpclassifier__{k}"] = v
        if to_set:
            est.set_params(**to_set)
    return est
