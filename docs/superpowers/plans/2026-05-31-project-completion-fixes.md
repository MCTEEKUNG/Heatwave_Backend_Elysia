# Project Completion — Fan-Out Plan

Concrete remaining work to complete the Heatwave project, drawn from `docs/PRODUCTION.md`
(documented gaps, not invented scope). Split into PARALLEL units (disjoint files, fanned
out to subagents) and SEQUENTIAL units (touch shared pipeline files / gated on data).

## Parallel units (fan-out — each owns ONLY its new files; reads anything)

| Unit | Goal (PRODUCTION.md item) | Files it OWNS (create) |
|------|---------------------------|------------------------|
| **U1 Operating point** | P1 "tune operating point": precision-leaning + two-tier (watch/warning) + per-horizon thresholds | `src/operating_point.py`, `tests/test_operating_point.py` |
| **U2 Daily job at scale** | ops "scale daily job to 77 provinces, rate-limit batching, resumable" | `scripts/run_daily_forecast.py`, `tests/test_run_daily_forecast.py` |
| ~~U3 Weak-slice report~~ | DROPPED — `scripts/model_report.py` already produces per-region/per-province error slices (functional duplicate). | — |

Partition is disjoint: no file appears under two units; none touches `src/features.py`,
`pipeline/build_*`, or `train_*` (the shared/sequential surface). Each unit is a new
module + its own test → composes without conflict. Hard guard for both agents: read
anything, but WRITE only your two files — never `experiments/results/leaderboard.json`
or shared modules; if you need to edit outside your set, STOP and report.

> GEFS pull (S1 input) verified ALIVE (downloading 2016+ inits) — let it finish; do not
> abandon. "Complete" is anchored to this finite PRODUCTION.md punch-list (U1, U2, S1, S2),
> not an open-ended condition.

## Sequential units (controller handles; coupled or gated — NOT fanned out)

- **S1 Powered P0 measurement** — gated on the GEFS pull; `scripts/train_p0.py` (shared with data engine). Run after data lands; decides whether to wire P0.
- **S2 NDVI merge + climatology-leakage fix** — both edit `pipeline/build_era5_dataset.py` (+ `src/climatology.py`), so they share files and must be one sequential change, not parallel.

## After fan-out: integrate + verify
Run `pytest tests/ -q` (Python) — disjoint files compose, but check the new modules
interoperate with existing signatures. Then update `docs/PRODUCTION.md` to reflect what's done.

## Execution status (2026-05-31)

- **U1 operating point** ✅ — `src/operating_point.py` (+21 tests). Commits 7096b52, c4f67fa.
- **U2 daily job at scale** ✅ — `scripts/run_daily_forecast.py` (+24 tests, `--dry-run` schedule 16 batches/77 prov). Commit 0dbce11.
- **Integration** ✅ — full suite **126 passed**; disjoint partition composed with zero conflict.
- **S1 powered P0** ⏳ — GEFS dense 2016–2019 pull progressing (~18 inits/hr; ~7 h for full set). Apparatus complete (`train_p0.py`); a fully-powered number is download-bound. Run `train_p0.py` once the store has enough inits.
- **S2 NDVI merge / climatology-leakage fix** — deferred (low impact per oracle/CV evidence; NDVI is a slow antecedent feature that won't cross the measured ceiling). Tracked, not blocking.

**"Complete" is anchored here:** the finite PRODUCTION.md parallelizable punch-list (U1, U2)
is done + verified; the remaining production lever (P0) is apparatus-complete and
data-accumulating. No further engineering compresses the GEFS download time.
