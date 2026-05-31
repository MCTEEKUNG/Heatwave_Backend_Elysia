"""Run a pipeline script as a streamed subprocess "job".

A StageJob satisfies the same contract as a Trainer (run(config, progress_cb,
should_stop) -> dict) so the existing single-slot runner drives it unchanged.
Each stdout line becomes a log; lines matching the spec's progress_regex update
progress; the spec's summary_parser turns the captured stdout into the result.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class StageSpec:
    name: str
    argv: list[str]
    progress_regex: Optional[str]          # one capture group -> current step
    summary_parser: Callable[[list[str]], dict]
    total_steps: int = 0                   # 0 => indeterminate progress


_P0_A = re.compile(r"A antecedent only\s+ROC=([\d.]+)\s+PR-AUC=([\d.]+)\s+lift=([\d.]+)x")
_P0_B = re.compile(r"B \+ GEFS forecast \(P0\)\s+ROC=([\d.]+)\s+PR-AUC=([\d.]+)\s+lift=([\d.]+)x")
_P0_MATCHED = re.compile(r"matched rows=(\d+).*years=\[([\d, ]+)\].*pos_rate=([\d.]+)")


def parse_p0_summary(lines: list[str]) -> dict:
    out: dict = {}
    text = "".join(lines)
    if (m := _P0_MATCHED.search(text)):
        out["matched_rows"] = int(m.group(1))
        out["origin_years"] = [int(x) for x in m.group(2).split(",") if x.strip()]
        out["pos_rate"] = float(m.group(3))
    if (m := _P0_A.search(text)):
        out["a_roc"], out["a_prauc"], out["a_lift"] = float(m.group(1)), float(m.group(2)), float(m.group(3))
    if (m := _P0_B.search(text)):
        out["b_roc"], out["b_prauc"], out["b_lift"] = float(m.group(1)), float(m.group(2)), float(m.group(3))
    return out


class _StopStage(Exception):
    pass


class StageJob:
    def __init__(self, spec: StageSpec):
        self.spec = spec
        self.name = spec.name

    def _iter_process_lines(self, argv: list[str]):
        """Yield stdout lines from the live subprocess (overridden in tests)."""
        self._proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        assert self._proc.stdout is not None
        yield from self._proc.stdout

    def run(self, config: dict, progress_cb, should_stop,
            log_cb: Optional[Callable[[str, str], None]] = None) -> dict:
        prog = re.compile(self.spec.progress_regex) if self.spec.progress_regex else None
        captured: list[str] = []
        try:
            for raw in self._iter_process_lines(self.spec.argv):
                line = raw.rstrip("\n")
                captured.append(raw)
                if log_cb:
                    log_cb("info", line)
                if prog and (m := prog.search(line)):
                    step = int(m.group(1))
                    progress_cb(step, self.spec.total_steps or step, line)
                if should_stop():
                    raise _StopStage()
        except _StopStage:
            p = getattr(self, "_proc", None)
            if p is not None:
                p.terminate()
            return {"stopped": True}
        return self.spec.summary_parser(captured)


STAGE_REGISTRY: dict[str, StageSpec] = {
    "train_p0": StageSpec(
        name="train_p0",
        argv=[sys.executable, "-u", "scripts/train_p0.py"],
        progress_regex=None,
        summary_parser=parse_p0_summary,
    ),
}


def get_stage(name: str) -> StageJob:
    try:
        return StageJob(STAGE_REGISTRY[name])
    except KeyError:
        raise ValueError(f"unknown stage: {name!r}")


def available_stages() -> list[str]:
    return sorted(STAGE_REGISTRY)
