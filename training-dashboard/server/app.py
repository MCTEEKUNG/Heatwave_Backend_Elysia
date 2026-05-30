"""FastAPI + WebSocket control server for the Heatwave Training Dashboard.

Run from the REPO ROOT so ``pipeline`` and ``src`` import correctly::

    .venv\\Scripts\\python.exe -m uvicorn server.app:app \\
        --app-dir training-dashboard --host 127.0.0.1 --port 8000

WebSocket endpoint: ws://127.0.0.1:8000/ws
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from typing import Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import protocol
from .runner import Runner
from .trainers import available as available_trainers

app = FastAPI(title="Heatwave Training Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    """Tracks active WebSocket connections and fans out events to all of them."""

    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def accept(self, ws: WebSocket) -> None:
        await ws.accept()

    async def register(self, ws: WebSocket, snapshot_fn) -> bool:
        """Atomically send the current snapshot, then start receiving broadcasts.

        Holding ``lock`` across both steps (and capturing the snapshot *inside*
        the lock) guarantees the new client's first frame is its snapshot and
        that it can never receive a broadcast that precedes it -- closing the
        connect/replay race. Returns False if the socket is already dead.
        """
        async with self.lock:
            try:
                await ws.send_text(json.dumps(snapshot_fn()))
            except Exception:
                return False
            self.active.add(ws)
            return True

    async def disconnect(self, ws: WebSocket) -> None:
        async with self.lock:
            self.active.discard(ws)

    async def send_one(self, ws: WebSocket, event: dict) -> None:
        await ws.send_text(json.dumps(event))

    async def broadcast(self, event: dict) -> None:
        text = json.dumps(event)
        # Hold the lock across the whole send loop so concurrent broadcasts
        # (each scheduled as its own task from the worker thread) are serialized
        # and frame order is preserved. Dead sockets are dropped inline -- we
        # must NOT call self.disconnect() here, as it would re-acquire this lock
        # and deadlock.
        async with self.lock:
            dead = []
            for ws in list(self.active):
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active.discard(ws)


manager = ConnectionManager()
runner = Runner()

# Captured at startup so the worker thread can schedule coroutines on it.
_loop: Optional[asyncio.AbstractEventLoop] = None


@app.on_event("startup")
async def _on_startup() -> None:
    global _loop
    _loop = asyncio.get_running_loop()

    def _broadcast_from_thread(event: dict) -> None:
        # Called from the runner's worker thread -> hop onto the event loop.
        loop = _loop
        if loop is None:
            return
        asyncio.run_coroutine_threadsafe(manager.broadcast(event), loop)

    runner.broadcast = _broadcast_from_thread


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "running": runner.is_running}


# Path is relative to the repo root (the server's working directory), where
# scripts/bakeoff.py writes the model-comparison leaderboard.
LEADERBOARD_PATH = "experiments/results/leaderboard.json"


MODEL_REPORT_PATH = "experiments/results/model_report.json"
MODEL_CARD_PATH = "models/model_card.json"


def _read_json_artifact(path: str, empty: dict) -> dict:
    if not os.path.exists(path):
        return {"available": False, **empty}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["available"] = True
        return data
    except Exception as exc:  # noqa: BLE001 -- never 500 the dashboard
        return {"available": False, "error": str(exc), **empty}


@app.get("/api/leaderboard")
async def leaderboard() -> dict:
    """Return the latest bake-off leaderboard, or available=False if none yet."""
    return _read_json_artifact(LEADERBOARD_PATH, {"results": []})


@app.get("/api/model-report")
async def model_report() -> dict:
    """Return the production-model deep-dive report, or available=False if none."""
    return _read_json_artifact(MODEL_REPORT_PATH, {})


@app.get("/api/model-card")
async def model_card() -> dict:
    """Return the trained-artifact provenance card, or available=False if none."""
    return _read_json_artifact(MODEL_CARD_PATH, {})


# Trainers whose dashboard runs persist a downloadable .pkl (everything except
# the synthetic 'simulated' trainer). Used as a strict whitelist below.
_SAVABLE_TRAINERS = set(available_trainers()) - {"simulated"}


@app.get("/api/model-file/{name}")
async def model_file(name: str):
    """Download a dashboard-trained model bundle (models/dashboard/<name>.pkl).

    ``name`` is validated against a fixed whitelist of trainer names -- the
    request string is never interpolated into a filesystem path.
    """
    if name not in _SAVABLE_TRAINERS:
        raise HTTPException(status_code=404, detail="unknown model")
    path = os.path.join("models", "dashboard", f"{name}.pkl")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="not trained yet -- run it from the dashboard first")
    return FileResponse(path, media_type="application/octet-stream",
                        filename=f"heatwave-{name}.pkl")


@app.post("/api/reveal-models")
async def reveal_models() -> dict:
    """Open the dashboard models folder in the OS file explorer.

    Local dev convenience: the server IS the user's machine. The path is FIXED
    (models/dashboard) -- never taken from the request -- so there is no path or
    command injection surface.
    """
    folder = os.path.abspath(os.path.join("models", "dashboard"))
    os.makedirs(folder, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(folder)  # noqa: S606 -- fixed local path, Windows explorer
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return {"opened": folder}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"could not open folder: {exc}")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await manager.accept(ws)
    # Atomically send the last known status (idle initially) and join the
    # broadcast set; bail if the socket died before we could greet it.
    if not await manager.register(ws, runner.last_status):
        return

    try:
        while True:
            raw = await ws.receive_text()
            await _handle_message(ws, raw)
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)


async def _handle_message(ws: WebSocket, raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await manager.send_one(ws, protocol.error_event("invalid JSON"))
        return

    try:
        command = protocol.parse_command(data)
    except Exception as exc:  # noqa: BLE001
        await manager.send_one(ws, protocol.error_event(str(exc)))
        return

    if isinstance(command, protocol.StartCommand):
        config = command.config.model_dump() if command.config else {}
        # runner.start handles the single-run lock + warn log itself.
        runner.start(command.trainer, config)
    elif isinstance(command, protocol.StopCommand):
        runner.stop()
