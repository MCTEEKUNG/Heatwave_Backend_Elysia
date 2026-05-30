# Heatwave Training Dashboard (dev-only)

A small real-time dashboard to launch and monitor Heatwave model training:
progress bar, ETA, live speed sparkline, streaming log, final metrics, and
Start/Stop controls. It is a **developer/ops tool** — it is not shipped to end
users and is intentionally separate from the Elysia product backend and the
Expo app.

Design spec: [`docs/superpowers/specs/2026-05-30-training-dashboard-design.md`](../docs/superpowers/specs/2026-05-30-training-dashboard-design.md)

```
training-dashboard/
  server/   FastAPI + WebSocket control server (Python)   -> 127.0.0.1:8000  /ws
  web/      Vite + React + TS dashboard (bun)              -> 127.0.0.1:5173
  e2e_ws_check.py        live protocol integration check (1 client)
  multiclient_check.py   live broadcast check (2 clients)
```

## Quick start

Two terminals, both from the **repo root** (`C:\Users\ASUS\Heatwave_AI`).

**1. Server** (uses the existing `.venv`; install dev deps once):
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn server.app:app --app-dir training-dashboard --host 127.0.0.1 --port 8000
```

**2. Web** (uses bun):
```powershell
cd training-dashboard\web
bun install
bun run dev
```

Open http://127.0.0.1:5173 and click **Start**. With the default `simulated`
trainer it runs immediately — no training data required.

## Trainers

- **simulated** (default) — a synthetic loop; works with no data, good for
  trying the dashboard and for fast/deterministic tests.
- **lgbm** — the real pipeline (`pipeline/train.py`). Requires
  `data/processed/dataset.parquet`; until that exists it reports a friendly
  "dataset not found" error instead of crashing. Progress is reported per
  LightGBM boosting round. Stop is cooperative (no pause/resume — LightGBM
  cannot pause a fit).

## Tests & checks

```powershell
# Server unit tests
.\.venv\Scripts\python.exe -m pytest training-dashboard/server/tests -q

# Web unit tests
cd training-dashboard\web; bunx vitest run

# Live integration (server must be running on :8000)
.\.venv\Scripts\python.exe training-dashboard\e2e_ws_check.py
.\.venv\Scripts\python.exe training-dashboard\multiclient_check.py
```

## How it works

The browser opens a WebSocket to the server. On `start`, the server runs the
selected trainer in a worker thread; the trainer reports progress via a
callback, which the runner turns into `status`/`log`/`metrics` events and
broadcasts to every connected dashboard. The wire protocol (one schema shared
by both trainers) is defined in `server/protocol.py` and mirrored in
`web/src/protocol.ts`.

## Extending (Phase 2)

A future long, epoch-based training loop can plug in by implementing the same
`Trainer.run(config, progress_cb, should_stop)` contract in
`server/trainers/`. Because it reuses the existing event protocol, it
automatically gets the progress bar, ETA, speed chart, and log. A genuinely
pausable loop could then add Pause/resume (reserved in the protocol), and
"training finished" notifications could reuse the repo's existing LINE bot.
