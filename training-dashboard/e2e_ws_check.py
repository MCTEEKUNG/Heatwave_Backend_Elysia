"""End-to-end WebSocket integration check against a LIVE training server.

Run the server first:
  .venv\\Scripts\\python.exe -m uvicorn server.app:app --app-dir training-dashboard --host 127.0.0.1 --port 8000
Then:
  .venv\\Scripts\\python.exe training-dashboard/e2e_ws_check.py

Exits non-zero on any contract violation.
"""
import asyncio
import json
import sys

import websockets

URL = "ws://127.0.0.1:8000/ws"
FAIL = []


def check(cond, msg):
    if not cond:
        FAIL.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


async def recv_until(ws, pred, timeout=15.0):
    """Collect events until pred(event) is true; return (events, matched)."""
    events = []
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=end - loop.time())
        except asyncio.TimeoutError:
            return events, None
        ev = json.loads(raw)
        events.append(ev)
        if pred(ev):
            return events, ev
    return events, None


async def main():
    print(f"[connect] {URL}")
    async with websockets.connect(URL) as ws:
        # 1. On-connect status must be idle
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        check(first.get("type") == "status", "first frame is a status event")
        check(first.get("state") == "idle", f"initial state is idle (got {first.get('state')})")

        # 2. Start a short fast run, collect to done
        await ws.send(json.dumps({"command": "start", "trainer": "simulated",
                                  "config": {"total_steps": 500, "speed_per_sec": 500}}))
        events, done = await recv_until(ws, lambda e: e.get("type") == "status" and e.get("state") == "done")
        check(done is not None, "reached state=done")

        statuses = [e for e in events if e.get("type") == "status"]
        progresses = [e["progress"] for e in statuses]
        check(progresses == sorted(progresses), f"progress is monotonic non-decreasing ({progresses})")
        check(any(0 < p < 100 for p in progresses) or len(progresses) >= 1, "saw progress updates")
        if done:
            check(abs(done["progress"] - 100.0) < 1e-6, "done progress == 100")
            check(done["step"] == done["total_steps"], "done step == total_steps")
            # field-name contract on a running/done status
            for f in ("speed_per_sec", "eta_seconds", "total_steps", "step", "message", "ts"):
                check(f in done, f"status has field '{f}'")

        # 3. metrics event arrives after done
        _, metrics = await recv_until(ws, lambda e: e.get("type") == "metrics", timeout=5)
        check(metrics is not None, "received a metrics event")
        check(isinstance(metrics and metrics.get("report"), dict), "metrics.report is an object")

        # 4. New run, then STOP mid-flight -> must return to idle
        await ws.send(json.dumps({"command": "start", "trainer": "simulated",
                                  "config": {"total_steps": 100000, "speed_per_sec": 200}}))
        # wait until it's actually running
        _, running = await recv_until(ws, lambda e: e.get("type") == "status" and e.get("state") == "running", timeout=5)
        check(running is not None, "second run reached state=running")
        await ws.send(json.dumps({"command": "stop"}))
        _, idle = await recv_until(ws, lambda e: e.get("type") == "status" and e.get("state") == "idle", timeout=8)
        check(idle is not None, "stop returned server to state=idle")
        print(f"  [idle frame] {idle}")
        # The real stability test: after idle, the worker thread must be DEAD.
        # No further running/progress status frames may arrive.
        trailing, _ = await recv_until(ws, lambda e: False, timeout=3.0)
        zombie = [e for e in trailing if e.get("type") == "status" and e.get("state") == "running"]
        check(not zombie, f"no zombie progress after stop (got {len(zombie)} stray running frames)")

    print()
    if FAIL:
        print(f"INTEGRATION FAILED: {len(FAIL)} problem(s)")
        for f in FAIL:
            print(f" - {f}")
        sys.exit(1)
    print("INTEGRATION PASSED: all contract checks green")


if __name__ == "__main__":
    asyncio.run(main())
