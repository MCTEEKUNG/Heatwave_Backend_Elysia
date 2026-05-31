# Heatwave Cockpit — Phase 1 (Tab Shell + Lab) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the training-only dashboard into a tabbed cockpit and ship the **Lab** tab — a live GEFS-pull monitor and a one-click P0 (`train_p0`) runner with a decision-gate readout — reusing the existing WS/runner infrastructure.

**Architecture:** Front end gains a top `TabBar`; today's `App.tsx` body is extracted **verbatim** into `<TrainTab/>` so the existing experience is untouched. New `<LabPanel/>` polls read-only HTTP endpoints for GEFS status and starts/stops the detached pull. A new server `StageJob` runs `scripts/train_p0.py` as a streamed subprocess through the **unchanged** single-slot runner; its A-vs-B result is parsed and rendered with the stop-condition gate from `docs/MODEL-IMPROVEMENT.md`.

**Tech Stack:** FastAPI + WebSocket (Python, `server/`), Vite + React 19 + TypeScript (`web/`), pytest (`server/tests`), Vitest + React Testing Library (`web/src`).

**Scope:** Tab shell + Lab tab only. Pipeline / Forecast / Ops tabs are separate follow-up plans (each reuses `StageJob`). Tabs other than Train and Lab render a simple "coming soon" stub this phase.

**Repo paths are relative to** `C:\Users\ASUS\Heatwave_AI`. Run the web `cd training-dashboard/web`; run server tests from the repo root.

---

## File Structure

**Create:**
- `training-dashboard/web/src/components/TabBar.tsx` — top tab navigation (presentational)
- `training-dashboard/web/src/components/TabBar.test.tsx` — TabBar tests
- `training-dashboard/web/src/tabs/TrainTab.tsx` — today's App body, extracted unchanged
- `training-dashboard/web/src/tabs/LabPanel.tsx` — GEFS monitor + P0 runner
- `training-dashboard/web/src/tabs/StubTab.tsx` — "coming soon" placeholder for Pipeline/Forecast/Ops
- `training-dashboard/web/src/lab.ts` — typed fetch helpers + pure formatters for Lab (unit-tested)
- `training-dashboard/web/src/lab.test.ts` — formatter/parser tests
- `training-dashboard/server/gefs_status.py` — pure reader: store + log → status dict
- `training-dashboard/server/stages.py` — `StageJob` (subprocess stream) + `STAGE_REGISTRY` + `get_stage`
- `training-dashboard/server/jobs.py` — `resolve_job(name, kind)` over trainers + stages
- `training-dashboard/server/tests/test_gefs_status.py`
- `training-dashboard/server/tests/test_stages.py`
- `training-dashboard/server/tests/test_gefs_endpoints.py`

**Modify:**
- `training-dashboard/web/src/App.tsx` — becomes shell: header + `TabBar` + active-tab router; keeps the single WS client
- `training-dashboard/web/src/protocol.ts` — add optional `kind` to `StartCommand`
- `training-dashboard/web/src/ws.ts` — add `startStage(name)` 
- `training-dashboard/server/protocol.py` — add optional `kind` to `StartCommand`
- `training-dashboard/server/runner.py` — resolve via `resolve_job(name, kind)` instead of `get_trainer`
- `training-dashboard/server/app.py` — new endpoints: `/api/gefs/status|start|stop`, `/api/p0/runs`; pass `kind` to `runner.start`

---

## PART A — Tab Shell

### Task A1: TabBar component

**Files:**
- Create: `training-dashboard/web/src/components/TabBar.tsx`
- Test: `training-dashboard/web/src/components/TabBar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// training-dashboard/web/src/components/TabBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TabBar, { type TabKey } from './TabBar'

describe('TabBar', () => {
  it('renders all tabs and marks the active one', () => {
    render(<TabBar active="train" onSelect={() => {}} />)
    expect(screen.getByRole('tab', { name: /Train/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /Lab/ })).toHaveAttribute('aria-selected', 'false')
    // all five tabs present
    for (const t of ['Pipeline', 'Train', 'Forecast', 'Ops', 'Lab'])
      expect(screen.getByRole('tab', { name: new RegExp(t) })).toBeInTheDocument()
  })

  it('calls onSelect with the tab key when clicked', () => {
    const onSelect = vi.fn()
    render(<TabBar active="train" onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('tab', { name: /Lab/ }))
    expect(onSelect).toHaveBeenCalledWith('lab' satisfies TabKey)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd training-dashboard/web && bunx vitest run src/components/TabBar.test.tsx`
Expected: FAIL — `Cannot find module './TabBar'`.

- [ ] **Step 3: Write minimal implementation**

```tsx
// training-dashboard/web/src/components/TabBar.tsx
export type TabKey = 'pipeline' | 'train' | 'forecast' | 'ops' | 'lab'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'train', label: 'Train' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'ops', label: 'Ops' },
  { key: 'lab', label: 'Lab' },
]

export default function TabBar({
  active,
  onSelect,
}: {
  active: TabKey
  onSelect: (key: TabKey) => void
}) {
  return (
    <nav className="tab-bar" role="tablist" aria-label="Cockpit sections">
      {TABS.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          className={`tab ${active === t.key ? 'tab-active' : ''}`}
          onClick={() => onSelect(t.key)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd training-dashboard/web && bunx vitest run src/components/TabBar.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Add minimal styling**

Append to `training-dashboard/web/src/App.css`:

```css
.tab-bar { display: flex; gap: 4px; margin: 0 0 18px; flex-wrap: wrap; }
.tab { background: transparent; border: 1px solid rgba(241,236,227,.14); color: var(--paper, #f1ece3);
  border-radius: 8px 8px 0 0; padding: 8px 16px; cursor: pointer; font: inherit; opacity: .65; }
.tab:hover { opacity: .9; }
.tab-active { opacity: 1; border-bottom-color: transparent; background: rgba(255,106,61,.14);
  box-shadow: inset 0 -2px 0 #ff6a3d; }
```

- [ ] **Step 6: Commit**

```bash
git add training-dashboard/web/src/components/TabBar.tsx training-dashboard/web/src/components/TabBar.test.tsx training-dashboard/web/src/App.css
git commit -m "feat(dashboard): add TabBar navigation component"
```

### Task A2: Extract TrainTab + wire tab router in App

**Files:**
- Create: `training-dashboard/web/src/tabs/TrainTab.tsx`
- Create: `training-dashboard/web/src/tabs/StubTab.tsx`
- Modify: `training-dashboard/web/src/App.tsx`

- [ ] **Step 1: Create StubTab**

```tsx
// training-dashboard/web/src/tabs/StubTab.tsx
export default function StubTab({ title }: { title: string }) {
  return (
    <div className="stub-tab">
      <h2>{title}</h2>
      <p className="subtitle">Coming in a later phase of the cockpit.</p>
    </div>
  )
}
```

- [ ] **Step 2: Create TrainTab — move today's App body verbatim**

Cut the JSX that currently sits **inside** `App.tsx`'s returned `<div className="app">` *below the `<header>`* (the `Controls`, `ProgressBar`, `status-row`, `panels`, saved-banner IIFE, `LogPanel`, `LeaderboardPanel`, `RunHistory`, `ModelReport`, `Toast`) into a new presentational component. It receives everything it needs as props — no behavior change.

```tsx
// training-dashboard/web/src/tabs/TrainTab.tsx
import type { TrainerKind } from '../protocol'
import type { UiState } from '../ws'
import Controls from '../components/Controls'
import ProgressBar from '../components/ProgressBar'
import Eta from '../components/Eta'
import SpeedChart from '../components/SpeedChart'
import LogPanel from '../components/LogPanel'
import MetricsPanel from '../components/MetricsPanel'
import LeaderboardPanel from '../components/LeaderboardPanel'
import RunHistory from '../components/RunHistory'
import ModelReport from '../components/ModelReport'
import FolderIcon from '../components/FolderIcon'

const API_BASE = 'http://127.0.0.1:8000'

export default function TrainTab({
  state,
  trainer,
  setTrainer,
  onStart,
  onStop,
  connected,
  running,
  refreshSignal,
}: {
  state: UiState
  trainer: TrainerKind
  setTrainer: (t: TrainerKind) => void
  onStart: (config?: Record<string, number>) => void
  onStop: () => void
  connected: boolean
  running: boolean
  refreshSignal: number
}) {
  const saved = state.metrics?.saved as
    | { name: string; file: string; path: string; size_kb: number }
    | undefined
  return (
    <>
      <Controls
        trainer={trainer}
        onTrainerChange={setTrainer}
        onStart={onStart}
        onStop={onStop}
        running={running}
        connected={connected}
      />
      <ProgressBar progress={state.progress} step={state.step} total={state.total_steps} />
      <div className="status-row">
        <Eta seconds={state.eta_seconds} />
        <span className="status-state" data-state={state.state}>state: {state.state}</span>
        {state.message ? <span className="status-message">{state.message}</span> : null}
      </div>
      <div className="panels">
        <SpeedChart history={state.speedHistory} current={state.speed_per_sec} />
        <MetricsPanel metrics={state.metrics} />
      </div>
      {state.state === 'done' && saved ? (
        <div className="saved-banner">
          <span className="saved-check" aria-hidden="true">✓</span>
          <span>saved model <code>{saved.path}</code> ({saved.size_kb} KB)</span>
          <button
            className="btn btn-refresh folder-btn"
            title="Open the models folder in your file explorer"
            onClick={() => { void fetch(`${API_BASE}/api/reveal-models`, { method: 'POST' }) }}
          >
            <FolderIcon /> open folder
          </button>
        </div>
      ) : null}
      <LogPanel logs={state.logs} />
      <LeaderboardPanel refreshSignal={refreshSignal} />
      <RunHistory refreshSignal={refreshSignal} />
      <ModelReport />
    </>
  )
}
```

- [ ] **Step 3: Rewrite App.tsx as the shell + tab router**

Keep ALL existing hooks/effects (WS client, toast transitions, indicator). Replace the returned body below `<header>` with the `TabBar` + active-tab switch. The `Toast` stays app-level.

```tsx
// training-dashboard/web/src/App.tsx  (return block only — keep the hooks above unchanged)
import TabBar, { type TabKey } from './components/TabBar'
import TrainTab from './tabs/TrainTab'
import LabPanel from './tabs/LabPanel'
import StubTab from './tabs/StubTab'
// ...existing imports stay; remove now-unused direct component imports moved into TrainTab...

  const [tab, setTab] = useState<TabKey>(
    (window.location.hash.replace('#', '') as TabKey) || 'train',
  )
  function selectTab(k: TabKey) {
    setTab(k)
    window.location.hash = k
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Heatwave Cockpit</h1>
        <div className={`conn-indicator ${indicatorClass}`}>
          <span className="conn-dot" aria-hidden="true">●</span>
          <span className="conn-text">{CONNECTION_LABEL[state.connection]}</span>
        </div>
      </header>

      <TabBar active={tab} onSelect={selectTab} />

      {tab === 'train' && (
        <TrainTab
          state={state} trainer={trainer} setTrainer={setTrainer}
          onStart={handleStart} onStop={handleStop}
          connected={connected} running={running} refreshSignal={refreshSignal}
        />
      )}
      {tab === 'lab' && <LabPanel connected={connected} />}
      {tab === 'pipeline' && <StubTab title="Pipeline" />}
      {tab === 'forecast' && <StubTab title="Forecast" />}
      {tab === 'ops' && <StubTab title="Ops" />}

      <Toast message={toast} />
    </div>
  )
```

- [ ] **Step 4: Add stub styling**

Append to `training-dashboard/web/src/App.css`:

```css
.stub-tab { padding: 48px 8px; text-align: center; opacity: .8; }
```

- [ ] **Step 5: Verify the whole web build + existing tests still pass**

Run: `cd training-dashboard/web && bunx tsc --noEmit && bunx vitest run`
Expected: type-check clean; all existing tests (Eta, ws, TabBar) PASS. (LabPanel import resolves after Task B/C; for this commit, temporarily stub `LabPanel` as `export default function LabPanel(){return null}` if executing strictly in order, then replace it in Task C.)

- [ ] **Step 6: Commit**

```bash
git add training-dashboard/web/src/App.tsx training-dashboard/web/src/tabs/TrainTab.tsx training-dashboard/web/src/tabs/StubTab.tsx training-dashboard/web/src/App.css
git commit -m "refactor(dashboard): extract TrainTab, add tab router shell"
```

---

## PART B — GEFS monitor (read-only + detached control)

### Task B1: gefs_status reader

**Files:**
- Create: `training-dashboard/server/gefs_status.py`
- Test: `training-dashboard/server/tests/test_gefs_status.py`

- [ ] **Step 1: Write the failing test**

```python
# training-dashboard/server/tests/test_gefs_status.py
import pandas as pd
from server.gefs_status import gefs_status

def _store(tmp_path):
    df = pd.DataFrame({
        "province_id": [1, 1, 2, 2],
        "issue_date": ["2016-03-01", "2017-03-01", "2016-03-01", "2017-03-01"],
        "target_date": ["2016-03-02", "2017-03-02", "2016-03-02", "2017-03-02"],
        "lead_k": [1, 1, 1, 1],
        "fc_tmax": [30.0, 31.0, 32.0, 33.0],
        "fc_spfh": [0.01, 0.012, 0.011, 0.013],
    })
    p = tmp_path / "gefs_forecast_store.parquet"
    df.to_parquet(p, index=False)
    return str(p)

def test_status_summarizes_store(tmp_path):
    store = _store(tmp_path)
    log = tmp_path / "log.txt"
    log.write_text("checkpoint @ 20/62 inits (20 new), rows this run 10780 -> store written\n")
    st = gefs_status(store_path=store, log_path=str(log), target_inits=124)
    assert st["inits"] == 2
    assert st["by_year"] == {"2016": 1, "2017": 1}
    assert st["fc_spfh_pct"] == 100.0
    assert st["rows"] == 4
    assert st["target"] == 124
    assert "checkpoint @ 20/62" in st["log_tail"]

def test_status_missing_store_is_safe(tmp_path):
    st = gefs_status(store_path=str(tmp_path / "nope.parquet"),
                     log_path=str(tmp_path / "nope.log"), target_inits=124)
    assert st["inits"] == 0 and st["rows"] == 0 and st["by_year"] == {}
    assert st["log_tail"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_gefs_status.py -v`
Expected: FAIL — `ModuleNotFoundError: server.gefs_status`.

- [ ] **Step 3: Write implementation**

```python
# training-dashboard/server/gefs_status.py
"""Read-only summary of the detached GEFS reforecast pull for the Lab tab.

Pure function over the store parquet + build log; never launches anything.
"""
from __future__ import annotations

import os

import pandas as pd

STORE_PATH = "data/processed/gefs_forecast_store.parquet"
LOG_PATH = "data/processed/gefs_build_log.txt"
TARGET_INITS = 124  # 2016-2019 Mar-May, stride 3 (season_inits)


def gefs_status(store_path: str = STORE_PATH, log_path: str = LOG_PATH,
                target_inits: int = TARGET_INITS) -> dict:
    out = {"inits": 0, "rows": 0, "by_year": {}, "fc_spfh_pct": 0.0,
           "target": target_inits, "log_tail": ""}
    if os.path.exists(store_path):
        s = pd.read_parquet(store_path)
        out["rows"] = int(len(s))
        if len(s):
            out["inits"] = int(s["issue_date"].nunique())
            yr = pd.to_datetime(s["issue_date"]).dt.year
            out["by_year"] = {str(int(y)): int(n) for y, n in yr.value_counts().sort_index().items()}
            if "fc_spfh" in s.columns:
                out["fc_spfh_pct"] = round(float(s["fc_spfh"].notna().mean()) * 100, 1)
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        out["log_tail"] = "".join(lines[-12:]).strip()
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_gefs_status.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add training-dashboard/server/gefs_status.py training-dashboard/server/tests/test_gefs_status.py
git commit -m "feat(dashboard): GEFS pull status reader"
```

### Task B2: GEFS endpoints (status / start / stop)

**Files:**
- Modify: `training-dashboard/server/app.py`
- Test: `training-dashboard/server/tests/test_gefs_endpoints.py`

- [ ] **Step 1: Write the failing test**

```python
# training-dashboard/server/tests/test_gefs_endpoints.py
from fastapi.testclient import TestClient
from server.app import app

def test_gefs_status_endpoint_returns_shape():
    with TestClient(app) as c:
        r = c.get("/api/gefs/status")
        assert r.status_code == 200
        body = r.json()
        for k in ("inits", "rows", "by_year", "fc_spfh_pct", "target", "running", "log_tail"):
            assert k in body
        assert isinstance(body["running"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_gefs_endpoints.py -v`
Expected: FAIL — 404 (route absent).

- [ ] **Step 3: Add endpoints to app.py**

Add near the other `@app.get` routes (after `model_card`). Imports at top: `from .gefs_status import gefs_status`, and `import signal` is not needed (use `os.kill`/`Popen.terminate`).

```python
# --- GEFS detached pull control (Lab tab) ----------------------------------- #
GEFS_PID_FILE = "data/processed/gefs_pull.pid"
GEFS_LOG = "data/processed/gefs_build_log.txt"


def _pid_alive(pid: int) -> bool:
    # NB: on Windows os.kill(pid, 0) does NOT probe — any non-CTRL signal calls
    # TerminateProcess and would KILL the pull. Use OpenProcess+GetExitCodeProcess.
    if sys.platform.startswith("win"):
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == STILL_ACTIVE
    try:
        os.kill(pid, 0)  # POSIX: signal 0 = existence check (raises if dead)
        return True
    except (OSError, ProcessLookupError):
        return False


def _gefs_running_pid() -> Optional[int]:
    if not os.path.exists(GEFS_PID_FILE):
        return None
    try:
        pid = int(open(GEFS_PID_FILE).read().strip())
    except Exception:
        return None
    return pid if _pid_alive(pid) else None


@app.get("/api/gefs/status")
async def gefs_status_endpoint() -> dict:
    st = gefs_status()
    st["running"] = _gefs_running_pid() is not None
    return st


@app.post("/api/gefs/start")
async def gefs_start(body: Optional[dict] = None) -> dict:
    """Launch (or resume) the detached GEFS pull. Idempotent: refuses if alive."""
    if _gefs_running_pid() is not None:
        raise HTTPException(status_code=409, detail="GEFS pull already running")
    years = (body or {}).get("years") or [2016, 2017]
    argv = [sys.executable, "scripts/build_gefs_store.py", *[str(int(y)) for y in years]]
    creationflags = 0x00000008 if sys.platform.startswith("win") else 0  # DETACHED_PROCESS
    logf = open(GEFS_LOG, "ab")
    proc = subprocess.Popen(
        argv, stdout=logf, stderr=subprocess.STDOUT,
        creationflags=creationflags,
        start_new_session=not sys.platform.startswith("win"),
    )
    with open(GEFS_PID_FILE, "w") as f:
        f.write(str(proc.pid))
    return {"pid": proc.pid, "years": years}


@app.post("/api/gefs/stop")
async def gefs_stop() -> dict:
    pid = _gefs_running_pid()
    if pid is None:
        return {"stopped": False, "reason": "not running"}
    try:
        os.kill(pid, getattr(__import__("signal"), "SIGTERM", 15))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"could not stop: {exc}")
    return {"stopped": True, "pid": pid}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_gefs_endpoints.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add training-dashboard/server/app.py training-dashboard/server/tests/test_gefs_endpoints.py
git commit -m "feat(dashboard): GEFS pull start/stop/status endpoints"
```

### Task B3: Lab formatters (lab.ts)

**Files:**
- Create: `training-dashboard/web/src/lab.ts`
- Test: `training-dashboard/web/src/lab.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// training-dashboard/web/src/lab.test.ts
import { describe, it, expect } from 'vitest'
import { gefsPercent, type GefsStatus } from './lab'

describe('gefsPercent', () => {
  it('computes inits/target as a clamped percent', () => {
    const st: GefsStatus = { inits: 62, target: 124, rows: 0, by_year: {},
      fc_spfh_pct: 100, running: true, log_tail: '' }
    expect(gefsPercent(st)).toBe(50)
  })
  it('is 0 when target is 0', () => {
    expect(gefsPercent({ inits: 5, target: 0, rows: 0, by_year: {},
      fc_spfh_pct: 0, running: false, log_tail: '' })).toBe(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd training-dashboard/web && bunx vitest run src/lab.test.ts`
Expected: FAIL — cannot find `./lab`.

- [ ] **Step 3: Write lab.ts**

```ts
// training-dashboard/web/src/lab.ts
const API_BASE = 'http://127.0.0.1:8000'

export interface GefsStatus {
  inits: number
  target: number
  rows: number
  by_year: Record<string, number>
  fc_spfh_pct: number
  running: boolean
  log_tail: string
}

export interface P0Run {
  ts: number
  origin_years: number[]
  matched_rows: number
  pos_rate: number
  a_roc: number
  b_roc: number
  a_lift: number
  b_lift: number
}

export function gefsPercent(s: GefsStatus): number {
  if (!s.target) return 0
  return Math.max(0, Math.min(100, Math.round((s.inits / s.target) * 100)))
}

export async function fetchGefsStatus(): Promise<GefsStatus> {
  const r = await fetch(`${API_BASE}/api/gefs/status`)
  return (await r.json()) as GefsStatus
}
export async function startGefs(): Promise<void> {
  await fetch(`${API_BASE}/api/gefs/start`, { method: 'POST' })
}
export async function stopGefs(): Promise<void> {
  await fetch(`${API_BASE}/api/gefs/stop`, { method: 'POST' })
}
export async function fetchP0Runs(): Promise<P0Run[]> {
  const r = await fetch(`${API_BASE}/api/p0/runs`)
  const body = (await r.json()) as { runs: P0Run[] }
  return body.runs ?? []
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd training-dashboard/web && bunx vitest run src/lab.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add training-dashboard/web/src/lab.ts training-dashboard/web/src/lab.test.ts
git commit -m "feat(dashboard): Lab fetch helpers + gefsPercent"
```

---

## PART C — StageJob backend + P0 runner + LabPanel

### Task C1: StageJob + stage registry

**Files:**
- Create: `training-dashboard/server/stages.py`
- Create: `training-dashboard/server/jobs.py`
- Test: `training-dashboard/server/tests/test_stages.py`

- [ ] **Step 1: Write the failing test** (feed canned stdout — no real subprocess)

```python
# training-dashboard/server/tests/test_stages.py
from server.stages import StageJob, StageSpec, parse_p0_summary

def test_stagejob_streams_lines_and_parses_summary(monkeypatch):
    canned = [
        "P0 covariates: ['fc_tmax', 'fc_rh', 'fc_heat_index']\n",
        "matched rows=49588 (covered by real forecasts) years=[2016, 2017, 2018, 2019] pos_rate=0.020\n",
        "  A antecedent only            ROC=0.602 PR-AUC=0.040 lift=1.30x\n",
        "  B + GEFS forecast (P0)       ROC=0.631 PR-AUC=0.052 lift=1.69x\n",
    ]
    spec = StageSpec(name="train_p0", argv=["python", "-c", "pass"],
                     progress_regex=None, summary_parser=parse_p0_summary)
    job = StageJob(spec)
    monkeypatch.setattr(job, "_iter_process_lines", lambda argv: iter(canned))
    logs = []
    report = job.run({}, lambda step, total, msg: None, lambda: False,
                     log_cb=lambda lvl, m: logs.append(m))
    assert any("matched rows=49588" in m for m in logs)
    assert report["a_roc"] == 0.602 and report["b_roc"] == 0.631
    assert report["b_lift"] == 1.69 and report["origin_years"] == [2016, 2017, 2018, 2019]

def test_parse_p0_summary_handles_missing():
    assert parse_p0_summary(["nothing useful\n"]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_stages.py -v`
Expected: FAIL — `ModuleNotFoundError: server.stages`.

- [ ] **Step 3: Write stages.py**

```python
# training-dashboard/server/stages.py
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
        proc = getattr(self, "_proc", None)
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
```

- [ ] **Step 4: Write jobs.py (resolver over trainers + stages)**

```python
# training-dashboard/server/jobs.py
"""Resolve a job by (name, kind): a Trainer or a pipeline StageJob.

Both expose run(config, progress_cb, should_stop) -> dict, so the runner is
agnostic to which kind it drives.
"""
from __future__ import annotations

from .stages import get_stage
from .trainers import get_trainer


def resolve_job(name: str, kind: str = "trainer"):
    if kind == "stage":
        return get_stage(name)
    return get_trainer(name)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_stages.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add training-dashboard/server/stages.py training-dashboard/server/jobs.py training-dashboard/server/tests/test_stages.py
git commit -m "feat(dashboard): StageJob subprocess runner + P0 summary parser"
```

### Task C2: Wire stage runs through the runner + protocol kind

**Files:**
- Modify: `training-dashboard/server/runner.py`
- Modify: `training-dashboard/server/protocol.py`
- Modify: `training-dashboard/server/app.py`
- Test: `training-dashboard/server/tests/test_runner.py` (add a case)

- [ ] **Step 1: Write the failing test** (runner drives a stage; log_cb bridges to log events)

Append to `training-dashboard/server/tests/test_runner.py`:

```python
def test_runner_runs_a_stage_job_and_emits_metrics():
    from server.runner import Runner
    events = []
    r = Runner(broadcast=events.append, status_interval=0.0)
    # a fake stage: resolve_job is monkeypatched via the kind="stage" path
    import server.runner as rmod
    class _FakeStage:
        name = "train_p0"
        def run(self, config, progress_cb, should_stop, log_cb=None):
            if log_cb: log_cb("info", "matched rows=10")
            return {"a_roc": 0.6, "b_roc": 0.63}
    rmod.resolve_job = lambda name, kind="trainer": _FakeStage()
    assert r.start("train_p0", {}, kind="stage") is True
    r.join(2.0)
    kinds = [e.get("type") for e in events]
    assert "metrics" in kinds
    metrics = [e for e in events if e.get("type") == "metrics"][0]
    assert metrics["report"]["b_roc"] == 0.63
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_runner.py::test_runner_runs_a_stage_job_and_emits_metrics -v`
Expected: FAIL — `start()` takes no `kind`, and `resolve_job` not imported.

- [ ] **Step 3: Generalize runner.py**

Change the import and the `start`/`_run` signatures. Replace `from .trainers import get_trainer` with `from .jobs import resolve_job`. Then:

```python
    def start(self, name: str, config: Optional[dict] = None,
              kind: str = "trainer") -> bool:
        with self._lock:
            if self._running:
                already = True
            else:
                already = False
                self._running = True
                self._stop_flag.clear()
        if already:
            self._emit(protocol.log_event("a run is already in progress", level="warn"))
            return False
        self._thread = threading.Thread(
            target=self._run, args=(name, config or {}, kind), daemon=True)
        try:
            self._thread.start()
        except Exception:
            with self._lock:
                self._running = False
            self._emit(protocol.error_event("failed to start worker thread"))
            return False
        return True
```

In `_run`, change the signature to `def _run(self, name: str, config: dict, kind: str) -> None:`, replace the `f"starting {trainer_name} trainer"` log with `f"starting {name} ({kind})"`, and resolve+call the job, passing `log_cb` only to stages:

```python
            job = resolve_job(name, kind)
            if kind == "stage":
                report = job.run(config, progress_cb, self.should_stop,
                                 log_cb=lambda lvl, m: self._emit(protocol.log_event(m, level=lvl)))
            else:
                report = job.run(config, progress_cb, self.should_stop)
```

- [ ] **Step 4: Add `kind` to protocol StartCommand**

In `training-dashboard/server/protocol.py`, add to `StartCommand`:

```python
class StartCommand(BaseModel):
    command: Literal["start"]
    trainer: str  # job name (trainer or stage)
    kind: Literal["trainer", "stage"] = "trainer"
    config: Optional[StartConfig] = None
```

- [ ] **Step 5: Pass kind in app.py**

In `_handle_message`, change the StartCommand branch:

```python
    if isinstance(command, protocol.StartCommand):
        config = command.config.model_dump() if command.config else {}
        runner.start(command.trainer, config, kind=command.kind)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests -v`
Expected: PASS (existing runner/protocol/trainer tests + the new stage case).

- [ ] **Step 7: Commit**

```bash
git add training-dashboard/server/runner.py training-dashboard/server/protocol.py training-dashboard/server/app.py training-dashboard/server/tests/test_runner.py
git commit -m "feat(dashboard): drive StageJobs through the runner via job kind"
```

### Task C3: P0 run-history endpoint + append on completion

**Files:**
- Modify: `training-dashboard/server/stages.py` (append history in parser path)
- Modify: `training-dashboard/server/app.py` (`/api/p0/runs`)
- Test: `training-dashboard/server/tests/test_stages.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `training-dashboard/server/tests/test_stages.py`:

```python
def test_append_and_read_p0_history(tmp_path, monkeypatch):
    import server.stages as st
    monkeypatch.setattr(st, "P0_HISTORY", str(tmp_path / "p0_runs.jsonl"))
    st.append_p0_run({"a_roc": 0.60, "b_roc": 0.63, "origin_years": [2016, 2017]})
    st.append_p0_run({"a_roc": 0.59, "b_roc": 0.61, "origin_years": [2016, 2017, 2018]})
    runs = st.read_p0_runs()
    assert len(runs) == 2 and runs[0]["b_roc"] == 0.63 and "ts" in runs[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_stages.py::test_append_and_read_p0_history -v`
Expected: FAIL — `append_p0_run` undefined.

- [ ] **Step 3: Add history helpers to stages.py**

```python
import json
import time

P0_HISTORY = "data/processed/p0_runs.jsonl"


def append_p0_run(report: dict) -> None:
    if not report or "a_roc" not in report:
        return
    row = {"ts": time.time(), **report}
    os.makedirs(os.path.dirname(P0_HISTORY), exist_ok=True)
    with open(P0_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def read_p0_runs() -> list[dict]:
    if not os.path.exists(P0_HISTORY):
        return []
    out = []
    with open(P0_HISTORY, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return list(reversed(out))
```

Wire the append into the P0 parser so a real run records itself: at the end of `parse_p0_summary`, before `return out`, add:

```python
    if "a_roc" in out:
        append_p0_run(out)
```

- [ ] **Step 4: Add the endpoint to app.py**

```python
from .stages import read_p0_runs

@app.get("/api/p0/runs")
async def p0_runs() -> dict:
    return {"runs": read_p0_runs()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests/test_stages.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add training-dashboard/server/stages.py training-dashboard/server/app.py training-dashboard/server/tests/test_stages.py
git commit -m "feat(dashboard): persist + serve P0 run history"
```

### Task C4: Web — startStage command + LabPanel

**Files:**
- Modify: `training-dashboard/web/src/protocol.ts`, `training-dashboard/web/src/ws.ts`
- Create: `training-dashboard/web/src/tabs/LabPanel.tsx`

- [ ] **Step 1: Extend protocol.ts + ws.ts**

In `protocol.ts`, add `kind` to `StartCommand`:

```ts
export interface StartCommand {
  command: 'start'
  trainer: string
  kind?: 'trainer' | 'stage'
  config?: { total_steps?: number; speed_per_sec?: number; n_estimators?: number; max_depth?: number; learning_rate?: number }
}
```

In `ws.ts`, add a method on `WsClient`:

```ts
  startStage(name: string): boolean {
    return this.send({ command: 'start', trainer: name, kind: 'stage' })
  }
```

- [ ] **Step 2: Write the LabPanel result-gate test**

```tsx
// training-dashboard/web/src/tabs/LabPanel.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { p0Gate } from './LabPanel'

describe('p0Gate', () => {
  it('green when A recovered and B beats A', () => {
    expect(p0Gate(0.62, 0.66).tone).toBe('good')
  })
  it('amber honest-null when A recovered but B ~= A', () => {
    expect(p0Gate(0.61, 0.612).tone).toBe('null')
  })
  it('red structurally-broken when A stays random', () => {
    expect(p0Gate(0.50, 0.51).tone).toBe('broken')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd training-dashboard/web && bunx vitest run src/tabs/LabPanel.test.tsx`
Expected: FAIL — cannot find `./LabPanel` / `p0Gate`.

- [ ] **Step 4: Write LabPanel.tsx**

```tsx
// training-dashboard/web/src/tabs/LabPanel.tsx
import { useEffect, useState } from 'react'
import {
  fetchGefsStatus, startGefs, stopGefs, fetchP0Runs, gefsPercent,
  type GefsStatus, type P0Run,
} from '../lab'

export function p0Gate(aRoc: number, bRoc: number): { tone: 'good' | 'null' | 'broken'; text: string } {
  if (aRoc < 0.58) return { tone: 'broken', text: 'A still ~random — evaluation underpowered/broken; more data or pivot' }
  if (bRoc - aRoc >= 0.01) return { tone: 'good', text: 'A recovered and forecast covariate adds lift — real P0 signal' }
  return { tone: 'null', text: 'A recovered but B ≈ A — honest null; forecast covariate does not help here' }
}

export default function LabPanel({ connected }: { connected: boolean }) {
  const [gefs, setGefs] = useState<GefsStatus | null>(null)
  const [runs, setRuns] = useState<P0Run[]>([])

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const [g, r] = await Promise.all([fetchGefsStatus(), fetchP0Runs()])
        if (alive) { setGefs(g); setRuns(r) }
      } catch { /* server down; keep last */ }
    }
    void tick()
    const id = setInterval(tick, 4000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const latest = runs[0]
  const gate = latest ? p0Gate(latest.a_roc, latest.b_roc) : null

  return (
    <div className="lab">
      <section className="card lab-card">
        <div className="lab-head">
          <h3>GEFS reforecast pull</h3>
          <div className="lab-actions">
            <button className="btn" disabled={gefs?.running} onClick={() => void startGefs()}>Start / resume</button>
            <button className="btn" disabled={!gefs?.running} onClick={() => void stopGefs()}>Stop</button>
          </div>
        </div>
        {gefs ? (
          <>
            <div className="lab-progress">
              <div className="lab-bar" style={{ width: `${gefsPercent(gefs)}%` }} />
            </div>
            <p className="lab-stat">
              <strong>{gefs.inits}/{gefs.target}</strong> inits · {gefs.rows.toLocaleString()} rows ·
              humidity {gefs.fc_spfh_pct}% · {gefs.running ? '● running' : 'idle'}
            </p>
            <p className="lab-years">{Object.entries(gefs.by_year).map(([y, n]) => `${y}:${n}`).join('  ')}</p>
            <pre className="lab-log">{gefs.log_tail}</pre>
          </>
        ) : <p className="subtitle">loading…</p>}
      </section>

      <section className="card lab-card">
        <div className="lab-head">
          <h3>P0 forecast-covariate measurement</h3>
          <button className="btn btn-primary" disabled={!connected}
            onClick={() => window.dispatchEvent(new CustomEvent('lab-run-p0'))}>
            Run P0
          </button>
        </div>
        {latest && gate ? (
          <>
            <table className="lab-table">
              <thead><tr><th>model</th><th>ROC</th><th>PR-AUC lift</th></tr></thead>
              <tbody>
                <tr><td>A antecedent</td><td>{latest.a_roc.toFixed(3)}</td><td>{latest.a_lift.toFixed(2)}×</td></tr>
                <tr><td>B + GEFS forecast</td><td>{latest.b_roc.toFixed(3)}</td><td>{latest.b_lift.toFixed(2)}×</td></tr>
              </tbody>
            </table>
            <div className={`lab-gate gate-${gate.tone}`}>{gate.text}</div>
            <p className="lab-meta">matched {latest.matched_rows?.toLocaleString?.() ?? '—'} rows ·
              years {latest.origin_years?.join(', ')} · pos {(latest.pos_rate * 100).toFixed(1)}%</p>
          </>
        ) : <p className="subtitle">No P0 run yet — click “Run P0”.</p>}
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Wire the Run-P0 button to the WS client**

The Run-P0 button dispatches a window event; handle it in `App.tsx` (which owns the WS client) by adding, inside the existing mount `useEffect`, a listener that calls `client.startStage('train_p0')`:

```tsx
    const runP0 = () => clientRef.current?.startStage('train_p0')
    window.addEventListener('lab-run-p0', runP0)
    // ...and in the cleanup return:  window.removeEventListener('lab-run-p0', runP0)
```

(LightGBM/stage progress + completion already flow through the shared WS into the Train tab's status/log; the Lab table refreshes from `/api/p0/runs` on its 4 s poll once the stage finishes and appends history.)

- [ ] **Step 6: Add Lab styling**

Append to `training-dashboard/web/src/App.css`:

```css
.lab { display: flex; flex-direction: column; gap: 16px; }
.lab-card { padding: 16px; }
.lab-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.lab-actions { display: flex; gap: 8px; }
.lab-progress { height: 8px; border-radius: 6px; background: rgba(241,236,227,.1); overflow: hidden; margin: 10px 0; }
.lab-bar { height: 100%; background: linear-gradient(90deg,#ff6a3d,#ffc24b); transition: width .4s; }
.lab-stat { margin: 4px 0; } .lab-years { opacity: .6; font-family: var(--mono, monospace); font-size: 12px; }
.lab-log { background: #0b0a0d; border: 1px solid rgba(241,236,227,.1); border-radius: 8px; padding: 8px;
  font-size: 11px; max-height: 140px; overflow: auto; white-space: pre-wrap; }
.lab-table { width: 100%; border-collapse: collapse; margin: 8px 0; }
.lab-table th, .lab-table td { text-align: left; padding: 4px 8px; border-bottom: 1px solid rgba(241,236,227,.08); }
.lab-gate { border-radius: 8px; padding: 10px 12px; margin: 8px 0; font-weight: 600; }
.gate-good { background: rgba(90,209,138,.16); border: 1px solid #5ad18a; }
.gate-null { background: rgba(255,194,75,.14); border: 1px solid #ffc24b; }
.gate-broken { background: rgba(229,84,84,.16); border: 1px solid #e55454; }
.lab-meta { opacity: .65; font-size: 12px; }
```

- [ ] **Step 7: Run tests + type-check**

Run: `cd training-dashboard/web && bunx tsc --noEmit && bunx vitest run`
Expected: all PASS (TabBar, lab, LabPanel, Eta, ws).

- [ ] **Step 8: Commit**

```bash
git add training-dashboard/web/src/protocol.ts training-dashboard/web/src/ws.ts training-dashboard/web/src/tabs/LabPanel.tsx training-dashboard/web/src/tabs/LabPanel.test.tsx training-dashboard/web/src/App.tsx training-dashboard/web/src/App.css
git commit -m "feat(dashboard): Lab tab — GEFS monitor + P0 runner with decision gate"
```

---

## Final verification

- [ ] **Server:** `cd C:/Users/ASUS/Heatwave_AI && .venv/Scripts/python.exe -m pytest training-dashboard/server/tests -q` — all green.
- [ ] **Web:** `cd training-dashboard/web && bunx tsc --noEmit && bunx vitest run` — all green.
- [ ] **Manual smoke (uses the LIVE GEFS pull as real data):** start the server, open `http://127.0.0.1:5173`, click **Lab** → GEFS card shows `N/124` advancing every 4 s and the log tail; click **Run P0** → Train-tab log streams `train_p0`, then the Lab table + gate populate from `/api/p0/runs`. Switch to **Train** → unchanged from before.
- [ ] Confirm the **decision gate** matches `docs/MODEL-IMPROVEMENT.md`: A ROC ≥ ~0.60 with B−A ≥ 0.01 → green; A ≥ 0.60, B≈A → amber null; A < 0.58 → red.

## Notes / guardrails carried from the spec
- Single-slot runner unchanged: a P0 stage and a training run can't overlap (by design). The GEFS pull is the only concurrent process (detached, I/O-bound).
- No production mutation in this phase (Promote lives in the Ops plan). Lab only reads + runs experiments.
- GEFS archive ends 2019 → the gate copy frames a null honestly; do not imply more data beyond 2019 is available.
- Follow-up plans: **Pipeline tab** (more StageJobs: build_dataset, run_daily_forecast), **Forecast tab** (map + time-series), **Ops tab** (Promote + daily-runner/LINE health).
```
