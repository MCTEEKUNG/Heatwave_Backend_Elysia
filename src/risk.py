# src/risk.py
"""Map a calibrated heatwave probability to a discrete risk level.

The four levels match the DB CHECK constraint on ``heatwave.forecasts.risk_level``:
``'low' | 'moderate' | 'high' | 'extreme'``.

Default probability bands (tunable -- these are policy thresholds, not learned):
    p < 0.10            -> 'low'
    0.10 <= p < 0.30    -> 'moderate'
    0.30 <= p < 0.60    -> 'high'
    p >= 0.60           -> 'extreme'

Bands are inclusive on the lower edge / exclusive on the upper edge so the
mapping is monotonic and every p in [0, 1] resolves to exactly one level.
"""

# Ordered low -> high so callers can compare severity if needed.
RISK_LEVELS = ("low", "moderate", "high", "extreme")

# Default upper edges (exclusive) for low / moderate / high; >= the last edge -> extreme.
DEFAULT_BANDS = (0.10, 0.30, 0.60)


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
