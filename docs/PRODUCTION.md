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
| ✅ DONE | Supabase wired + live write path proven | `DATABASE_URL` connects (smoke: 77 provinces); real Open-Meteo → model → upsert into `heatwave.forecasts` verified (Bangkok/Chiang Rai/Narathiwat, queryable via the Elysia API SQL) |
| 🟡 PARTIAL | Daily job at full scale | proven on a 3-province subset; full 77-province daily run needs rate-limit-friendly batching/scheduling (cron) |

**Verdict: production-READY, and now LIVE-WIRED.** The model is trained,
evaluated, calibrated, diagnosed, saved, its consumption path verified, AND the
real serving path runs end-to-end into Supabase. Remaining work is
coverage/fidelity improvements and operationalizing the daily job at full scale
(scheduling + rate-limit batching) — named below, not silently assumed done.

**Supabase project:** `heatwave-forecaster` (org Heatwave-AI, ref
`qpvvvwgfnucypzxhytmy`, region ap-southeast-1). Schema applied from
`supabase/migrations/0001_heatwave_schema.sql`.

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
- **P2 — Scale the daily job to all provinces + schedule it (cron).**

## Going live

1. `models/heatwave_model.pkl` — produced by `scripts/train_production.py`. ✅
2. `DATABASE_URL` (Supabase pooler, transaction mode 6543) in `.env`. ✅ — verified by
   `bun run smoke` (reads `heatwave.provinces` = 77).
3. Real forecast write — **proven** via `scripts/run_forecast_live.py` (3-province
   subset): live Open-Meteo → model → upsert into `heatwave.forecasts`. ✅
4. Schema applied from `supabase/migrations/0001_heatwave_schema.sql`
   (`scripts/db_apply.py`); 77 provinces seeded with Thai + English names. ✅
5. **Remaining (ops):**
   - Run the daily job for **all 77 provinces** (`pipeline/run_forecast.main()`),
     batched to respect the Open-Meteo hourly limit (the 3-province subset is the
     proof; full scale needs throttling). Schedule via cron.
   - Run the **Elysia backend** (`src/index.ts`, `/api/...`) with the same
     `DATABASE_URL` and point the mobile app at it (deploy/hosting).
   - Reset the Supabase DB password (it was shared in chat during setup).
