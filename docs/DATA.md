# Heatwave-AI — Data Card

What data the model needs, where it comes from, how to (re)build it, and the
caveats that matter. This documents the **wired** data pipeline
(`pipeline/build_dataset.py` → `data/processed/dataset.parquet` → training).

## 1. What the model trains on

| Item | Value |
|------|-------|
| Source | **Open-Meteo Historical Weather API** (ERA5 reanalysis), free, no API key |
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Spatial unit | 77 Thai provinces (`data/provinces.csv`, lat/lon centroids) |
| Period | **1991-01-01 → 2025-12-31** (daily) |
| Raw variables fetched | `temperature_2m_max`, `relative_humidity_2m_mean` (only these two are needed to derive the label) |
| Climatology baseline | 1991–2020 (for day-of-year p95) |

### Derivation (in code)
1. **sWBGT** (simplified wet-bulb globe temp) per day from `temperature_2m_max`
   + `relative_humidity_2m_mean` (`src/swbgt.py`).
2. **p95 climatology**: 95th percentile of sWBGT for each day-of-year, ±7-day
   window, over the 1991–2020 baseline (`src/climatology.py`).
3. **Heatwave label**: a day is a heatwave iff `sWBGT_max ≥ p95(doy)` **and** it
   belongs to a run of **≥ 2** consecutive exceedance days (`src/labels.py`).

### `data/processed/dataset.parquet` schema
`province_id, time, temperature_2m_max, relative_humidity_2m_mean, swbgt_max,
p95, is_hot, heatwave`
(`lat`/`lon` are merged from `provinces.csv` at train time.)
Companion: `data/processed/province_thresholds.parquet` (`province_id, doy, p95`).

Observed base rates (sample): `is_hot ≈ 6%`, `heatwave ≈ 3–4%` of days — a
**rare-event** problem.

## 2. How to build it

```powershell
# from repo root, with the venv deps installed (incl. pyarrow)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\build_full_dataset.py
```

The build is **resumable** (one checkpoint part per province under
`data/processed/_parts/`; re-running skips provinces already built) and
**rate-limit aware** (retries with backoff; a long cooldown after a 429).

**Tunable via env vars:**
- `HEATWAVE_SLEEP` — seconds between successful requests (default 20)
- `HEATWAVE_COOLDOWN` — seconds to wait after a 429 (default 75)
- `HEATWAVE_SUBSET=N` — build a **regionally-stratified** ~N-province subset
  (recommended for a first training set: covers all 6 regions, ~one hourly window)
- `HEATWAVE_WAIT_RESET=1` — poll gently until the hourly limit clears, then build
  (lets you launch it and walk away)
- `HEATWAVE_HOURLY=1` — derive a **correct daily-max sWBGT from hourly** data
  (higher label accuracy; see §3.2). ~24× heavier requests — use for targeted
  high-accuracy rebuilds, not the first full build.
- `HEATWAVE_STRIDE` — alternative even-`provinces[::stride]` subset

Example first build (stratified 20 provinces, self-starting):
`$env:HEATWAVE_SUBSET=20; $env:HEATWAVE_WAIT_RESET=1; .\.venv\Scripts\python.exe scripts\build_full_dataset.py`

Quick end-to-end sanity check on a few provinces (no disk writes):
`.\.venv\Scripts\python.exe scripts\validate_data_seam.py`

## 3. Caveats (read before trusting numbers)

1. **Open-Meteo free tier is hourly-rate-limited.** A full 1991–2025 request is
   "heavy"; only a few succeed per minute and the **hourly** budget caps a full
   77-province build in one sitting. The builder paces + cools down, but a full
   build may need to run across more than one hourly window (it resumes). Error
   seen: *"Hourly API request limit exceeded."*
2. **sWBGT_max label bias (highest-value accuracy fix) — fix now implemented,
   off by default.** The default daily path computes sWBGT from daily
   `temperature_2m_max` + daily-**mean** RH; physically the daily *max*
   temperature coincides with the daily *min* humidity, so `swbgt_max` is
   biased. The correct fix — fetch **hourly** temp+RH, compute hourly sWBGT, take
   the daily max — is implemented (`openmeteo_client.fetch_history_hourly` +
   `build_dataset.hourly_to_daily_swbgt`, enable with `HEATWAVE_HOURLY=1`). It is
   **off by default** because it is ~24× heavier and collides with the hourly
   rate limit. **Tension to weigh:** on the free tier you can have *broad daily
   coverage* OR *hourly accuracy on a few provinces*, not both quickly — favor
   coverage for the first training, hourly as a later accuracy pass (or a paid
   tier / bulk ERA5 download for both).
3. **Two data designs exist; we use the wired one.** `config.yaml` describes a
   heavier **ERA5 surface/upper + MODIS-NDVI (Google Earth Engine)** design with
   heat-index labeling. That path is **not wired** into `train_model`. This card
   documents the **Open-Meteo + sWBGT** path that the code actually runs. The
   ERA5/NDVI path is a larger, separate effort — pursue it only if the added
   predictors (vegetation, upper-air) are worth the ingestion complexity.

## 4. Status

`v1` dataset is built from however many provinces have completed (see
`data/processed/_parts/`). Re-run `build_full_dataset.py` (across hourly windows
as needed) to reach all 77. The large parquet artifacts are git-ignored; the
**reproducible builder** is the source of truth.

## 5. Canonical clean dataset v2 — ERA5 + (NDVI pending): `dataset_era5.parquet`

Built per `docs/superpowers/plans/2026-05-31-clean-era5-ndvi-dataset.md`. **All
future ERA5-based training references this dataset.**

| Item | Value |
|------|-------|
| Source | **ERA5 reanalysis** (Copernicus CDS), `.nc` from the `MCTEEKUNG/Heatwave_Backend_Elysia` repo via `scripts/fetch_era5_repo.py` |
| Temporal scope | **2016–2025** (6-hourly era; 2000–2015 are daily/t2m-only → out of scope) |
| Spatial | all **77** provinces (nearest 0.25° cell to centroid) |
| Raw vars | `t2m, d2m, sp, u10, v10` (6-hourly) |
| Daily aggregates | `t2m_c_max, rh_mean, heat_index_max` (**6-hourly→daily-max, the correct intensity**), `wind_speed_max, sp_mean` |
| Label | **B (relative): `heat_index_max ≥ per-doy p95` AND ≥2-day run** (~4.3% base rate) — see `docs/DATASET_PROFILE.md` for the decision vs the rejected absolute 16% label |
| Split | **temporal** — train 2016–2021 / val 2022–2023 / test 2024–2025 |
| Build | `.venv\Scripts\python.exe pipeline\build_era5_dataset.py` (resumes from `era5_daily.parquet`) |

**Pipeline:** `src/heat_index.py` (Magnus RH + Rothfusz HI) → `src/era5_ingest.py`
(NetCDF→daily, rejects daily files loudly) → `pipeline/build_era5_dataset.py`
(label) → `src/features.py` (leakage-safe antecedent features) → `scripts/train_era5.py`.

**Status (honest):** the clean v2 model (`era5_lgbm`, F2 0.317) currently scores
**below** the v1 Open-Meteo model (F2 0.556) — **not** because the data is worse but
because requiring humidity restricted training to 6 years (2016–2021) that are cooler
than the 2024–25 test years (positive rate drifts 2.6%→8.1%), and antecedent-only
features hit the known signal ceiling. See `docs/MODEL-IMPROVEMENT.md §5` for the full
diagnosis and next options. **v1 remains the better-scoring model; v2 is the clean,
reproducible foundation** for the history/label-robustness/forecast-covariate work.

> NDVI (NASA MOD13A3) ingestion exists (`src/ndvi_ingest.py`) but is **not yet merged**
> into `dataset_era5.parquet`; it is deferred as a measured ablation (a slow antecedent
> feature won't recover the history/shift deficit).
