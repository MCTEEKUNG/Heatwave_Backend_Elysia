"""Single-worker training runner.

Owns ONE worker thread at a time. Converts raw ``progress_cb(step, total, msg)``
calls from a trainer into ``status`` events carrying computed EWMA speed + eta,
throttled to ~once/second. Maintains a cooperative stop flag, a single-run lock,
the last status (for replay to newly-connected clients), and a synchronous
``broadcast`` hook the app installs.

The runner is deliberately event-loop-agnostic: it only ever calls a plain
synchronous ``broadcast(event: dict)``. The app bridges that into asyncio; tests
install a list-appender. This keeps every runner test fully synchronous and
deterministic.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from . import protocol
from .jobs import resolve_job

EWMA_ALPHA = 0.3

Broadcast = Callable[[dict], None]


class EwmaSpeed:
    """Exponentially-weighted moving average of steps/sec (alpha=0.3).

    Seeding convention: the first sample sets ``ewma = sample`` directly; every
    later sample folds in as ``ewma = alpha*sample + (1-alpha)*ewma``.
    """

    def __init__(self, alpha: float = EWMA_ALPHA):
        self.alpha = alpha
        self.value: float = 0.0
        self._last_step: Optional[int] = None
        self._last_time: Optional[float] = None
        self._seeded = False

    def update(self, step: int, now: float) -> float:
        """Record a (step, time) sample; return the current ewma speed."""
        if self._last_step is not None and self._last_time is not None:
            dt = now - self._last_time
            dstep = step - self._last_step
            if dt > 0 and dstep >= 0:
                sample = dstep / dt
                if not self._seeded:
                    self.value = sample
                    self._seeded = True
                else:
                    self.value = self.alpha * sample + (1 - self.alpha) * self.value
        self._last_step = step
        self._last_time = now
        return self.value

    def eta_seconds(self, step: int, total: int) -> Optional[int]:
        """eta = round((total-step)/ewma); None when ewma == 0."""
        if self.value <= 0:
            return None
        remaining = max(0, total - step)
        return int(round(remaining / self.value))


class Runner:
    def __init__(self, broadcast: Optional[Broadcast] = None,
                 status_interval: float = 1.0):
        # broadcast(event_dict) -- installed by the app; defaults to no-op.
        self.broadcast: Broadcast = broadcast or (lambda event: None)
        self.status_interval = status_interval

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._running = False

        self._last_status: dict = protocol.status_event(
            "idle", message="idle", ts=time.time()
        )

    # -- state helpers ----------------------------------------------------- #
    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def last_status(self) -> dict:
        with self._lock:
            return dict(self._last_status)

    def _emit(self, event: dict) -> None:
        if event.get("type") == "status":
            with self._lock:
                self._last_status = dict(event)
        try:
            self.broadcast(event)
        except Exception:
            # Broadcasting must never take down the worker.
            pass

    def should_stop(self) -> bool:
        return self._stop_flag.is_set()

    # -- public API -------------------------------------------------------- #
    def start(self, name: str, config: Optional[dict] = None,
              kind: str = "trainer") -> bool:
        """Start a run. Returns False (and emits a warn log) if already running."""
        with self._lock:
            if self._running:
                already = True
            else:
                already = False
                self._running = True
                self._stop_flag.clear()
        if already:
            self._emit(protocol.log_event(
                "a run is already in progress", level="warn"))
            return False

        self._thread = threading.Thread(
            target=self._run, args=(name, config or {}, kind), daemon=True)
        try:
            self._thread.start()
        except Exception:
            # Thread creation can fail under resource exhaustion; don't leave
            # the runner permanently wedged with _running == True.
            with self._lock:
                self._running = False
            self._emit(protocol.error_event("failed to start training thread"))
            return False
        return True

    def stop(self) -> None:
        """Request a cooperative halt of the current run."""
        self._stop_flag.set()

    def join(self, timeout: Optional[float] = None) -> None:
        t = self._thread
        if t is not None:
            t.join(timeout)

    # -- worker ------------------------------------------------------------ #
    def _run(self, name: str, config: dict, kind: str) -> None:
        ewma = EwmaSpeed()
        last_emit = 0.0
        last_log_msg = None
        state = {"step": 0, "total": 0}

        def progress_cb(step: int, total: int, message: str) -> None:
            nonlocal last_emit, last_log_msg
            state["step"], state["total"] = step, total
            now = time.time()
            speed = ewma.update(step, now)
            # Interim log events: throttle to ~status_interval so a per-step
            # message stream becomes a few human-readable log lines, and never
            # repeat the identical line back-to-back.
            if message and message != last_log_msg and (
                now - last_emit >= self.status_interval or last_emit == 0.0
            ):
                last_log_msg = message
                self._emit(protocol.log_event(message, level="info"))
            # Throttle status emission to ~status_interval, but always emit the
            # very first sample so clients see movement immediately.
            if now - last_emit >= self.status_interval or last_emit == 0.0:
                last_emit = now
                progress = 100.0 * step / total if total else 0.0
                self._emit(protocol.status_event(
                    "running",
                    progress=progress,
                    step=step,
                    total_steps=total,
                    speed_per_sec=speed,
                    eta_seconds=ewma.eta_seconds(step, total),
                    message=message,
                    ts=now,
                ))

        try:
            self._emit(protocol.log_event(
                f"starting {name} ({kind})", level="info"))
            job = resolve_job(name, kind)
            if kind == "stage":
                report = job.run(config, progress_cb, self.should_stop,
                                 log_cb=lambda lvl, m: self._emit(protocol.log_event(m, level=lvl)))
            else:
                report = job.run(config, progress_cb, self.should_stop)

            if self._stop_flag.is_set():
                # Cooperative stop -> back to idle.
                self._emit(protocol.status_event(
                    "idle", message="stopped", ts=time.time()))
                self._emit(protocol.log_event("run stopped", level="warn"))
            else:
                total = state["total"] or 0
                self._emit(protocol.status_event(
                    "done",
                    progress=100.0,
                    step=state["step"],
                    total_steps=total,
                    speed_per_sec=ewma.value,
                    eta_seconds=0,
                    message="done",
                    ts=time.time(),
                ))
                self._emit(protocol.metrics_event(report or {}))
                self._emit(protocol.log_event("run complete", level="info"))
        except Exception as exc:  # noqa: BLE001 -- server must not crash
            msg = f"{type(exc).__name__}: {exc}"
            self._emit(protocol.error_event(msg))
            self._emit(protocol.status_event(
                "error", message=msg, ts=time.time()))
        finally:
            # Clear the stop flag under the same lock that flips _running, so a
            # stop() racing with the next start() can't be silently discarded.
            with self._lock:
                self._running = False
                self._stop_flag.clear()
