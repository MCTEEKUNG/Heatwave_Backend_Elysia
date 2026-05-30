# Dataset Profile

- rows: 281,281  provinces: 77
- years: 2016–2025 (ERA5 6-hourly era; earlier years are daily/t2m-only, out of v2 scope)

## Candidate labels (profiled on `era5_daily.parquet`)

| label | definition | base rate | verdict |
|-------|-----------|-----------|---------|
| A — absolute | `heat_index_max ≥ 41 °C` | **16.39%** | too common — "any hot-humid day", not a heatwave; breaks rare-event comparability |
| **B — relative (CHOSEN)** | `heat_index_max ≥ per-doy p95` **AND** ≥2-day run | **4.3%** | proper rare-event regime; anomalous-for-season + persistent = a heatwave |

## Decision (Phase 3 gate)

**Canonical label = B (relative).** Rationale: a 16% positive rate is not a "heatwave" — it
labels routine hot-season days and would silently change the problem from rare-event to
common-event (invalidating the F2/precision/recall calibration tuned for ~4%). Label B
(anomalous *and* persistent) matches the project's heatwave definition, gives a ~4.3%
rare-event rate consistent with the prior dataset, and reuses the existing climatology
machinery (`src/climatology.compute_doy_percentiles` + `src/labels.label_heatwave`).

Reproduce: `.venv\Scripts\python.exe pipeline\build_era5_dataset.py` (default `mode="relative"`).

> Note (future refinement): the per-doy p95 is currently computed over all available years
> including the test window — a small, low-variance climatological leak. A stricter version
> would fit p95 on train years only. Acceptable for v2; flagged for later.
