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
from typing import Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import protocol
from .runner import Runner

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


@app.get("/api/leaderboard")
async def leaderboard() -> dict:
    """Return the latest bake-off leaderboard, or available=False if none yet."""
    if not os.path.exists(LEADERBOARD_PATH):
        return {"available": False, "results": []}
    try:
        with open(LEADERBOARD_PATH, encoding="utf-8") as f:
            data = json.load(f)
        data["available"] = True
        return data
    except Exception as exc:  # noqa: BLE001 -- never 500 the dashboard
        return {"available": False, "error": str(exc), "results": []}


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
