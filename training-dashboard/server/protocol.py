"""Frozen wire protocol for the Heatwave Training Dashboard.

Pydantic models for the client->server commands and each server->client event,
plus tiny helpers to build event dicts that serialize to the EXACT JSON the web
client is coded against. Field names here are part of the frozen contract -- do
not rename them.
"""
from __future__ import annotations

import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Client -> server commands
# --------------------------------------------------------------------------- #
class StartConfig(BaseModel):
    """Optional ``config`` block of a ``start`` command."""

    total_steps: int = 10000
    speed_per_sec: float = 100.0


class StartCommand(BaseModel):
    command: Literal["start"]
    # Any registered trainer name; the registry (server/trainers) is the source
    # of truth and raises a friendly error for unknown names.
    trainer: str
    config: Optional[StartConfig] = None


class StopCommand(BaseModel):
    command: Literal["stop"]


def parse_command(data: dict) -> BaseModel:
    """Parse a raw decoded JSON dict into the matching command model.

    Raises ``ValueError`` (with a friendly message) if it does not match.
    """
    cmd = data.get("command") if isinstance(data, dict) else None
    if cmd == "start":
        return StartCommand(**data)
    if cmd == "stop":
        return StopCommand(**data)
    raise ValueError(f"unknown command: {cmd!r}")


# --------------------------------------------------------------------------- #
# Server -> client events
# --------------------------------------------------------------------------- #
State = Literal["idle", "running", "done", "error"]


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    state: State
    progress: float = 0.0
    step: int = 0
    total_steps: int = 0
    speed_per_sec: float = 0.0
    eta_seconds: Optional[int] = None
    message: str = ""
    ts: float = Field(default_factory=time.time)


class LogEvent(BaseModel):
    type: Literal["log"] = "log"
    level: Literal["info", "warn", "error"] = "info"
    message: str = ""
    ts: float = Field(default_factory=time.time)


class MetricsEvent(BaseModel):
    type: Literal["metrics"] = "metrics"
    report: dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str = ""


# --------------------------------------------------------------------------- #
# Serialization helpers -- return plain JSON-able dicts
# --------------------------------------------------------------------------- #
def status_event(
    state: State,
    *,
    progress: float = 0.0,
    step: int = 0,
    total_steps: int = 0,
    speed_per_sec: float = 0.0,
    eta_seconds: Optional[int] = None,
    message: str = "",
    ts: Optional[float] = None,
) -> dict:
    return StatusEvent(
        state=state,
        progress=progress,
        step=step,
        total_steps=total_steps,
        speed_per_sec=speed_per_sec,
        eta_seconds=eta_seconds,
        message=message,
        ts=time.time() if ts is None else ts,
    ).model_dump()


def log_event(message: str, level: str = "info", ts: Optional[float] = None) -> dict:
    return LogEvent(
        level=level, message=message, ts=time.time() if ts is None else ts
    ).model_dump()


def metrics_event(report: dict) -> dict:
    return MetricsEvent(report=report).model_dump()


def error_event(message: str) -> dict:
    return ErrorEvent(message=message).model_dump()
