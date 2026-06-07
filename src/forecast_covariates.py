"""P0 forecast-covariate plumbing — leakage-safe, train/serve-consistent.

The model's measured ceiling is signal-bound: antecedent-only features can't see
the target day (oracle PR-AUC 0.33 -> 0.88). This module wires the *forecast* of
the target day in as a feature, identically at train and serve time.

- TRAIN: join a forecast store (keyed by issue_date/target_date/lead_k) onto the
  stacked forecasting frame (origin_time/target_time/horizon_k). The store always
  satisfies ``issue_date < target_date`` and we bind ``origin_time == issue_date``,
  so a covariate is only ever the forecast *issued at origin* for a *future* target
  -> leakage-safe by construction.
- SERVE: ``build_serve_covariate`` derives the same ``fc_heat_index`` from the
  Open-Meteo forecast already fetched in ``pipeline/run_forecast.py`` using the SAME
  heat-index function the store writer uses -> no train/serve skew.

``feature_columns`` (src/features.py) auto-includes any ``fc_*`` column, so once a
covariate is joined onto the frame it becomes a model feature with no extra wiring.
"""
from __future__ import annotations

import pandas as pd

from src.heat_index import heat_index_c

DEFAULT_COVARIATES = ("fc_heat_index",)


def load_forecast_store(path: str) -> pd.DataFrame:
    """Read a forecast store parquet, normalise dtypes, and assert no leakage.

    Raises ValueError if any row has ``issue_date >= target_date`` (a covariate
    that would not be knowable at origin).
    """
    df = pd.read_parquet(path)
    df["issue_date"] = pd.to_datetime(df["issue_date"])
    df["target_date"] = pd.to_datetime(df["target_date"])
    if (df["issue_date"] >= df["target_date"]).any():
        n = int((df["issue_date"] >= df["target_date"]).sum())
        raise ValueError(
            f"forecast store has {n} leaky row(s): issue_date >= target_date")
    if "lead_k" in df.columns:
        df["lead_k"] = df["lead_k"].astype(int)
    return df


def join_forecast_covariates(frame: pd.DataFrame, store: pd.DataFrame,
                             cols=DEFAULT_COVARIATES,
                             require_coverage: bool = True) -> pd.DataFrame:
    """Attach forecast covariate column(s) to a forecasting frame.

    Match on ``(province_id, origin_time == issue_date, target_time ==
    target_date, horizon_k == lead_k)``. ``require_coverage=True`` (training) does
    an inner join -> only covariate-covered rows survive (matched-rows A/B).
    ``False`` does a left join, leaving ``fc_*`` NaN where uncovered.
    """
    f = frame.copy()
    s = store.copy()
    f["_ok"] = pd.to_datetime(f["origin_time"]).dt.normalize()
    f["_tk"] = pd.to_datetime(f["target_time"]).dt.normalize()
    f["horizon_k"] = f["horizon_k"].astype(int)
    s["_ok"] = pd.to_datetime(s["issue_date"]).dt.normalize()
    s["_tk"] = pd.to_datetime(s["target_date"]).dt.normalize()
    s["horizon_k"] = s["lead_k"].astype(int)

    keep = ["province_id", "_ok", "_tk", "horizon_k", *cols]
    how = "inner" if require_coverage else "left"
    merged = f.merge(s[keep], on=["province_id", "_ok", "_tk", "horizon_k"], how=how)
    return merged.drop(columns=["_ok", "_tk"])


def build_serve_covariate(forecast_df: pd.DataFrame, province_id,
                          origin_date, horizons=range(1, 8)) -> pd.DataFrame:
    """Build serve-time forecast covariate rows from an Open-Meteo forecast frame.

    ``forecast_df`` carries ``time``, ``temperature_2m_max``,
    ``relative_humidity_2m_mean``. For each horizon k we look up the forecast for
    ``origin_date + k`` and compute ``fc_heat_index`` via the shared
    ``heat_index_c`` (identical to the store writer -> no skew). Returns rows keyed
    like a tiny store: province_id / origin_time / target_time / horizon_k.
    """
    fdf = forecast_df.copy()
    fdf["time"] = pd.to_datetime(fdf["time"]).dt.normalize()
    by_time = fdf.set_index("time")
    origin = pd.to_datetime(origin_date).normalize()

    rows = []
    for k in horizons:
        target = origin + pd.Timedelta(days=int(k))
        if target not in by_time.index:
            continue
        r = by_time.loc[target]
        tmax = float(r["temperature_2m_max"])
        rh = float(r["relative_humidity_2m_mean"])
        rows.append({
            "province_id": province_id,
            "origin_time": origin,
            "target_time": target,
            "horizon_k": int(k),
            "fc_heat_index": float(heat_index_c(tmax, rh)),
        })
    return pd.DataFrame(rows)


def forecast_store_readiness(store: pd.DataFrame, min_issue_days: int = 60) -> dict:
    """Coverage summary + a boolean gate for production retraining.

    ``ready`` is True once the store spans at least ``min_issue_days`` distinct
    issue dates (a serve-time-matched hindcast long enough to train on).
    """
    issue = pd.to_datetime(store["issue_date"])
    n_issue_days = int(issue.dt.normalize().nunique())
    span_days = int((issue.max() - issue.min()).days) if len(issue) else 0
    return {
        "n_issue_days": n_issue_days,
        "span_days": span_days,
        "min_issue_days": min_issue_days,
        "ready": n_issue_days >= min_issue_days,
    }
