# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Heatwave forecasting for Thai provinces. **Four codebases share one root directory** — know which one you're in before touching anything:

| Codebase | Lives in | Stack | Purpose |
|----------|----------|-------|---------|
| **ML / forecasting** (Python) | `src/*.py`, `pipeline/`, `evaluation/`, `scripts/`, `tests/` | Python 3.12 `.venv`, pandas/sklearn/lightgbm | trains the heatwave model |
| **Product backend** (TypeScript) | `src/index.ts`, `src/routes/`, `src/line/`, `package.json`, `tsconfig.json` | Elysia + Bun | serves predictions + LINE bot |
| **Product frontend** | `HeatMAP-Frontend/` | Expo / React Native, Bun | mobile/web app |
| **Training dashboard** (local-only) | `training-dashboard/` | FastAPI (`server/`, :8000) + Vite/React (`web/`, :5173) | live training UI |

**Gotcha: `src/` is mixed** — Python ML modules (`features.py`, `model.py`, …) and the TypeScript Elysia backend (`index.ts`, `routes/`, `line/`) live in the *same* folder. The root `package.json`/`bun.lock`/`tsconfig.json` belong to the **backend**, not the ML code.

## Commands

Platform is **Windows + PowerShell**; the Python interpreter is `.venv\Scripts\python.exe` (always use it, not bare `python`). `conftest.py` puts the repo root on `sys.path`, so `import src.*` / `import pipeline.*` work and pytest must be run **from the repo root**.

```powershell
# --- Python ML ---
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/ -q                          # full suite
.\.venv\Scripts\python.exe -m pytest tests/test_features.py::test_name -v   # single test
.\.venv\Scripts\python.exe pipeline\build_era5_dataset.py                # build canonical v2 dataset
.\.venv\Scripts\python.exe scripts\train_era5.py                         # train + eval (temporal)
.\.venv\Scripts\python.exe scripts\bakeoff.py                            # compare model families -> leaderboard

# --- Product backend (Elysia/Bun, root) ---
bun install ; bun test ; bun run dev          # dev = hot-reload src/index.ts ; bun test src/line for LINE tests

# --- Product frontend (Expo) ---
cd HeatMAP-Frontend ; bun install ; bun run lint ; bun start

# --- Training dashboard (local) ---
cd training-dashboard ; .\dev.ps1     # starts FastAPI :8000 + Vite :5173 ; .\stop.ps1 to stop
```

The dashboard FastAPI server is launched **without `--reload`** — restart it to pick up server-side changes.

## The core architecture: leakage-safe forecasting (read before changing the model)

This is a per-(province, horizon `k`=1..7) **rare-event binary forecast** (~4% positives). The non-obvious, load-bearing design spans several files:

- **`src/features.py` — the #1 rule.** Features are **antecedent-only**: every value feature is built with `.shift(1).rolling(...)` so day `t`'s own value never enters its own features. The target is `y = heatwave.shift(-k)` (heatwave `k` days in the future). `LEAKY_COLS` lists target-day truth columns that must **never** become raw features. `make_forecasting_frame` stacks one row per (origin-day × horizon).
- **Temporal split, never random.** Train on earlier years, validate/test on later years (`src/splits.py`, `evaluation/cv.py` rolling-origin). A random split on autocorrelated daily weather is leakage — it produces fake ~0.99 scores.
- **Label** (`src/labels.py`, `src/climatology.py`): heatwave = value `≥` per-day-of-year p95 **and** part of a `≥2`-day run. `src/swbgt.py` / `src/heat_index.py` compute the heat metric.
- **Calibration + operating point** (`src/calibration.py`): isotonic calibration + F2-tuned threshold on the validation fold.
- **Metrics** (`evaluation/heatwave_metrics.py`): PR-AUC, F2, ROC, Brier/BSS. For rare events, **normalize PR-AUC by prevalence** (`PR-AUC / base_rate`) before comparing across years — raw PR-AUC's no-skill floor *is* the base rate.

### Hard-won integrity rules (the project exists because a prior version violated them)
- **ERA5 reanalysis / Open-Meteo "historical forecast" = analysis (the truth), NOT a forecast of the future.** Using past reanalysis as antecedent features is clean; using the **target day's** reanalysis as a feature is leakage (see `scripts/oracle_headroom.py`, which uses it deliberately to measure the skill *ceiling*). The Open-Meteo Historical Forecast API returns analysis-quality values for past dates (`corr≈1.0` with actuals) — do not train on it.
- **Genuine lead-`k` forecasts only come from forward-collection or reforecasts.** `scripts/collect_forecast.py` (forward, scheduled daily) and `scripts/fetch_gefs_reforecast.py` (NOAA GEFSv12, real 2000–2019, free) build the leakage-safe forecast store keyed by `(province, issue_date, target_date, lead_k)` with `issue_date < target_date`.
- Antecedent-only models plateau around ROC ≈ 0.6–0.76. The only proven lever past that is **forecast covariates** (P0). See `docs/MODEL-IMPROVEMENT.md` for the full diagnosis, oracle/noise-model headroom, and the P0 status.

## Data & datasets

- `data/` is **git-ignored**; the **reproducible builders are the source of truth**, not the parquet files.
- `data/processed/dataset.parquet` — **v1** (Open-Meteo, 1991–2025, 20 provinces). Currently the **better-scoring** model (F2 ≈ 0.56).
- `data/processed/dataset_era5.parquet` — **v2 canonical** (real ERA5 6-hourly, 2016–2025, 77 provinces, daily-max heat-index label). Cleaner/leakage-free but scores lower due to the short humidity-era history; see `docs/DATA.md` §5 and `docs/DATASET_PROFILE.md`.
- **`config.yaml` describes an ERA5/MODIS-NDVI design that is NOT wired into training** (historical/aspirational). The actually-wired pipeline is documented in `docs/DATA.md` — trust the docs and the code, not `config.yaml`.

## Database (Supabase)

`DATABASE_URL` in `.env` (git-ignored) is a Supabase pooler connection. Data lives in a **private `heatwave` schema** (not exposed via the Data API). Backend connects with `postgres` (Bun); Python writes with `psycopg` (`src/db_write.py`). Migrations in `supabase/migrations/`.

## Plans & docs

Implementation plans live in `docs/superpowers/plans/`; design/status docs in `docs/` (`DATA.md`, `ML-APPROACH.md`, `MODEL-IMPROVEMENT.md`, `PRODUCTION.md`). When working a multi-step ML change, check `docs/MODEL-IMPROVEMENT.md` first — it carries the current diagnosis and the prioritized levers.
