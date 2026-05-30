"""Protocol pydantic round-trips and serialization helpers."""
import pytest

from server import protocol


def test_start_command_with_config():
    cmd = protocol.parse_command({
        "command": "start",
        "trainer": "simulated",
        "config": {"total_steps": 500, "speed_per_sec": 250},
    })
    assert isinstance(cmd, protocol.StartCommand)
    assert cmd.trainer == "simulated"
    assert cmd.config.total_steps == 500
    assert cmd.config.speed_per_sec == 250


def test_start_command_without_config():
    cmd = protocol.parse_command({"command": "start", "trainer": "lgbm"})
    assert isinstance(cmd, protocol.StartCommand)
    assert cmd.config is None


def test_stop_command():
    cmd = protocol.parse_command({"command": "stop"})
    assert isinstance(cmd, protocol.StopCommand)


def test_unknown_command_raises():
    with pytest.raises(ValueError):
        protocol.parse_command({"command": "nope"})


def test_bad_trainer_raises():
    with pytest.raises(Exception):
        protocol.parse_command({"command": "start", "trainer": "magic"})


def test_status_event_fields_exact():
    ev = protocol.status_event(
        "running", progress=42.5, step=425, total_steps=1000,
        speed_per_sec=100.0, eta_seconds=6, message="hi", ts=1.0)
    assert ev == {
        "type": "status", "state": "running", "progress": 42.5, "step": 425,
        "total_steps": 1000, "speed_per_sec": 100.0, "eta_seconds": 6,
        "message": "hi", "ts": 1.0,
    }


def test_status_event_eta_null():
    ev = protocol.status_event("running", eta_seconds=None, ts=2.0)
    assert ev["eta_seconds"] is None


def test_log_event_fields():
    ev = protocol.log_event("careful", level="warn", ts=3.0)
    assert ev == {"type": "log", "level": "warn", "message": "careful", "ts": 3.0}


def test_metrics_event_arbitrary_nested():
    report = {"trainer": "lgbm", "test": {"f2": 0.7, "nested": {"a": [1, 2]}}}
    ev = protocol.metrics_event(report)
    assert ev == {"type": "metrics", "report": report}


def test_error_event_fields():
    ev = protocol.error_event("boom")
    assert ev == {"type": "error", "message": "boom"}
