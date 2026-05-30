import pytest

from src.risk import prob_to_risk, RISK_LEVELS, DEFAULT_BANDS


def test_default_bands_each_region():
    assert prob_to_risk(0.0) == "low"
    assert prob_to_risk(0.05) == "low"
    assert prob_to_risk(0.10) == "moderate"   # lower edge inclusive
    assert prob_to_risk(0.29) == "moderate"
    assert prob_to_risk(0.30) == "high"
    assert prob_to_risk(0.59) == "high"
    assert prob_to_risk(0.60) == "extreme"
    assert prob_to_risk(1.0) == "extreme"


def test_output_always_valid_level():
    for p in [i / 100 for i in range(0, 101)]:
        assert prob_to_risk(p) in RISK_LEVELS
        assert prob_to_risk(p) in ("low", "moderate", "high", "extreme")


def test_monotonic_non_decreasing_severity():
    order = {lvl: i for i, lvl in enumerate(RISK_LEVELS)}
    prev = -1
    for p in [i / 200 for i in range(0, 201)]:
        cur = order[prob_to_risk(p)]
        assert cur >= prev
        prev = cur


def test_out_of_range_raises():
    with pytest.raises(ValueError):
        prob_to_risk(-0.01)
    with pytest.raises(ValueError):
        prob_to_risk(1.01)
    with pytest.raises(ValueError):
        prob_to_risk(None)


def test_custom_bands():
    bands = (0.2, 0.5, 0.8)
    assert prob_to_risk(0.1, bands=bands) == "low"
    assert prob_to_risk(0.2, bands=bands) == "moderate"
    assert prob_to_risk(0.5, bands=bands) == "high"
    assert prob_to_risk(0.8, bands=bands) == "extreme"


def test_bad_bands_raise():
    with pytest.raises(ValueError):
        prob_to_risk(0.5, bands=(0.5, 0.3, 0.9))  # not ascending


def test_default_bands_constant_shape():
    assert len(DEFAULT_BANDS) == 3
    assert list(DEFAULT_BANDS) == sorted(DEFAULT_BANDS)
