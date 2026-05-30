# Heatwave Training Dashboard — Server

Dev-only FastAPI + WebSocket control server for driving training runs.

WebSocket endpoint: `ws://127.0.0.1:8000/ws`

## Install (into the existing repo venv)

Run from the repo root (`C:\Users\ASUS\Heatwave_AI`):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run the server

The folder name `training-dashboard` has a hyphen (not a valid Python module),
so the server is launched **from the repo root** with uvicorn's `--app-dir`
adding the hyphenated folder to `sys.path`. This also keeps `pipeline` and `src`
importable (they live at the repo root, which is the cwd):

```powershell
.venv\Scripts\python.exe -m uvicorn server.app:app --app-dir training-dashboard --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/healthz`

## Run the tests

From the repo root:

```powershell
.venv\Scripts\python.exe -m pytest training-dashboard/server/tests -q
```

## Protocol (summary)

Client → server (JSON text frames):

```json
{ "command": "start", "trainer": "simulated", "config": { "total_steps": 10000, "speed_per_sec": 100 } }
{ "command": "stop" }
```

Server → client event `type`s: `status`, `log`, `metrics`, `error`.
See `protocol.py` for the exact field set. CORS allows the Vite dev origins
`http://localhost:5173` and `http://127.0.0.1:5173`.

## Trainers

- `simulated` — a timed fake loop (`total_steps`, `speed_per_sec`).
- `lgbm` — the real pipeline; reads `data/processed/dataset.parquet` and runs
  `pipeline.train.train_model`, reporting one progress tick per boosting round.
  If the dataset is missing it raises a friendly `FileNotFoundError`.
