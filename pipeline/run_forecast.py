# pipeline/run_forecast.py
"""Daily forecast-generation job: trained model -> heatwave.forecasts rows.

For each province we assemble a single per-province daily frame from recent
Open-Meteo *history* plus the *forecast* tail, build the backward-only
forecasting features via ``src.features.make_forecasting_frame``, keep only the
rows whose origin day is the generated date, score horizons k=1..7 with the
trained model, map P(heatwave) -> risk_level, and emit one dict row per
(province, horizon).

Why the forecast tail is needed even though features are backward-only:
``make_forecasting_frame`` sets ``y = heatwave.shift(-k)`` and drops rows with a
NaN target. For origin == today, ``heatwave(today+k)`` would be NaN and the row
would be dropped. We pad the frame with future-dated rows (today+1..today+7) so
that ``shift(-k)`` resolves; ``y`` is a throwaway training artifact at inference
(``_antecedent_features`` never reads ``heatwave``). The forecast pull also
supplies ``swbgt_pred`` for each target_date (model predicts probability, not
sWBGT).

``build_forecast_rows`` is pure (no network, no DB): pass in a provinces frame,
a model object exposing ``predict_proba``, and a per-province frame builder. The
network/DB wiring lives only in ``main()``.
"""
from datetime import date, datetime, timezone

import pandas as pd

from src import features as features_mod
from src import openmeteo_client
from src.model import predict_proba
from src.risk import prob_to_risk
from src.swbgt import swbgt

MODEL_PATH = "models/heatwave_model.pkl"
DEFAULT_MODEL_VERSION = "lgbm-v1"
LABEL_THRESHOLD = 0.5  # tunable: default decision threshold for predicted_label


def _province_daily_frame(province, history_df, forecast_df):
    """Combine history + forecast into one per-province daily frame.

    Computes ``swbgt_max`` from weather, dedupes on ``time`` (history+forecast
    overlap on 'today'), and attaches static province columns plus a placeholder
    ``heatwave`` column so the latest origin day survives the feature builder's
    dropna. The ``p95`` column, if present on the inputs, is carried through.
    """
    frames = [df for df in (history_df, forecast_df) if df is not None and len(df)]
    combined = pd.concat(frames, ignore_index=True)
    combined["time"] = pd.to_datetime(combined["time"])
    # forecast wins on overlap (keep='last' after stable sort puts forecast after history)
    combined = combined.sort_values("time").drop_duplicates(
        subset="time", keep="last").reset_index(drop=True)

    combined["swbgt_max"] = swbgt(
        combined["temperature_2m_max"], combined["relative_humidity_2m_mean"])

    combined["province_id"] = province["id"]
    for col in ("lat", "lon"):
        if col in province:
            combined[col] = province[col]

    # placeholder so heatwave.shift(-k) is non-NaN at the latest origin day.
    if "heatwave" not in combined.columns:
        combined["heatwave"] = 0
    return combined


def build_forecast_rows(provinces, model, generated_at,
                        history_days=40, horizons=range(1, 8),
                        frame_builder=None, model_version=DEFAULT_MODEL_VERSION,
                        label_threshold=LABEL_THRESHOLD, origin_date=None):
    """Return a list of forecast row dicts. Pure: no network, no DB.

    Parameters
    ----------
    provinces : DataFrame with at least ``id`` (and ideally ``lat``/``lon``).
    model : object exposing ``predict_proba`` compatible with ``src.model``.
    generated_at : ``datetime`` stamp written to the ``generated_at`` column.
    origin_date : the origin day used to select forecast rows; ``target_date =
        origin_date + k``. If None, defaults to ``generated_at.date()``. Pass
        this explicitly when ``generated_at`` is in a different timezone than the
        weather data (e.g. UTC stamp but Bangkok-local frame dates), otherwise
        the origin filter can match nothing.
    frame_builder : callable ``(province_row) -> per-province daily DataFrame``
        ending at the forecast tail (origin + max horizon). Injected so tests can
        supply synthetic data with no network. ``main`` wires the real fetch.
    """
    horizons = list(horizons)
    if origin_date is None:
        origin_date = generated_at.date() if isinstance(generated_at, datetime) \
            else generated_at
    generated_date = origin_date
    generated_ts = pd.Timestamp(generated_date)

    if frame_builder is None:
        raise ValueError("frame_builder is required (inject fetch + assembly)")

    rows = []
    for _, province in provinces.iterrows():
        daily = frame_builder(province)
        daily = daily.copy()
        daily["time"] = pd.to_datetime(daily["time"])

        # map target_date -> sWBGT computed from that day's (forecast) weather
        swbgt_by_time = dict(zip(daily["time"], daily["swbgt_max"]))

        frame = features_mod.make_forecasting_frame(daily, horizons=horizons)
        # keep only rows whose ORIGIN is the generated date -> one row per horizon
        today_rows = frame[frame["origin_time"] == generated_ts]
        if today_rows.empty:
            # Loud, not silent: an empty origin means generated_date is not in
            # the assembled frame (timezone misalignment) or history/forecast is
            # too short to build features. Surfacing it prevents a "success"
            # print that secretly upserted nothing.
            import warnings
            warnings.warn(
                f"province {province['id']}: no rows at origin {generated_date} "
                f"(frame spans {daily['time'].min().date()}..{daily['time'].max().date()}); "
                "check timezone alignment and history length",
                RuntimeWarning, stacklevel=2)
            continue
        today_rows = today_rows.sort_values("horizon_k").reset_index(drop=True)

        feat_cols = features_mod.feature_columns(frame)
        probs = predict_proba(model, today_rows[feat_cols])

        for i, (_, fr) in enumerate(today_rows.iterrows()):
            k = int(fr["horizon_k"])
            target_time = pd.Timestamp(fr["target_time"])
            prob = float(probs[i])
            sw = swbgt_by_time.get(target_time)
            rows.append({
                "province_id": int(province["id"]),
                "target_date": target_time.date(),
                "generated_at": generated_at,
                "horizon_days": k,
                "probability": prob,
                "predicted_label": bool(prob >= label_threshold),
                "swbgt_pred": None if sw is None else float(sw),
                "risk_level": prob_to_risk(prob),
                "model_version": model_version,
            })
    return rows


def _bangkok_today():
    """Today's date in Asia/Bangkok (UTC+7, no DST), to align with Open-Meteo."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=7)).date()


def _real_frame_builder(end, history_days, forecast_days, thresholds=None):
    """Build the real Open-Meteo-backed per-province frame builder for ``main``.

    ``end`` is the Bangkok-local 'today' (the origin day); history covers
    ``end - history_days .. end`` and the forecast supplies the future tail.
    """
    start = end - pd.Timedelta(days=history_days)

    def builder(province):
        hist = openmeteo_client.fetch_history(
            province["lat"], province["lon"],
            start.isoformat(), end.isoformat())
        fcst = openmeteo_client.fetch_forecast(
            province["lat"], province["lon"], days=forecast_days)
        daily = _province_daily_frame(province, hist, fcst)
        if thresholds is not None:
            # attach per-doy p95 from precomputed province_thresholds
            d = daily.copy()
            d["doy"] = d["time"].dt.dayofyear
            thr = thresholds[thresholds["province_id"] == province["id"]]
            d = d.merge(thr[["doy", "p95"]], on="doy", how="left")
            daily = d.drop(columns=["doy"])
        return daily

    return builder


def main():
    """Wire real fetch + model load + DB write. Not exercised by unit tests."""
    import joblib

    from src.provinces import load_provinces
    from src.db_write import upsert_forecasts

    provinces = load_provinces("data/provinces.csv")
    # Trusted first-party artifact: our own LightGBM model serialized by the
    # training pipeline (joblib is the project's standard model format). Not
    # untrusted input -- path is fixed and local.
    model = joblib.load(MODEL_PATH)

    # p95 must come from the precomputed baseline thresholds, NOT recomputed from
    # the short recent history (compute_doy_percentiles filters to 1991-2020).
    thresholds = None
    try:
        thresholds = pd.read_parquet("data/processed/province_thresholds.parquet")
    except Exception:
        print("WARNING: province_thresholds.parquet not found; p95 features "
              "will be missing and prediction may fail on feature mismatch.")

    horizons = range(1, 8)
    generated_at = datetime.now(timezone.utc)   # real UTC stamp for the DB column
    origin = _bangkok_today()                   # origin aligned to Open-Meteo TZ
    # forecast must extend to origin + max(horizon); Open-Meteo includes 'today',
    # so request max(horizon)+1 days (extra days are trimmed by make_forecasting_frame).
    forecast_days = max(horizons) + 1
    builder = _real_frame_builder(origin, history_days=40,
                                  forecast_days=forecast_days,
                                  thresholds=thresholds)
    rows = build_forecast_rows(provinces, model, generated_at,
                               history_days=40, horizons=horizons,
                               frame_builder=builder, origin_date=origin)
    n = upsert_forecasts(rows)
    print(f"upserted {n} forecast rows "
          f"({provinces['id'].nunique()} provinces) generated_at={generated_at}")


if __name__ == "__main__":
    main()
