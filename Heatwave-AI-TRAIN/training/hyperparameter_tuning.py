"""
training/hyperparameter_tuning.py
Grid search / random search helper for any scikit-learn compatible model.
"""
import logging
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV

logger = logging.getLogger(__name__)


def tune_grid(estimator, param_grid: dict, X_train, y_train,
              scoring: str = "f1", cv: int = 3, n_jobs: int = -1) -> dict:
    """
    Run GridSearchCV and return best params + best score.

    Parameters
    ----------
    estimator  : sklearn-compatible estimator (e.g. XGBClassifier())
    param_grid : dict of parameter grids
    X_train    : training features
    y_train    : training labels
    scoring    : metric to optimise (default: f1)
    cv         : number of CV folds

    Returns
    -------
    dict with 'best_params' and 'best_score'
    """
    logger.info("Starting GridSearchCV with %d param combos ...", _count_grid(param_grid))
    gs = GridSearchCV(estimator, param_grid, scoring=scoring,
                      cv=cv, n_jobs=n_jobs, verbose=1)
    gs.fit(X_train, y_train)
    logger.info("Best params: %s | Best %s: %.4f", gs.best_params_, scoring, gs.best_score_)
    return {"best_params": gs.best_params_, "best_score": gs.best_score_}


def tune_random(estimator, param_dist: dict, X_train, y_train,
                n_iter: int = 30, scoring: str = "f1",
                cv: int = 3, n_jobs: int = -1, random_state: int = 42) -> dict:
    """
    Run RandomizedSearchCV for faster tuning of large parameter spaces.

    Returns
    -------
    dict with 'best_params' and 'best_score'
    """
    logger.info("Starting RandomizedSearchCV (%d iterations) ...", n_iter)
    rs = RandomizedSearchCV(estimator, param_dist, n_iter=n_iter,
                            scoring=scoring, cv=cv, n_jobs=n_jobs,
                            random_state=random_state, verbose=1)
    rs.fit(X_train, y_train)
    logger.info("Best params: %s | Best %s: %.4f", rs.best_params_, scoring, rs.best_score_)
    return {"best_params": rs.best_params_, "best_score": rs.best_score_}


def _count_grid(param_grid: dict) -> int:
    from math import prod
    return prod(len(v) for v in param_grid.values())
