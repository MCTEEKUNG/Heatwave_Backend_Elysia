"""Two simultaneous clients must BOTH receive ordered broadcasts (validates the
locked-broadcast fan-out fix). Requires a live server on 127.0.0.1:8000."""
import asyncio
import json
import sys

import websockets

URL = "ws://127.0.0.1:8000/ws"


async def watch(ws, tag):
    """Collect status progresses until state=done; return list of progresses."""
    progresses = []
    while True:
        ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        if ev.get("type") == "status":
            if ev["state"] == "running":
                progresses.append(ev["progress"])
            elif ev["state"] == "done":
                progresses.append(ev["progress"])
                return progresses


async def main():
    async with websockets.connect(URL) as a, websockets.connect(URL) as b:
        # drain each client's initial snapshot
        await a.recv()
        await b.recv()
        # client A starts a short fast run
        await a.send(json.dumps({"command": "start", "trainer": "simulated",
                                 "config": {"total_steps": 600, "speed_per_sec": 600}}))
        ra, rb = await asyncio.gather(watch(a, "A"), watch(b, "B"))

    ok = True
    for tag, prog in (("A", ra), ("B", rb)):
        mono = prog == sorted(prog)
        reached = prog and abs(prog[-1] - 100.0) < 1e-6
        print(f"  client {tag}: {len(prog)} status frames, monotonic={mono}, reached_done={bool(reached)} -> {prog}")
        ok = ok and mono and reached
    print("\n" + ("MULTICLIENT PASSED" if ok else "MULTICLIENT FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
