# P0 Forecast-Covariate Plumbing — Design

**Date:** 2026-06-07
**Sub-project:** 1 of 2 (P0 forecast covariates → then NDVI as sub-project 2)
**Status:** design approved; spec under review

## 1. Context & motivation

`docs/MODEL-IMPROVEMENT.md` measured the model's ceiling rigorously:
- All 7 model families converge at F2 ≈ 0.53–0.56 → the bottleneck is **feature
  information**, not the algorithm.
- Oracle headroom: antecedent-only PR-AUC **0.33** → with target-day weather **0.88**.
  The label is highly learnable *only* when the model can see the target day.
- The model is **blind to the forecast of the day it predicts**: at inference,
  `pipeline/run_forecast.py` already fetches the Open-Meteo forecast for the
  target days but uses it only for `swbgt_pred` — it is **thrown away as a feature**.
- Proven real lift (GEFS reforecast heat-index covariate): ROC 0.578→0.657,
  PR-AUC lift 1.22×→1.82× (**+49% rel**), concentrated at leads 3–5.

This sub-project wires forecast covariates into the leakage-safe pipeline so the
proven lever is realised. It is the **plumbing** — train/serve-consistent,
leakage-safe, validated on GEFS — gated so the production *retrain* waits until a
serve-time-matched forecast hindcast has accumulated.

## 2. Goal / non-goals

**Goal:** a single, shared, leakage-safe path that adds forecast heat-index
covariates (`fc_heat_index`, optionally `fc_tmax`, `fc_rh`) to BOTH training and
serving, identical by construction; validated to reproduce the GEFS A/B lift; with
a documented readiness gate before production retrain.

**Non-goals (out of scope here):**
- Retraining/deploying the production model with covariates **now** — blocked on
  data (forward store spans only ~8 days as of 2026-06-07; needs ~2–3 months / a
  hot season). This design *prepares* for it behind a gate.
- NDVI features (sub-project 2; `features.py` already has `ndvi_lag1/lag2` hooks).
- Changing the label, climatology, or model family.

## 3. Current state (relevant)

- **`src/features.py`**: `make_forecasting_frame()` emits one row per
  (origin_day × horizon) with `origin_time`, `target_time`, `horizon_k`, `y`, and
  antecedent/calendar/static features. `feature_columns()` returns every column
  except `{y, origin_time, target_time}` → **any `fc_*` column added to the frame
  is auto-included as a model feature.**
- **`pipeline/train.py`**: `train_model(dataset, …, frame=None)` builds frames,
  temporal-splits (train ≤2023 / val 2024 / test 2025), calibrates, F2-tunes,
  saves `models/heatwave_model.pkl`.
- **`pipeline/run_forecast.py`**: `build_forecast_rows()` builds the per-province
  frame from Open-Meteo history+forecast, keeps origin==today rows, scores k=1..7.
  The forecast `fcst` is fetched in `_real_frame_builder` and used for
  `swbgt_by_time` only.
- **Forecast stores** (`data/processed/`):
  - `forecast_store.parquet` — forward-collected, **serve-time-matched** (Open-Meteo).
    Cols: `province_id, issue_date, target_date, lead_k, fc_tmax, fc_rh, fc_heat_index`.
    ~3,234 rows, issue 2026-05-31 → present. **This is the production training source** (once mature).
  - `gefs_forecast_store.parquet` — NOAA GEFS reforecast, 2016–2019, 61,446 rows.
    Cols: `…, fc_tmax, fc_spfh` (heat-index derived in `train_p0.py`). **Validation only**
    (different NWP system than serve-time).
- **`scripts/train_p0.py`**: existing A (antecedent) vs B (+forecast) harness on GEFS.

## 4. Architecture & components

### 4.1 `src/forecast_covariates.py` (NEW — pure, no network/DB)
- `load_forecast_store(path) -> DataFrame` — read + normalise dtypes
  (`issue_date`, `target_date` as datetime; `lead_k` int).
- `join_forecast_covariates(frame, store, cols=("fc_heat_index",), require_coverage=True) -> DataFrame`
  - Left/inner-merge `store[cols]` onto `frame` on
    `frame.province_id == store.province_id`,
    `frame.origin_time == store.issue_date`,
    `frame.target_time == store.target_date`,
    `frame.horizon_k == store.lead_k`.
  - **Leakage-safe by construction**: store rows always satisfy `issue_date < target_date`;
    matching `origin_time==issue_date` means the covariate was knowable at origin.
  - `require_coverage=True` (training): inner join → keep only rows with a covariate
    (matched-rows A/B, mirrors `train_p0`). `False`: left join, `fc_*` may be NaN.
  - Returns the frame with `fc_*` columns appended (auto-picked by `feature_columns`).
- `build_serve_covariate(forecast_df, province_id, origin_date, horizons) -> DataFrame`
  - From the Open-Meteo forecast already fetched at serve, produce rows
    `(province_id, origin_time, target_time, horizon_k, fc_heat_index[, fc_tmax, fc_rh])`
    for k in horizons, using the **same heat-index computation as the store writer**.
- `forecast_store_readiness(store) -> dict` — coverage summary
  (distinct issue_dates, date span, #positives joinable) + a boolean `ready` against
  a documented threshold (e.g. ≥ ~60 issue-days spanning a hot season). Used to gate
  production retrain.

### 4.2 Train/serve consistency (THE load-bearing constraint)
The forward store's `fc_heat_index` is written by `scripts/collect_forecast.py` from
`fc_tmax`+`fc_rh`. The serve builder MUST compute `fc_heat_index` with the **identical
formula**. Mitigation: factor the heat-index-from-(tmax, rh) computation into ONE
function (reuse `src/heat_index.py`/`src/swbgt.py`) and call it from BOTH
`collect_forecast.py` and `build_serve_covariate`. A test asserts parity.

### 4.3 `pipeline/train.py`
`train_model(dataset, …, forecast_store=None)`. When provided, call
`join_forecast_covariates(frame, store, require_coverage=True)` before the split.
`None` (default) = antecedent-only, **behaviour unchanged** (backward-compatible).

### 4.4 `pipeline/run_forecast.py`
In `build_forecast_rows`/the serve path: after assembling `today_rows`, call
`build_serve_covariate(...)` and join `fc_*` onto them by `(target_time, horizon_k)`
BEFORE `predict_proba`, so the model sees the same `feature_columns` as training.
Only active when the loaded model's `feature_cols` include `fc_*` (so an
antecedent-only model is unaffected).

### 4.5 `scripts/train_p0.py`
Refactor its join to call `join_forecast_covariates` (test the production path, not a
parallel one). Keep the A vs B comparison; it must still reproduce the ~+49% PR-AUC lift.

## 5. Data flow
- **Train:** `dataset.parquet` → `make_forecasting_frame` →
  `join_forecast_covariates(forward_store, require_coverage=True)` → temporal split →
  train → calibrate → F2 threshold → `heatwave_model.pkl` (with `fc_*` in `feature_cols`).
- **Serve:** `run_forecast` fetches Open-Meteo history+forecast (already) →
  `build_serve_covariate` from the forecast → join onto origin==today rows →
  `predict_proba` with the same feature columns → risk rows → Supabase.

## 6. Leakage safety
- Store invariant `issue_date < target_date` (enforced at write in `collect_forecast.py`;
  re-asserted in `load_forecast_store`).
- Join binds `origin_time == issue_date`, so a covariate is only ever the forecast
  *issued at origin* for a *future* target. Unit test: no joined row has
  `issue_date >= target_date`, and `fc_*` is independent of `y`.

## 7. Production readiness gate
Production retrain with covariates only when `forecast_store_readiness(forward_store).ready`
is true (documented threshold). Until then the live model stays antecedent-only.
`collect_forecast.py` is scheduled (Windows Task Scheduler, daily) so the store matures.
GEFS is **never** used for the production model (NWP-system mismatch); validation only.

## 8. Testing
- `join_forecast_covariates`: key matching, `require_coverage` inner/left, NaN handling.
- Leakage guard: assert `issue_date < target_date` on all joined rows.
- Train/serve parity: `build_serve_covariate` value == store `fc_heat_index` for the
  same `(province, issue, target, lead)` inputs (shared heat-index fn).
- `train_model(forecast_store=synthetic)`: trains, `fc_*` present in `feature_cols`.
- Backward-compat: `train_model(forecast_store=None)` unchanged.
- Regression: `train_p0.py` via the new join still yields lift (B ROC > A by ~the
  documented margin on GEFS).

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Train/serve skew (different heat-index) | one shared heat-index fn; parity test |
| Coverage shrink (few matched rows) | readiness gate; train only when mature |
| GEFS ≠ serve-time NWP | GEFS validation-only; production trains on forward store |
| Silent antecedent fallback at serve | covariate path keyed on model `feature_cols`; warn if model expects `fc_*` but store/forecast missing |

## 10. Out of scope / follow-ups
- **Production retrain + deploy** with covariates — when the gate opens (~2–3 months).
- **Sub-project 2 — NDVI**: source MODIS MOD13A3 (`src/ndvi_ingest.py`/`ndvi_processor.py`
  exist), merge `ndvi_lag1/lag2` onto the daily frame (hooks already in `features.py`),
  ablate (ΔPR-AUC on the fixed temporal split). Expectation per docs: marginal — a slow
  antecedent feature cannot cross the signal ceiling; do it as a measured ablation on top
  of P0, keep only if it moves the needle.

## 11. Success criteria
1. One shared, leakage-safe covariate path used by train, serve, and the GEFS harness.
2. Leakage + train/serve-parity tests pass; backward-compat preserved.
3. GEFS A/B via the new code reproduces the documented lift (B > A).
4. `forecast_store_readiness` + scheduled collector in place; production retrain
   correctly gated (still antecedent-only today, flips automatically when data matures).
