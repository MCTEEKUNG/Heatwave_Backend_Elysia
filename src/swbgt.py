# src/swbgt.py
"""Simplified shade WBGT (Australian BoM).

NOT full ISO 7243 WBGT — there is no globe-temperature (solar) term here.
Used consistently for both training labels and inference so the metric is comparable.

    e     = (RH/100) * 6.105 * exp(17.27*Ta / (237.7 + Ta))   # vapor pressure (hPa)
    sWBGT = 0.567*Ta + 0.393*e + 3.94                          # deg C
"""
import numpy as np


def vapor_pressure_hpa(ta_c, rh_pct):
    """Water vapor pressure (hPa) from air temp (deg C) and RH (%)."""
    ta = np.asarray(ta_c, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    return (rh / 100.0) * 6.105 * np.exp(17.27 * ta / (237.7 + ta))


def swbgt(ta_c, rh_pct):
    """Simplified shade WBGT (deg C). Accepts scalars or arrays."""
    ta = np.asarray(ta_c, dtype=float)
    e = vapor_pressure_hpa(ta, rh_pct)
    return 0.567 * ta + 0.393 * e + 3.94
