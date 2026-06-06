# Heatwave — Go-Live Runbook (local model → live forecasts on the frontend)

**Goal:** after a model is trained locally, get its forecasts flowing all the way to the
live HeatMAP frontend.

**Verified architecture (the model does NOT get loaded by the backend):**
```
[Train in dashboard]  →  models/dashboard/<name>.pkl
        │ Ops tab: Promote (file copy)
        ▼
   models/heatwave_model.pkl   (the production artifact)
        │ Python daily job: scripts/run_daily_forecast.py  (joblib.load → predict)
        ▼
   Supabase  heatwave.forecasts   ← this is where the model's output enters the system
        │ Bun/Elysia backend reads via DATABASE_URL (postgres pkg, direct Postgres)
        ▼
   Backend API (Render: heatwave-backend-elysia.onrender.com)
        ▼
   HeatMAP-Frontend (Vercel: heat-map-frontend.vercel.app) — real users
```

**Current production facts (measured 2026-06-01):**
- Frontend live on Vercel, calls `EXPO_PUBLIC_API_URL=https://heatwave-backend-elysia.onrender.com`.
- Backend live on Render (`/api/health` → 200) **but running STALE code**: `origin/main`
  has **no** `/api/forecast/map` route (returns 404). The Supabase-reading forecast routes
  exist only on the feature branches.
- `DATABASE_URL` auth currently fails — **password issue, not format** (username
  `postgres.{ref}` + pooler host:6543 are correct). Likely an outdated password or
  un-URL-encoded special characters.
- No CI workflow in this repo (`.github/workflows` absent) → the daily forecast job is not
  automated.
- Model skill is modest (antecedent ceiling). The proven P0 forecast covariate
  (ROC 0.578→0.657) is **not yet wired into production training** — this runbook ships a
  working-but-not-production-grade model; improving skill is a separate track.

---

## BLOCKER — P0: fix `DATABASE_URL` (USER — credential, gates P2–P4)

Everything downstream of "generate forecasts" needs a working Supabase connection (both the
daily job that *writes* and the backend that *reads*).

1. Supabase Dashboard → Project `qpvvvwgfnucypzxhytmy` → **Settings → Database → Database
   password**. Copy the current password (or **Reset database password** if unknown).
2. If the password contains any of `@ : / ? # [ ] %` it MUST be **URL-encoded** in the
   connection string (e.g. `@` → `%40`, `#` → `%23`).
3. Update the password in BOTH places:
   - local `.env` → `DATABASE_URL=...`
   - Render → service `heatwave-backend-elysia` → Environment → `DATABASE_URL`.
4. (Optional) confirm the project isn't **paused** (free tier pauses on inactivity) — resume
   it in the dashboard if so.
5. Verify (this command masks the password):
   ```
   .venv/Scripts/python.exe -c "import os;from urllib.parse import urlparse;\
   url=[l.split('=',1)[1].strip().strip('\"') for l in open('.env',encoding='utf-8') if l.startswith('DATABASE_URL')][0];\
   import psycopg;c=psycopg.connect(url,connect_timeout=15);cur=c.cursor();\
   cur.execute('select count(*) from heatwave.forecasts');print('OK forecasts rows=',cur.fetchone()[0])"
   ```
   Expected: `OK forecasts rows= <n>` (no auth error).

When this passes, ping me — I run P2 onward.

---

## P1 — Produce the production model  (USER drives the dashboard)

1. Dashboard **Train** tab → select `lgbm` → **Start**. Dataset (255,680 rows) is ready.
   Wait for `done` + metrics.
2. Dashboard **Ops** tab → find the `lgbm` model → type the confirm → **Promote**. This
   copies it to `models/heatwave_model.pkl`.
3. (Skill is modest by design — that's fine for plumbing the pipeline end-to-end.)

*I can run this via script instead if you prefer, but you already have the dashboard open.*

---

## P2 — Generate forecasts into Supabase  (ME — needs P0 done)

1. Run the daily forecast job once:
   `.venv/Scripts/python.exe scripts/run_daily_forecast.py`
   (loads `models/heatwave_model.pkl` → predicts 77 provinces × 7 leads → `upsert_forecasts`).
2. Verify rows exist: `select count(*), max(generated_at) from heatwave.forecasts`.

---

## P3 — Backend: get the forecast routes onto the deploy branch  (DECISION + ME prep, USER deploys)

**The risk:** `origin/main` (what Render deploys) lacks the forecast routes. The feature
branches have them, but **`feat/clean-era5-ndvi-dataset`'s `src/index.ts` is HYBRID** — it
still calls `runPythonScript(.../prediction/predict.py)` for the old `/api/predict` route the
live frontend uses. Deploying that to Render (no Python, no TRAIN dir) would 500 `/api/predict`.
`feat/region-line-oa`'s backend is the cleaner pure-Bun rewrite.

**Decision needed (yours):** which backend goes to production?
- **Option A — minimal, safe:** cherry-pick ONLY the backend files (`src/index.ts`,
  `src/routes/forecast.ts`, `src/db.ts`, `src/routes/*`) — reconciled to pure-Bun (drop the
  Python `/api/predict` route or stub it) — onto a small PR into `main`. Render auto-deploys.
  *Does not drag the 70-commit dashboard branch into main.*
- **Option B:** point Render's deploy branch at a dedicated backend branch instead of `main`.

Then verify: `curl https://heatwave-backend-elysia.onrender.com/api/forecast/map` → real rows
(not 404). Also set `DATABASE_URL` in Render (P0 step 3).

*I will prepare the reconciled backend PR on request; I will NOT merge to main or trigger a
production deploy without your explicit go-ahead.*

---

## P4 — Verify the full chain  (ME + USER)

1. `…/api/forecast/map` returns real rows.
2. Frontend map page shows colored provinces. (Note: `PredictionResults.tsx` calls the OLD
   `/api/predict`; the map uses the new routes. Decide whether to retire `/api/predict` in the
   frontend.)
3. Spot-check a province detail.

---

## P5 — Automate the daily forecast  (DESIGN needed before YAML — deferred)

A daily GitHub Action needs `models/heatwave_model.pkl`, which is **gitignored and not on the
CI runner**. Decide the artifact story FIRST:
- **train-in-CI** (CI runs train + forecast), or
- **download the model** from a Hugging Face repo / GitHub Release the Promote step uploads to.

Once decided, the workflow runs `run_daily_forecast.py` on a cron with `DATABASE_URL` (+ any
data-source keys) as repo secrets. **Do not write this YAML until the artifact story is fixed.**

---

## Who does what (summary)
| Step | Owner | Blocked by |
|------|-------|-----------|
| P0 fix DATABASE_URL password | **USER** | — |
| P1 train + promote | **USER** (dashboard) | — |
| P2 generate forecasts → Supabase | ME | P0 |
| P3 reconcile + deploy backend | ME prep / **USER** deploy decision | — (deploy after P2) |
| P4 verify chain | ME + USER | P0,P2,P3 |
| P5 automate | ME (after design) + USER (secrets) | artifact story |
