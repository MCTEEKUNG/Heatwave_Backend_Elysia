import pytest

from src.risk import prob_to_risk, RISK_LEVELS, DEFAULT_BANDS


def test_default_bands_each_region():
    # MAP colours use CONSERVATIVE public bands (calm map): red only when the
    # forecast probability is genuinely high. Authority alerts use a separate,
    # more sensitive threshold (see test_alert_tier_from_probability).
    assert prob_to_risk(0.0) == "low"
    assert prob_to_risk(0.05) == "low"
    assert prob_to_risk(0.10) == "moderate"   # lower edge inclusive
    assert prob_to_risk(0.29) == "moderate"
    assert prob_to_risk(0.30) == "high"       # orange from 0.30
    assert prob_to_risk(0.44) == "high"
    assert prob_to_risk(0.45) == "extreme"    # red only from 0.45
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


def test_alert_tier_from_probability():
    """Authority alerts (watch/warning) come from PROBABILITY at the measured
    F2-tuned operating points (0.217 / 0.281) — decoupled from the calmer map
    colours so alerts stay sensitive while the public map stays calm."""
    from src.risk import ALERT_THRESHOLDS, prob_to_alert_tier
    assert ALERT_THRESHOLDS == {"watch": 0.217, "warning": 0.281}
    assert prob_to_alert_tier(0.05) == "none"
    assert prob_to_alert_tier(0.20) == "none"
    assert prob_to_alert_tier(0.217) == "watch"
    assert prob_to_alert_tier(0.280) == "watch"
    assert prob_to_alert_tier(0.281) == "warning"
    assert prob_to_alert_tier(0.60) == "warning"


def test_map_calm_but_alert_sensitive_decoupled():
    """The whole point of the split: a p that is only 'moderate' on the map can
    still be a 'watch' for authorities."""
    from src.risk import prob_to_alert_tier
    assert prob_to_risk(0.25) == "moderate"        # calm map (yellow)
    assert prob_to_alert_tier(0.25) == "watch"     # sensitive alert
