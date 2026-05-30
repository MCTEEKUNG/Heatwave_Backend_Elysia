# Heatwave Training Dashboard — Design

**Date:** 2026-05-30
**Status:** Approved (design); pending implementation plan
**Scope:** A dev-only, real-time dashboard to launch and monitor Heatwave model
training, with a progress bar, ETA, live speed chart, log stream, final metrics,
and Start/Stop controls.

---

## 1. Motivation & reality check

The original proposal assumed a long, step-based training loop (10,000 steps,
Start/Pause/Stop, ETA recomputed per second) on a FastAPI + plain-React-web +
Redis stack. Two mismatches with the actual repo drove this design:

1. **Training is a short batch job, not a pausable loop.** `pipeline/train.py`
   loads `data/processed/dataset.parquet`, runs a single LightGBM `.fit()`,
   calibrates, tunes an F2 threshold, evaluates on a held-out year, and saves
   `models/heatwave_model.pkl`. It finishes in seconds-to-minutes. LightGBM /
   sklearn cannot be paused/resumed mid-fit. **However**, LightGBM supports
   per-round callbacks, so a real progress bar and rough ETA over
   `num_boost_round` are achievable; only pause/resume is not.

2. **Stack mismatch.** The product backend is **Elysia + Bun** (`src/index.ts`),
   the app is **Expo / React Native** (`HeatMAP-Frontend`), and persistence is
   **Supabase Postgres**. Building the proposal verbatim would add a second,
   conflicting stack.

**Chosen direction (user-approved):** "Start small, design for growth." Build a
general training monitor that works for the current short LightGBM job now, and
is structured so a future long training loop plugs into the same event protocol
and gains the full controls later.

**Current data state:** there is no `data/processed/dataset.parquet` yet, so the
real trainer cannot run today. A **simulated trainer** is therefore the default,
making the dashboard demoable immediately; the real LightGBM trainer is wired
behind the same protocol for when data exists.

---

## 2. Architecture

Three parts — two new (dev-only, not shipped to end users), one tiny
backward-compatible hook into existing training code.

```
training-dashboard/                 # new, dev-only
  server/                           # FastAPI + WebSocket control server (localhost:8000)
    app.py                          # WS /ws: accept commands, broadcast events, single-run lock
    runner.py                       # runs a trainer in a worker thread; computes speed/ETA; broadcasts
    protocol.py                     # pydantic command/event schema (one schema, both phases)
    trainers/
      __init__.py                   # registry: name -> trainer factory
      base.py                       # Trainer interface + cooperative-cancel contract
      simulated.py                  # 10k-step fake loop — DEFAULT, works with no data
      lgbm.py                       # wraps pipeline.train.train_model + LightGBM per-round callback
  web/                              # Vite + React dashboard (localhost:5173)
    src/
      ws.ts                         # WebSocket client + auto-reconnect + event reducer
      App.tsx                       # layout
      components/ProgressBar.tsx
      components/SpeedChart.tsx
      components/Eta.tsx
      components/LogPanel.tsx
      components/Controls.tsx       # trainer selector + Start/Stop
      components/Toast.tsx

src/model.py                        # add OPTIONAL progress_cb kwarg (default None = unchanged)
pipeline/train.py                   # thread progress_cb through train_model (default None = unchanged)
requirements-dev.txt                # fastapi, uvicorn[standard], pytest (installed into existing .venv)
```

The FastAPI server is a **dev-only training-ops server**, deliberately separate
from the Elysia product backend. This is the correct boundary because training
is Python; it is not a rewrite of the product API.

---

## 3. Event protocol

One schema serves both trainers and both phases. Defined with pydantic in
`server/protocol.py`; the web client mirrors the types in `ws.ts`.

**Client → server (commands):**
```json
{ "command": "start", "trainer": "simulated", "config": { "total_steps": 10000, "speed": 100 } }
{ "command": "stop" }
```

**Server → client (events):**
```json
{ "type": "status", "state": "idle|running|done|error",
  "progress": 62.0, "step": 6200, "total_steps": 10000,
  "speed_per_sec": 105.3, "eta_seconds": 108, "message": "...", "ts": 1234567890.0 }

{ "type": "log",     "level": "info|warn|error", "message": "round 120 val-F2 0.71", "ts": ... }
{ "type": "metrics", "report": { "threshold": 0.31, "test": { ... }, "baseline_constant": { ... } } }
{ "type": "error",   "message": "dataset not found: data/processed/dataset.parquet" }
```

**ETA:** `eta_seconds = (total_steps - step) / ewma_speed`, where `ewma_speed`
is an exponentially-weighted moving average of steps/sec (smoothing factor
~0.3). This avoids the jumpy raw-average ETA in the original sample. If
`ewma_speed == 0`, `eta_seconds = null`.

---

## 4. Components & responsibilities

| Unit | Does | Depends on |
|------|------|-----------|
| `protocol.py` | Typed commands/events; validation | pydantic |
| `trainers/base.py` | `Trainer` interface: `run(config, progress_cb, should_stop)`; cooperative cancel via `should_stop()` checked each step | — |
| `trainers/simulated.py` | Sleeps per step, emits progress; honors `should_stop` | base |
| `trainers/lgbm.py` | Calls `pipeline.train.train_model` with a LightGBM callback over `num_boost_round`; raises to abort when `should_stop`; returns the real report | base, pipeline.train |
| `runner.py` | Owns the single worker thread; turns raw `progress_cb` calls into `status` events with computed EWMA speed/ETA; catches exceptions → `error`; enforces single-run lock; keeps last status for replay | trainers, protocol |
| `app.py` | FastAPI app; `/ws` endpoint; routes commands to runner; broadcasts events to all connected clients | runner, protocol |
| `ws.ts` | Connects, auto-reconnects with backoff, reduces events into UI state | — |
| React components | Render progress/eta/speed/log/metrics; emit start/stop | ws.ts |

**Hook into existing code (minimal, backward-compatible):**
- `src/model.py::train(X, y, ..., progress_cb=None)` — when `progress_cb` is
  provided, pass a LightGBM `callbacks=[...]` that calls `progress_cb(step,
  total, message)` each boosting round. Default `None` → current behavior.
- `pipeline/train.py::train_model(dataset, ..., progress_cb=None)` — forwards
  `progress_cb` to `train_lgbm`. Default `None` → current behavior.

---

## 5. Data flow

```
[web] click Start ──ws──> [app.py] ──> [runner] spawn worker thread
                                            │
                              trainer.run(config, progress_cb, should_stop)
                                            │ progress_cb(step,total,msg) each step/round
                                            ▼
                              [runner] compute EWMA speed + ETA
                                            │ broadcast {type:status,...} (and {type:log})
                                            ▼
[web] ws.ts reducer ──> ProgressBar / Eta / SpeedChart / LogPanel update
                                            │
                              trainer finishes ──> broadcast {type:metrics, report}
                                            ▼
[web] show metrics panel + Toast("Training complete")
```

Stop: `stop` command sets the runner's stop flag; the trainer observes it via
`should_stop()` (simulated) or an aborting LightGBM callback (lgbm), exits,
runner broadcasts `state:"idle"`.

---

## 6. Controls (honest to the technology)

- **Start** — launches the selected trainer in the worker thread.
- **Stop** — cooperative cancel (true halt, not pause).
- **Pause — omitted in Phase 1.** LightGBM cannot pause a fit. The protocol
  reserves room for it; a Phase 2 long loop that checkpoints can implement it.

---

## 7. Error handling

- Trainer exceptions are caught in `runner.py` → `error` event + `state:"error"`;
  the server never crashes.
- Missing `data/processed/dataset.parquet` (lgbm trainer) → a friendly `error`
  event ("dataset not found; run build_dataset first"), not a stack trace.
- WebSocket disconnect → the dashboard auto-reconnects with backoff; the server
  replays the last known `status` on reconnect.
- Single-run lock → a `start` while already running is rejected with a `log`
  warning; no second thread is spawned.

---

## 8. Notifications (YAGNI)

Phase 1: in-dashboard toast + an optional browser `Notification` on done/error.
Email and LINE push are deferred — the repo already has a LINE bot
(`src/line/`), so a "training finished" push is trivial to add in Phase 2.

---

## 9. Testing

- **server (pytest):** protocol schema round-trips; runner emits monotonically
  non-decreasing progress; EWMA-ETA math; stop flag halts the simulated trainer
  promptly; lgbm trainer emits a clean error when the dataset is absent. The
  simulated trainer keeps these fast and deterministic.
- **web (vitest):** the `ws.ts` event reducer (status/log/metrics/error → UI
  state) and ETA formatting (`108 → "1 m 48 s"`). Intentionally light.

---

## 10. Phasing

- **Phase 1 (now):** simulated + lgbm trainers; Start/Stop; progress, ETA,
  speed chart, log, final metrics, toast. Works today via the simulated trainer;
  lgbm trainer errors gracefully until `dataset.parquet` exists.
- **Phase 2 (later):** a long epoch-based training loop implements the same
  `progress_cb` contract → gains Pause/resume + checkpointing; optional
  LINE/email notify; optional Postgres run-history for past runs.

---

## 11. Decisions locked

- Standalone Vite + React dashboard (not inside the Expo product app).
- FastAPI + WebSocket dev-only control server (training is Python, observer is Python).
- In-process training in a worker thread (enables the LightGBM callback); cooperative-cancel Stop.
- Simulated trainer is the default so the dashboard runs before real data exists.
- Reuse the existing `.venv`; add `fastapi`/`uvicorn`/`pytest` via `requirements-dev.txt`.
- One pydantic event protocol shared by both trainers and both phases.
- Pause and email/LINE notifications are explicitly deferred to Phase 2 (YAGNI).
