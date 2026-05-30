import numpy as np
import pandas as pd
from src.ndvi_ingest import add_ndvi_lags

def test_add_ndvi_lags_shifts_by_month():
    df = pd.DataFrame({
        "province_id": [1, 1, 1],
        "year": [2003, 2003, 2003],
        "month": [1, 2, 3],
        "ndvi": [0.30, 0.35, 0.40],
    })
    out = add_ndvi_lags(df).sort_values("month").reset_index(drop=True)
    assert out.loc[2, "ndvi_lag1"] == 0.35
    assert out.loc[2, "ndvi_lag2"] == 0.30
