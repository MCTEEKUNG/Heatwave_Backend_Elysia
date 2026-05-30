# Path to Production — Heatwave Forecaster

This is the synthesis of the diagnostics in
`experiments/results/model_report.json` (also rendered live in the dashboard's
"production readiness" + "development plan" panels). It states honestly what is
**done**, what is **partial**, and what is **blocked** on external systems.

## Readiness checklist

| status | gate | note |
|--------|------|------|
| ✅ DONE | Beats climatology + persistence | test F2 0.556 vs 0.47 / 0.42 |
| ✅ DONE | Probabilities calibrated | isotonic (pooled); Brier skill 0.094 |
| ✅ DONE | Diagnostics + error analysis | per-horizon, slices, calibration, sweep, importance |
| ✅ DONE | Artifact saved + **consumption path verified** | `joblib.load → build_forecast_rows` runs (21 rows) |
| 🟡 PARTIAL | Data coverage = 77 provinces | **20/77** built; resumable |
| 🟡 PARTIAL | Hourly-sWBGT label fidelity | daily-aggregate in use; `HEATWAVE_HOURLY=1` available |
| 🟡 PARTIAL | Alarm precision acceptable | 0.23 at recall 0.86 — product sign-off needed |
| 🔴 BLOCKED | Live serving wired | needs `DATABASE_URL`, live fetch, deploy infra |

**Verdict: production-READY as a candidate.** The model is trained, evaluated,
calibrated, diagnosed, saved, and its consumption path is verified. The
remaining items are coverage/fidelity improvements and external infrastructure —
named below, not silently assumed done.

## Development plan (prioritized)

- **P0 — Expand coverage 20 → 77 provinces.** Biggest generalization lever.
  `scripts/build_full_dataset.py` (resumable across hourly windows) → re-run
  `train_production.py` + `bakeoff.py`.
- **P0 — Fix weakest slices (Northeast; Chiang Rai F2 0.10).** Inspect those
  provinces' climatology/feature distributions; consider per-region thresholds
  or features for arid/northern, low-base-rate climates.
- **P1 — Tune the operating point** for the app's false-alarm tolerance using
  the validation threshold sweep (precision-leaning point or two-tier alerts).
- **P1 — Fix the sWBGT label bias** (hourly → daily-max) for key provinces and
  compare on the leaderboard.
- **P2 — Per-horizon decay** (F2 0.62 → 0.53 across lead 1→7): horizon-specific
  calibration/threshold or separate long-lead handling.
- **P2 — Wire live serving.**

## Going live (the BLOCKED gate, concretely)

1. `models/heatwave_model.pkl` — produced by `scripts/train_production.py`. ✅
2. Set `DATABASE_URL` (Supabase Postgres pooler) so `pipeline/run_forecast.main()`
   can upsert predictions.
3. Run `pipeline/run_forecast.main()` (or schedule it daily) — fetches the
   Open-Meteo forecast, builds rows via the verified path, writes to the
   `heatwave` schema.
4. The Elysia backend (`src/index.ts`, `/api/...`) serves those rows to the
   mobile app.

Steps 2–4 require credentials/infrastructure not available in this workspace —
hence BLOCKED here, not done.
