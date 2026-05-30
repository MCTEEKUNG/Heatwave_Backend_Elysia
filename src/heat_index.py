"""Relative humidity (August-Roche-Magnus) and Rothfusz heat index, vectorized.

Matches the source backend's physics so labels are comparable. All temps in degC,
RH in percent. heat_index_c returns the NWS Rothfusz heat index in degC.
"""
import numpy as np


def rh_from_dewpoint(t2m_c, d2m_c):
    """Relative humidity (%) from air temp and dewpoint (Magnus)."""
    t = np.asarray(t2m_c, dtype=float)
    td = np.asarray(d2m_c, dtype=float)
    a, b = 17.625, 243.04
    rh = 100.0 * np.exp((a * td) / (b + td)) / np.exp((a * t) / (b + t))
    return np.clip(rh, 0.0, 100.0)


def heat_index_c(t2m_c, rh_pct):
    """NWS Rothfusz heat index (degC). Computed in degF then converted back."""
    t = np.asarray(t2m_c, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    tf = t * 9.0 / 5.0 + 32.0
    hi = (-42.379 + 2.04901523 * tf + 10.14333127 * rh
          - 0.22475541 * tf * rh - 6.83783e-3 * tf**2
          - 5.481717e-2 * rh**2 + 1.22874e-3 * tf**2 * rh
          + 8.5282e-4 * tf * rh**2 - 1.99e-6 * tf**2 * rh**2)
    # low-HI regime: simple average form is more accurate
    simple = 0.5 * (tf + 61.0 + (tf - 68.0) * 1.2 + rh * 0.094)
    hi = np.where(tf < 80.0, simple, hi)
    return (hi - 32.0) * 5.0 / 9.0
