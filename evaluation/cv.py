# evaluation/cv.py
"""Rolling-origin (causal) time-series cross-validation folds.

Each fold trains on every year < test_year and evaluates on test_year, so no
future information leaks into training -- the correct CV for forecasting.
"""


def rolling_origin_folds(first_test: int, last_test: int) -> list:
    """Return [(train_max_year, test_year), ...] for test years first_test..last_test.

    train_max_year is test_year - 1; callers train on year <= train_max_year.
    """
    if first_test > last_test:
        raise ValueError("first_test must be <= last_test")
    return [(year - 1, year) for year in range(first_test, last_test + 1)]
