"""Runner behavior with the simulated trainer (synchronous, deterministic)."""
import threading
import time

import pytest

from server.runner import EwmaSpeed, Runner


def _collect():
    events = []
    lock = threading.Lock()

    def broadcast(ev):
        with lock:
            events.append(ev)

    return events, broadcast


def _wait_until_idle(runner, timeout=10.0):
    runner.join(timeout)
    deadline = time.time() + timeout
    while runner.is_running and time.time() < deadline:
        time.sleep(0.01)


# --------------------------------------------------------------------------- #
# EWMA / eta math
# --------------------------------------------------------------------------- #
def test_ewma_seeds_with_first_sample():
    e = EwmaSpeed(alpha=0.3)
    assert e.update(0, 0.0) == 0.0  # no prior sample yet
    # 100 steps in 1s -> first sample seeds directly to 100.
    assert e.update(100, 1.0) == pytest.approx(100.0)


def test_ewma_folds_subsequent_samples():
    e = EwmaSpeed(alpha=0.3)
    e.update(0, 0.0)
    e.update(100, 1.0)        # seed -> 100
    v = e.update(300, 2.0)    # sample = 200 -> 0.3*200 + 0.7*100 = 130
    assert v == pytest.approx(130.0)


def test_eta_seconds_math_and_null():
    e = EwmaSpeed(alpha=0.3)
    e.update(0, 0.0)
    e.update(100, 1.0)  # ewma = 100/s
    # remaining = 1000 - 100 = 900; 900/100 = 9
    assert e.eta_seconds(100, 1000) == 9
    # ewma == 0 -> null
    fresh = EwmaSpeed()
    assert fresh.eta_seconds(0, 100) is None


def test_eta_rounds():
    e = EwmaSpeed(alpha=0.3)
    e.update(0, 0.0)
    e.update(30, 1.0)  # 30/s
    # remaining 70 -> 70/30 = 2.333 -> round = 2
    assert e.eta_seconds(30, 100) == 2


# --------------------------------------------------------------------------- #
# Runner + simulated trainer
# --------------------------------------------------------------------------- #
def test_simulated_run_progress_monotonic_and_completes():
    events, broadcast = _collect()
    runner = Runner(broadcast=broadcast, status_interval=0.02)
    runner.start("simulated", {"total_steps": 200, "speed_per_sec": 5000})
    _wait_until_idle(runner)

    statuses = [e for e in events if e["type"] == "status"]
    running = [e for e in statuses if e["state"] == "running"]
    assert len(running) >= 2, "expected multiple running status samples"

    progresses = [e["progress"] for e in running]
    assert progresses == sorted(progresses), "progress must be non-decreasing"
    steps = [e["step"] for e in running]
    assert steps == sorted(steps), "step must be non-decreasing"
    assert all(0.0 <= p <= 100.0 for p in progresses)

    # Completion: a done status (progress 100) THEN a metrics event.
    types = [e["type"] for e in events]
    done = next(e for e in statuses if e["state"] == "done")
    assert done["progress"] == 100.0
    done_idx = events.index(done)
    metrics_idx = next(i for i, e in enumerate(events) if e["type"] == "metrics")
    assert metrics_idx > done_idx
    assert events[metrics_idx]["report"]["trainer"] == "simulated"


def test_interim_logs_emitted_during_run():
    events, broadcast = _collect()
    runner = Runner(broadcast=broadcast, status_interval=0.02)
    runner.start("simulated", {"total_steps": 400, "speed_per_sec": 2000})
    _wait_until_idle(runner)

    info_logs = [e for e in events
                 if e["type"] == "log" and e["level"] == "info"]
    # start log + run-complete log + at least one interim progress log.
    interim = [e for e in info_logs
               if e["message"] not in ("run complete",)
               and not e["message"].startswith("starting ")]
    assert interim, "expected interim log events while running"


def test_stop_halts_simulated_promptly():
    events, broadcast = _collect()
    # Slow trainer so we can stop it mid-run.
    runner = Runner(broadcast=broadcast, status_interval=0.02)
    runner.start("simulated", {"total_steps": 100000, "speed_per_sec": 200})
    # Let it make some progress, then stop.
    time.sleep(0.15)
    runner.stop()
    _wait_until_idle(runner, timeout=5.0)

    assert not runner.is_running
    statuses = [e for e in events if e["type"] == "status"]
    # Last status returns to idle on cooperative stop.
    assert statuses[-1]["state"] == "idle"
    # Never reached completion.
    assert not any(e["type"] == "metrics" for e in events)
    last_step = max((e["step"] for e in statuses if e["state"] == "running"),
                    default=0)
    assert last_step < 100000


def test_single_run_lock_emits_warn():
    events, broadcast = _collect()
    runner = Runner(broadcast=broadcast, status_interval=0.02)
    runner.start("simulated", {"total_steps": 5000, "speed_per_sec": 500})
    # Second start while running -> warn log, no second run.
    started = runner.start("simulated", {"total_steps": 5000, "speed_per_sec": 500})
    assert started is False
    runner.stop()
    _wait_until_idle(runner)

    warns = [e for e in events
             if e["type"] == "log" and e["level"] == "warn"
             and e["message"] == "a run is already in progress"]
    assert len(warns) == 1


def test_last_status_replay_starts_idle():
    runner = Runner()
    s = runner.last_status()
    assert s["type"] == "status"
    assert s["state"] == "idle"


def test_error_does_not_crash_and_sets_error_state(monkeypatch):
    # Force the lgbm trainer's dataset path to a guaranteed-missing file so this
    # test is deterministic whether or not a real dataset.parquet exists on disk.
    from server.trainers import lgbm as lgbm_mod
    monkeypatch.setattr(lgbm_mod, "DATASET_PATH",
                        "data/processed/__nonexistent_for_test__.parquet")

    events, broadcast = _collect()
    runner = Runner(broadcast=broadcast, status_interval=0.02)
    # lgbm with no dataset -> friendly FileNotFoundError -> error event + status.
    runner.start("lgbm", {})
    _wait_until_idle(runner)

    assert not runner.is_running
    error_events = [e for e in events if e["type"] == "error"]
    assert error_events, "expected an error event"
    assert "dataset not found" in error_events[0]["message"]
    statuses = [e for e in events if e["type"] == "status"]
    assert statuses[-1]["state"] == "error"
