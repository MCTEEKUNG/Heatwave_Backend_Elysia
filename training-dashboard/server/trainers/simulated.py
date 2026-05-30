"""A fake trainer: a timed loop that advances ~speed_per_sec steps/sec."""
from __future__ import annotations

import time

from .base import ProgressCb, ShouldStop, Trainer


class SimulatedTrainer(Trainer):
    name = "simulated"

    def run(self, config: dict, progress_cb: ProgressCb, should_stop: ShouldStop) -> dict:
        config = config or {}
        total_steps = int(config.get("total_steps", 10000))
        speed_per_sec = float(config.get("speed_per_sec", 100.0))
        if total_steps <= 0:
            total_steps = 1
        if speed_per_sec <= 0:
            speed_per_sec = 1.0

        # Seconds of wall-clock per step, so the loop advances ~speed_per_sec/s.
        per_step = 1.0 / speed_per_sec

        progress_cb(0, total_steps, "starting simulated run")

        step = 0
        stopped = False
        # Milestones at which we emit a more interesting message.
        milestones = {max(1, int(total_steps * f)) for f in (0.25, 0.5, 0.75)}
        for step in range(1, total_steps + 1):
            if should_stop():
                stopped = True
                break
            # Simulate the work for this step.
            if per_step > 0:
                time.sleep(per_step)
            if step in milestones:
                msg = f"reached {round(100 * step / total_steps)}% ({step}/{total_steps})"
            else:
                msg = f"step {step}/{total_steps}"
            progress_cb(step, total_steps, msg)

        return {
            "trainer": "simulated",
            "final_step": step,
            "total_steps": total_steps,
            "speed_per_sec": speed_per_sec,
            "stopped": stopped,
        }
