import numpy as np
import pandas as pd
from src.climatology import compute_doy_percentiles


def test_percentiles_per_doy_window():
    rng = pd.date_range("1991-01-01", "2020-12-31", freq="D")
    np.random.seed(0)
    df = pd.DataFrame({"time": rng, "swbgt_max": 28 + np.random.normal(0, 2, len(rng))})
    out = compute_doy_percentiles(df, value_col="swbgt_max", window=7,
                                  baseline=(1991, 2020))
    assert {"doy", "p90", "p95", "p975"}.issubset(out.columns)
    assert len(out) == 366
    assert (out["p975"] >= out["p95"]).all()
    assert (out["p95"] >= out["p90"]).all()
