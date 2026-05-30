"""FastAPI + WebSocket control server for the Heatwave Training Dashboard.

Run from the REPO ROOT so ``pipeline`` and ``src`` import correctly::

    .venv\\Scripts\\python.exe -m uvicorn server.app:app \\
        --app-dir training-dashboard --host 127.0.0.1 --port 8000

WebSocket endpoint: ws://127.0.0.1:8000/ws
"""
from __future__ import annotations

import asyncio
import json
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

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self.lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self.lock:
            self.active.discard(ws)

    async def send_one(self, ws: WebSocket, event: dict) -> None:
        await ws.send_text(json.dumps(event))

    async def broadcast(self, event: dict) -> None:
        text = json.dumps(event)
        async with self.lock:
            targets = list(self.active)
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:
                # Drop dead sockets; cleanup happens on their own disconnect.
                await self.disconnect(ws)


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


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    # On connect, immediately send the last known status (idle initially).
    try:
        await manager.send_one(ws, runner.last_status())
    except Exception:
        await manager.disconnect(ws)
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
