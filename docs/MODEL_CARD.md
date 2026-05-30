# Model Card — Heatwave Forecaster (production candidate)

Machine-readable provenance: `models/model_card.json` (written by
`scripts/train_production.py`). This is the human-readable companion.

## Overview
- **Model**: `heatwave-lgbm` — LightGBM gradient-boosted trees wrapped in
  `src.model.CalibratedModel` (isotonic calibration + F2-tuned threshold).
- **Task**: per `(province, lead 1–7 days)` binary classification of a heatwave
  day (sWBGT ≥ day-of-year p95 **and** ≥ 2-day run).
- **Stage**: **production CANDIDATE** — trained on **20 / 77 provinces** (all 6
  regions). Not the full-coverage production model; see Limitations.
- **Artifact**: `models/heatwave_model.pkl` (joblib, ~700 KB). Gitignored —
  reproduce with `scripts/train_production.py`.

## Intended use
- Operational multi-day heatwave **early warning** per Thai province, consumed
  by `pipeline/run_forecast.py` → Elysia API → mobile app.
- The operating point is **recall-leaning** (catch heatwaves; tolerate false
  alarms) — appropriate for a public-safety warning, but see precision below.

## Training data
- **Source**: Open-Meteo Archive (ERA5 reanalysis), 1991–2025, daily.
- **Label**: sWBGT-based, daily-aggregate (see `docs/DATA.md` for the known
  daily-vs-hourly bias — the top label-fidelity improvement).
- **Split** (temporal, no leakage): train ≤ 2023 · validate 2024 · test 2025.
- **Features** (34): leakage-safe rolling stats of sWBGT/Tmax/RH, climatology
  anomaly, seasonal sin/cos, static lat/lon/province, horizon.

## Evaluation (test 2025, threshold tuned on validation 2024)
| metric | value | baseline |
|--------|-------|----------|
| F2 | **0.556** | climatology 0.47 · persistence 0.42 |
| PR-AUC | 0.332 | base rate 0.150 |
| ROC-AUC | 0.760 | — |
| Brier skill | 0.094 | vs climatology |
| recall | 0.864 | — |
| precision | 0.229 | — |

Full diagnostics (per-horizon, per-region/province slices, calibration,
threshold sweep, feature importance) live in
`experiments/results/model_report.json` and the dashboard's deep-dive view.

## Limitations / known issues
- **Coverage 20/77 provinces** — generalization to unbuilt provinces is
  unverified. Expand before full production.
- **Weak slices**: Northeast region (F2 0.39) and notably **Chiang Rai
  (F2 0.10)** — the model is near-blind in some arid/northern, low-base-rate
  areas. Prioritize these (see development plan).
- **Low precision (0.23)**: many false alarms at the recall-leaning F2 point —
  needs a product decision on alert tolerance.
- **Label bias**: daily-aggregate sWBGT (Tmax + mean RH) vs the correct
  hourly→daily-max. Affects all models equally.

## Reproduce
```powershell
.\.venv\Scripts\python.exe scripts\build_full_dataset.py    # data (resumable)
.\.venv\Scripts\python.exe scripts\train_production.py       # artifact + verify
.\.venv\Scripts\python.exe scripts\model_report.py           # diagnostics + plan
```
See `docs/PRODUCTION.md` for the path from this candidate to live serving.
