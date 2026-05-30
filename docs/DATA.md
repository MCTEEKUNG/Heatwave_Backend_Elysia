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
- `HEATWAVE_STRIDE` — build a representative `provinces[::stride]` subset

Quick end-to-end sanity check on a few provinces (no disk writes):
`.\.venv\Scripts\python.exe scripts\validate_data_seam.py`

## 3. Caveats (read before trusting numbers)

1. **Open-Meteo free tier is hourly-rate-limited.** A full 1991–2025 request is
   "heavy"; only a few succeed per minute and the **hourly** budget caps a full
   77-province build in one sitting. The builder paces + cools down, but a full
   build may need to run across more than one hourly window (it resumes). Error
   seen: *"Hourly API request limit exceeded."*
2. **sWBGT_max label bias (highest-value accuracy fix).** sWBGT is computed from
   daily `temperature_2m_max` + daily-**mean** RH. Physically, the daily *max*
   temperature coincides with the daily *min* humidity, not the mean — so
   `swbgt_max` is systematically biased. The #1 data improvement is to fetch
   **hourly** temp+RH, compute hourly sWBGT, and take the daily max
   (`src/openmeteo_client.py` already flags this). Affects label fidelity, not
   the pipeline's correctness.
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
