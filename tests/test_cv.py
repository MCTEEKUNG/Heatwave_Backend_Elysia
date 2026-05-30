import pytest
from evaluation.cv import rolling_origin_folds


def test_folds_are_causal():
    folds = rolling_origin_folds(first_test=2023, last_test=2025)
    assert folds == [(2022, 2023), (2023, 2024), (2024, 2025)]
    for train_max, test_yr in folds:
        assert train_max < test_yr


def test_single_fold():
    assert rolling_origin_folds(2025, 2025) == [(2024, 2025)]


def test_bad_range_raises():
    with pytest.raises(ValueError):
        rolling_origin_folds(2025, 2024)
