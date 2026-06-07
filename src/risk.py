# src/risk.py
"""Map a calibrated heatwave probability to a discrete risk level.

SINGLE SOURCE OF TRUTH for severity policy. The frontend
(``HeatMAP-Frontend/services/forecastService.ts``) mirrors these bands and the
alert-tier thresholds — change them HERE first, then sync the frontend.

The four levels match the DB CHECK constraint on ``heatwave.forecasts.risk_level``:
``'low' | 'moderate' | 'high' | 'extreme'``.

TWO DECOUPLED policies (public map calm, authority alerts sensitive):

MAP colour bands (``prob_to_risk`` / ``DEFAULT_BANDS``) — public-facing, calm:
    p < 0.10           -> 'low'      (green)
    0.10 <= p < 0.30   -> 'moderate' (yellow)
    0.30 <= p < 0.45   -> 'high'     (orange)
    p >= 0.45          -> 'extreme'  (red — only when genuinely high)

ALERT tiers (``prob_to_alert_tier`` / ``ALERT_THRESHOLDS``) — for LINE / the
alerts roll-up; the MEASURED F2-tuned operating points (2025 test year):
    p >= 0.217  -> 'watch'    (precision 0.28 / recall 0.64)
    p >= 0.281  -> 'warning'  (precision 0.35 / recall 0.46)

They are intentionally SEPARATE: a p of 0.25 is only 'moderate' (yellow) on the
public map but already a 'watch' for authorities. Map colour comes from
``risk_level``; alert tier comes from the probability. The frontend mirrors both
(forecastService RISK_BANDS = map; ALERT_THRESHOLDS / getAlertTier = alerts).

NOTE: these thresholds were tuned for model_version 'lgbm-v1' calibrated
probabilities. Re-measure when the model is retrained (ALERT_TUNED_FOR_VERSION
documents the pairing).

Bands are inclusive on the lower edge / exclusive on the upper edge so the
mapping is monotonic and every p in [0, 1] resolves to exactly one level.
"""

# Ordered low -> high so callers can compare severity if needed.
RISK_LEVELS = ("low", "moderate", "high", "extreme")

# Measured two-tier operating points (2025 test year, lgbm-v1).
ALERT_THRESHOLDS = {"watch": 0.217, "warning": 0.281}
ALERT_TUNED_FOR_VERSION = "lgbm-v1"

# MAP colour bands (public-facing, CONSERVATIVE so the map stays calm): upper
# edges (exclusive) for low / moderate / high; >= the last edge -> extreme.
# DECOUPLED from ALERT_THRESHOLDS on purpose — authority alerts (prob_to_alert_tier)
# fire earlier (0.217/0.281) so they stay sensitive, while the public map only
# turns orange at 0.30 and red at 0.45 (genuinely high). See module docstring.
DEFAULT_BANDS = (0.10, 0.30, 0.45)


def prob_to_risk(p: float, bands=DEFAULT_BANDS) -> str:
    """Return one of ``RISK_LEVELS`` for probability ``p`` in [0, 1].

    ``bands`` is a 3-tuple of ascending exclusive upper edges
    ``(low_max, moderate_max, high_max)``. Raises ``ValueError`` if ``p`` is
    outside [0, 1] or ``bands`` is not strictly ascending.
    """
    if p is None or not (0.0 <= float(p) <= 1.0):
        raise ValueError(f"probability must be in [0, 1], got {p!r}")
    low_max, moderate_max, high_max = bands
    if not (low_max < moderate_max < high_max):
        raise ValueError(f"bands must be strictly ascending, got {bands!r}")

    p = float(p)
    if p < low_max:
        return "low"
    if p < moderate_max:
        return "moderate"
    if p < high_max:
        return "high"
    return "extreme"


def prob_to_alert_tier(p: float) -> str:
    """Authority two-tier alert from a calibrated probability, at the MEASURED
    F2-tuned operating points (``ALERT_THRESHOLDS``): ``>= 0.281 -> 'warning'``,
    ``>= 0.217 -> 'watch'``, else ``'none'``.

    Computed from probability (NOT the map ``risk_level``) so alerts stay
    sensitive even though the public map colours are deliberately calmer.
    """
    if p is None or not (0.0 <= float(p) <= 1.0):
        raise ValueError(f"probability must be in [0, 1], got {p!r}")
    p = float(p)
    if p >= ALERT_THRESHOLDS["warning"]:
        return "warning"
    if p >= ALERT_THRESHOLDS["watch"]:
        return "watch"
    return "none"
