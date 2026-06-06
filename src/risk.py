# src/risk.py
"""Map a calibrated heatwave probability to a discrete risk level.

SINGLE SOURCE OF TRUTH for severity policy. The frontend
(``HeatMAP-Frontend/services/forecastService.ts``) mirrors these bands and the
alert-tier thresholds — change them HERE first, then sync the frontend.

The four levels match the DB CHECK constraint on ``heatwave.forecasts.risk_level``:
``'low' | 'moderate' | 'high' | 'extreme'``.

Default probability bands (policy thresholds; the upper two are the MEASURED
two-tier operating points selected on the 2025 test year — see
docs/SESSION-REPORT.html §7):
    p < 0.10            -> 'low'       (quiet)
    0.10 <= p < 0.217   -> 'moderate'  (elevated, below watch)
    0.217 <= p < 0.281  -> 'high'      == WATCH  (precision 0.28 / recall 0.64)
    p >= 0.281          -> 'extreme'   == WARNING (precision 0.35 / recall 0.46)

Nesting the alert tiers inside the 4-tier bands keeps every surface consistent:
the map's colour (risk_level), the alerts roll-up (watch/warning), and
predicted_label's tuned threshold all derive from the same operating points.
The tier mapping is exactly: extreme -> 'warning', high -> 'watch', else 'none'.

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

# Default upper edges (exclusive) for low / moderate / high; >= the last edge -> extreme.
# The upper two edges ARE the alert thresholds (see module docstring).
DEFAULT_BANDS = (0.10, ALERT_THRESHOLDS["watch"], ALERT_THRESHOLDS["warning"])


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


def risk_to_alert_tier(risk_level: str) -> str:
    """Map a 4-tier ``risk_level`` to the public two-tier alert vocabulary.

    With ``DEFAULT_BANDS`` this is exact (the bands nest the alert thresholds):
    ``extreme -> 'warning'``, ``high -> 'watch'``, else ``'none'``.
    """
    if risk_level == "extreme":
        return "warning"
    if risk_level == "high":
        return "watch"
    return "none"
