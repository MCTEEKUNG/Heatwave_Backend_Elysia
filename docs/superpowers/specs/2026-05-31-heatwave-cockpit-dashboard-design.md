# Heatwave Cockpit Dashboard — Design Spec

**Date:** 2026-05-31
**Status:** Design (approved IA + phasing; Phase 1 detailed, Phases 2–3 roadmap)
**Builds on:** the existing `training-dashboard/` (FastAPI + WS server, Vite/React web)

## 1. Problem & Goal

The current dashboard is an excellent **training monitor** but is *training-only*. Running
the rest of the heatwave system (build data, GEFS pull, daily forecast, evaluate, deploy,
inspect predictions) means dropping to the shell and running scripts by hand. The user
wants the dashboard to become a **single cockpit that controls the whole system**.

Goal: extend (not rewrite) the dashboard into a **5-tab cockpit** covering the four
directions the user selected — pipeline control, forecast visualization, production/ops,
and deeper experimentation — while leaving the existing Train experience untouched.

## 2. Scope

In scope — five tabs (top-tab navigation, chosen over sidebar/scroll):

| # | Tab | New? | Phase | Purpose |
|---|-----|------|-------|---------|
| ① | **Pipeline** | new | 1 | Run each stage (build data / GEFS / train / forecast / deploy) with live progress |
| ② | **Train** | existing | — | The current dashboard, moved verbatim into a tab |
| ③ | **Forecast** | new | 2 | 77-province risk map, per-province time-series, predicted-vs-observed |
| ④ | **Ops** | new | 3 | Promote model → production, daily-runner status, LINE/Supabase health, drift |
| ⑤ | **Lab** | new | 1 | Live GEFS-pull monitor, run `train_p0` + read A-vs-B P0 lift, ablation, rolling-CV |

**Non-goals (YAGNI):** user accounts / multi-tenant, cloud cost tracking, Bayesian HP
search, SHAP per-prediction explainers, alerting/paging, mobile layout (this is a
local single-user operator cockpit; the public surface is the existing HeatMAP app + LINE).

## 3. Architecture

### 3.1 Frontend — top-tab shell wrapping existing components

```
App.tsx
 ├─ <Header> (brand + connection dot)              ← exists, keep
 ├─ <TabBar tabs=[Pipeline,Train,Forecast,Ops,Lab] active=…/>   ← NEW
 └─ <main> renders the active tab:
      Pipeline → <PipelinePanel/>        (NEW)
      Train    → <TrainTab/>             ← today's App body, extracted unchanged
      Forecast → <ForecastPanel/>        (NEW, phase 2)
      Ops      → <OpsPanel/>             (NEW, phase 3)
      Lab      → <LabPanel/>             (NEW)
```

- **Refactor step (Phase 1, mechanical):** extract today's `App.tsx` body (Controls,
  Progress, Speed/Metrics, saved banner, Log, Leaderboard, RunHistory, ModelReport) into
  `<TrainTab/>` with **zero behavioral change**. `App.tsx` becomes shell + tab router.
- Tab state in `App.tsx` (`useState`, URL hash `#pipeline|#train|…` for deep-link/refresh).
- The single WebSocket connection stays app-level and is shared by all tabs (so a job
  started in Pipeline keeps streaming even while viewing another tab).
- Keep the existing theme, fonts, and hand-built SVG charts — no new UI/chart library.

### 3.2 Backend — generalize the runner from "Trainer" to "Job"

Today `Runner` runs one `Trainer` at a time and streams `progress_cb(step,total,msg)` over
WS. The cockpit needs to run non-trainer work (pipeline scripts) through the same live
pipe. Generalize:

- Introduce a **`Job` protocol** = the current Trainer contract exactly:
  `name: str`, `run(config, progress_cb, should_stop) -> dict`. Existing trainers ARE jobs
  (rename base, keep behavior). The runner, WS protocol, ETA/speed, and single-worker lock
  are **unchanged** — they already speak `(step,total,msg)`.
- New job kind **`StageJob`** wraps a pipeline entry-point as a **subprocess** and turns its
  stdout into events: each line → `LogEvent`; lines matching a stage's progress regex →
  `progress_cb`. Cooperative stop = terminate the child on `should_stop()`.
  - `build_dataset` (StageJob → `python -m pipeline.build_dataset`)
  - `build_gefs_store` (StageJob; progress from `checkpoint @ N/124` lines)
  - `run_daily_forecast` (StageJob → `scripts/run_daily_forecast.py`; progress from its
    per-province counter)
  - `train_p0` (StageJob → `scripts/train_p0.py`; result parsed from its A/B summary line)
- **Concurrency rule:** the runner stays **single-slot for interactive jobs** (train, a
  stage run, train_p0) — one at a time, exactly as today (avoids CPU thrash on one box).
- **Long detached jobs (the multi-hour GEFS pull) are the exception:** started as a
  **detached OS process** (not the single slot), tracked by a **read-only monitor** that
  polls the store/log. This lets the GEFS pull run for hours while the operator trains or
  browses other tabs. (Mirrors how the pull is run today.)

### 3.3 Selecting a tab does not change server state
All tabs read from the same server. New read endpoints are pure GETs; only explicit buttons
(Run stage, Promote) mutate. State the operator can break (Promote to production) is gated
behind a typed confirmation.

## 4. Phase 1 — Pipeline + Lab (the detailed, implementable slice)

Chosen first because it (a) matches the live GEFS/P0 work, (b) reuses the runner/WS infra
almost entirely, so it ships fast and de-risks the Job generalization.

### 4.1 Pipeline tab (`<PipelinePanel/>`)

A horizontal **flow of stage cards** in pipeline order, each with a status lamp and a Run
button; the **shared Progress/Log** area below shows the active stage live.

```
[① Data ●]──[② Train ●]──[③ Forecast ○]──[④ Deploy ○]
   Build        (link to            Run daily        (link to
   dataset /    Train tab)          forecast         Ops tab)
   GEFS pull
─────────────────────────────────────────────────────────
 <ProgressBar/> + <Eta/> + <LogPanel/>   (reused as-is)
```

- **Stage cards** (`<StageCard kind status lastRun onRun/>`): lamp = idle/running/done/error;
  shows last-run time + key result (e.g. "dataset 281k rows, 2016–2025"). Data stage groups
  two actions: **Build dataset** and **GEFS pull** (the latter is detached → its lamp reflects
  the monitor, see Lab).
- **Wiring:** Run → `StartCommand{kind:"stage", name}` over the existing WS. Server starts the
  matching `StageJob`; progress/log stream through the unchanged pipe. Done → `MetricsEvent`
  with the stage's summary dict.
- Stages that already have rich tabs (Train, Deploy) show a compact summary + a "open tab"
  link rather than duplicating UI.

### 4.2 Lab tab (`<LabPanel/>`)

Two stacked cards.

**(a) GEFS pull monitor** — read-only, polls `GET /api/gefs/status`:
- `inits N/124`, by-year coverage, `fc_spfh %`, last checkpoint time, running? (detached pid
  alive), tail of the build log. A **Start/Resume pull** button launches the detached job
  (idempotent — resumes via the store's `done` set); a **Stop** button signals it.
- progress bar derived from `N/target` (target from the requested years).

**(b) P0 experiment** — run `train_p0` as a StageJob, render the result:
- Button **Run P0 measurement**; streams log; on completion shows a small table
  **A antecedent vs B + GEFS forecast** with `ROC`, `PR-AUC lift`, and the **decision gate**
  banner: *"A recovered to ≥0.60?"* → green (lift meaningful), amber (honest null), red
  (eval structurally broken — pivot). This encodes the stop-condition from
  `docs/MODEL-IMPROVEMENT.md` directly in the UI.
- History of P0 runs (origin years, matched rows, pos_rate, A/B numbers) appended to a small
  JSONL so runs are comparable over time.
- *(Later in Lab: ablation toggles for candidate antecedent features, rolling-CV launcher.
  Sketched, not Phase 1.)*

### 4.3 Phase 1 server additions

| Endpoint | Method | Returns |
|---|---|---|
| `GET /api/gefs/status` | GET | `{inits, target, by_year, fc_spfh_pct, last_checkpoint, running, log_tail}` |
| `POST /api/gefs/start` | POST | start/resume detached pull `{years?}` → `{pid}` |
| `POST /api/gefs/stop` | POST | stop detached pull |
| `GET /api/p0/runs` | GET | history of P0 measurements |
| WS `StartCommand` | — | extend with `kind: "trainer" \| "stage"` + `name` |

Stage registry (server) maps `name → (argv, progress_regex, summary_parser)`. New jobs are
table entries, not new endpoints.

## 5. Phases 2–3 — roadmap (own specs later)

**Phase 2 — Forecast tab.** Read forecast rows from Supabase `heatwave` schema (and/or
`forecast_store`). Start with a **77-province risk grid** (colored cells per province ×
lead 1–7, like HeatMAP's MapGrid — no geometry needed), click a cell → per-province
**probability + sWBGT time-series**; add **predicted-vs-observed** backtest once a model is
promoted. Upgrade to a true GeoJSON choropleth as 2b. New GETs: `/api/forecast/map`,
`/api/forecast/province/{id}`.

**Phase 3 — Ops tab.** **Promote** dashboard model → `models/heatwave_model.pkl` (copy +
sidecar provenance) behind a typed confirm; **daily-runner status** (last run, provinces
ok/failed, next schedule); **LINE OA / Supabase write health**; simple **drift** view
(recent forecast base-rate vs training). Promotion is a local file copy the operator
triggers — no auto-deploy/push.

## 6. Testing

- **Frontend:** keep existing Vitest tests green after the `TrainTab` extraction (proves no
  regression). New: `TabBar` routing, `StageCard` lamp states, P0 result-gate rendering,
  GEFS-status formatting. React Testing Library, no network.
- **Server:** `StageJob` stdout→event mapping (feed canned stdout, assert log/progress
  events + parsed summary); `/api/gefs/status` parsing from a fixture store+log;
  stage-registry table. Reuse the existing `server/tests` harness.
- **No live network or GEFS download in tests** — fixtures only.

## 7. Risks & constraints

- **GEFS archive ends 2019** — P0 measurement is bounded to cool origin years 2016–2019;
  the Lab gate must frame results honestly (already encoded).
- **Province geometry** for a true map is not in-repo → Phase 2 starts grid-based to avoid a
  blocker; geo-choropleth is an enhancement needing a Thailand province GeoJSON.
- **Single-slot runner** means a foreground stage and a training run can't overlap — by
  design; the only concurrent thing is the detached GEFS pull (I/O-bound).
- **Promote safety** — production cutover is gated behind explicit typed confirmation; the
  dashboard never auto-promotes, auto-deploys, or pushes.
- **Subprocess stage jobs** must stream stdout unbuffered (`-u`) and be killed cleanly on
  stop to avoid orphans.

## 8. Build order (Phase 1)

1. Extract `TrainTab` + add `TabBar`/tab router (mechanical; existing tests stay green).
2. Generalize `Trainer` → `Job`; add `StageJob` + stage registry; extend `StartCommand` kind.
3. Pipeline tab: stage cards wired to StageJobs (build_dataset, train, forecast links).
4. Lab tab: GEFS monitor (`/api/gefs/*` + detached launcher) and P0 runner + result gate.
5. Tests for all of the above; manual smoke with the *running* GEFS pull as live data.
