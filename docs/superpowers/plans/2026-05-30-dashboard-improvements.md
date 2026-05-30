# Heatwave Training Dashboard — Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard from a "training monitor" into a fast, traceable **experiment loop** — short idea→result time, every result reproducible.

**Architecture:** Local-only dev tool (FastAPI `:8000` + Vite `:5173`). Trainers run in a worker thread, read `data/processed/dataset.parquet`, and report progress over WebSocket. Improvements are additive: cache the expensive feature frame, log every run, give live progress + hyperparameters, and harden evaluation. No changes to the Elysia product backend.

**Tech Stack:** Python 3.12, pandas, scikit-learn/imbalanced-learn/xgboost/catboost/lightgbm, FastAPI, pydantic; React + TypeScript + Vite (bun); pytest + vitest.

**Run commands (from repo root):**
- Server tests: `.venv\Scripts\python.exe -m pytest training-dashboard/server/tests -q`
- ML tests: `.venv\Scripts\python.exe -m pytest tests -q`
- Web: `cd training-dashboard/web && bun run build && bunx vitest run`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `pipeline/frame_cache.py` (new) | Hash a dataset+horizons and cache the built forecasting frame |
| `pipeline/train.py` (modify) | `train_model(..., frame=None)` to accept a prebuilt frame |
| `pipeline/run_log.py` (new) | Append/read run records (`experiments/runs.jsonl`) |
| `training-dashboard/server/trainers/sklearn_models.py` (modify) | Use cached frame; live heartbeat; hyperparam overrides; log run |
| `training-dashboard/server/trainers/lgbm.py` (modify) | Use cached frame; log run |
| `training-dashboard/server/protocol.py` (modify) | Extend `StartConfig` with optional hyperparameters |
| `training-dashboard/server/app.py` (modify) | `GET /api/runs`, `POST /api/promote/{name}` |
| `src/model_zoo.py` (modify) | `make_model(name, spw, **overrides)` |
| `scripts/bakeoff.py`, `scripts/model_report.py` (modify) | Use cached frame; CV helper |
| `evaluation/cv.py` (new) | Rolling-origin time-series CV |
| `training-dashboard/web/src/components/Controls.tsx` (modify) | Hyperparameter inputs |
| `training-dashboard/web/src/components/RunHistory.tsx` (new) | Run-history table |

---

## Phase 1 — Frame caching (biggest speed lever)

Every `Start` rebuilds the ~1.78M-row forecasting frame from parquet. Cache it keyed by the dataset file signature + horizons so repeat runs skip straight to `fit`.

### Task 1: Frame cache module

**Files:**
- Create: `pipeline/frame_cache.py`
- Test: `tests/test_frame_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_frame_cache.py
import numpy as np, pandas as pd
from pipeline.frame_cache import cached_build_frames, frame_cache_key
from pipeline.train import build_frames
from tests.test_train import _synth_dataset  # reuse the synthetic dataset


def test_cached_frame_matches_build_frames(tmp_path):
    ds = _synth_dataset()
    ds.to_parquet(tmp_path / "ds.parquet")
    direct = build_frames(ds, horizons=range(1, 4))
    cached = cached_build_frames(str(tmp_path / "ds.parquet"), horizons=range(1, 4),
                                 cache_dir=str(tmp_path / "cache"))
    pd.testing.assert_frame_equal(direct.reset_index(drop=True), cached.reset_index(drop=True))


def test_second_call_hits_cache(tmp_path):
    ds = _synth_dataset(); ds.to_parquet(tmp_path / "ds.parquet")
    key = frame_cache_key(str(tmp_path / "ds.parquet"), range(1, 4))
    cache_dir = tmp_path / "cache"
    cached_build_frames(str(tmp_path / "ds.parquet"), range(1, 4), cache_dir=str(cache_dir))
    assert (cache_dir / f"{key}.parquet").exists()  # cache written


def test_cache_invalidates_when_dataset_changes(tmp_path):
    p = tmp_path / "ds.parquet"
    _synth_dataset(seed=0).to_parquet(p)
    k1 = frame_cache_key(str(p), range(1, 4))
    _synth_dataset(seed=1).to_parquet(p)  # rewrite -> new mtime/size
    k2 = frame_cache_key(str(p), range(1, 4))
    assert k1 != k2
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_frame_cache.py -q`
Expected: FAIL (`No module named pipeline.frame_cache`).

- [ ] **Step 3: Implement**

```python
# pipeline/frame_cache.py
"""Cache the (expensive) forecasting frame keyed by dataset signature + horizons.

The frame is a pure function of dataset.parquet content + horizons, so we key on
a cheap signature (file size + mtime_ns + horizons) -- rebuilding the dataset
changes mtime and invalidates the cache automatically.
"""
import hashlib
import os

import pandas as pd

from pipeline.train import build_frames

DEFAULT_CACHE_DIR = "data/processed/_frame_cache"


def frame_cache_key(dataset_path: str, horizons) -> str:
    st = os.stat(dataset_path)
    sig = f"{os.path.abspath(dataset_path)}|{st.st_size}|{st.st_mtime_ns}|{tuple(horizons)}"
    return hashlib.sha1(sig.encode()).hexdigest()[:16]


def cached_build_frames(dataset_path: str, horizons=range(1, 8),
                        cache_dir: str = DEFAULT_CACHE_DIR) -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{frame_cache_key(dataset_path, horizons)}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    ds = pd.read_parquet(dataset_path)
    if "lat" not in ds.columns:
        prov = pd.read_csv("data/provinces.csv")[["id", "lat", "lon"]]
        ds = ds.merge(prov, left_on="province_id", right_on="id", how="left").drop(columns=["id"])
    frame = build_frames(ds, horizons=horizons)
    frame.to_parquet(path, index=False)
    return frame
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_frame_cache.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Gitignore the cache + commit**

Add `data/processed/` is already ignored (covers `_frame_cache`). Verify, then:

```bash
git add pipeline/frame_cache.py tests/test_frame_cache.py
git commit -m "feat: frame cache keyed by dataset signature + horizons"
```

### Task 2: Let `train_model` accept a prebuilt frame (so lgbm benefits)

**Files:**
- Modify: `pipeline/train.py` (the `train_model` signature + the `build_frames` call)
- Test: `tests/test_train.py`

- [ ] **Step 1: Add the failing test**

```python
# append to tests/test_train.py
def test_train_model_accepts_prebuilt_frame():
    ds = _synth_dataset()
    frame = build_frames(ds, horizons=range(1, 4))
    bundle, report = train_model(ds, horizons=range(1, 4), frame=frame)
    assert report["n_train"] > 0 and "test" in report
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_train.py::test_train_model_accepts_prebuilt_frame -q`
Expected: FAIL (`train_model() got an unexpected keyword argument 'frame'`).

- [ ] **Step 3: Implement** — in `pipeline/train.py`, change the signature and the build line:

```python
def train_model(dataset, horizons=range(1, 8),
                train_end=2023, val_year=2024, test_year=2025,
                progress_cb=None, frame=None):
    ...
    frame = build_frames(dataset, horizons=horizons) if frame is None else frame
```

- [ ] **Step 4: Run the full train tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_train.py -q`
Expected: PASS (all, incl. the new one). Confirms backward compatibility (`frame=None` default unchanged).

- [ ] **Step 5: Commit**

```bash
git add pipeline/train.py tests/test_train.py
git commit -m "feat: train_model accepts an optional prebuilt frame"
```

### Task 3: Use the cache in the dashboard trainers + scripts

**Files:**
- Modify: `training-dashboard/server/trainers/sklearn_models.py`, `training-dashboard/server/trainers/lgbm.py`, `scripts/bakeoff.py`, `scripts/model_report.py`

- [ ] **Step 1:** In `sklearn_models.py` `run()`, replace the load+`build_frames` block with:

```python
from pipeline.frame_cache import cached_build_frames
...
progress_cb(2, TOTAL, "building/loading forecasting features (cached)")
frame = cached_build_frames(DATASET_PATH, horizons=range(1, 8))
feats = feature_columns(frame)
```
(Remove the now-unused `pd.read_parquet(DATASET_PATH)` + merge + `build_frames` in this trainer; `n_provinces` can come from `frame["province_id"].nunique()`.)

- [ ] **Step 2:** In `lgbm.py` `run()`, build the frame from cache and pass it through:

```python
from pipeline.frame_cache import cached_build_frames
...
frame = cached_build_frames(DATASET_PATH, horizons=range(1, 8))
bundle, report = train_model(pd.read_parquet(DATASET_PATH), progress_cb=_progress, frame=frame)
```
(LightGBM still reports per-round progress via `_progress`; `train_model` now skips the rebuild.)

- [ ] **Step 3:** In `scripts/bakeoff.py` and `scripts/model_report.py`, replace the explicit `pd.read_parquet`+merge+`build_frames` with `cached_build_frames(DATASET, horizons=HORIZONS)`.

- [ ] **Step 4: Verify** — run a trainer twice; the second is much faster.

Run:
```
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'training-dashboard'); sys.path.insert(0,'.'); import time; from server.trainers import get_trainer
for i in (1,2):
    t=time.time(); get_trainer('xgboost').run({}, lambda *a: None, lambda: False); print('run', i, round(time.time()-t,1),'s')"
```
Expected: run 2 noticeably faster than run 1 (frame served from cache).

- [ ] **Step 5:** Re-run suites and commit.

```bash
.venv\Scripts\python.exe -m pytest training-dashboard/server/tests tests -q   # expect all pass
git add training-dashboard/server/trainers/sklearn_models.py training-dashboard/server/trainers/lgbm.py scripts/bakeoff.py scripts/model_report.py
git commit -m "perf: dashboard trainers + scripts use the cached forecasting frame"
```

---

## Phase 2 — Run history (traceability)

Append every dashboard run to `experiments/runs.jsonl` and surface it. Makes "what did I try and what happened" answerable, and becomes the single source feeding the leaderboard.

### Task 4: Run-log module

**Files:**
- Create: `pipeline/run_log.py`
- Test: `tests/test_run_log.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_run_log.py
from pipeline.run_log import append_run, read_runs


def test_append_and_read(tmp_path):
    p = tmp_path / "runs.jsonl"
    append_run({"trainer": "xgboost", "f2": 0.53}, path=str(p))
    append_run({"trainer": "lgbm", "f2": 0.56}, path=str(p))
    runs = read_runs(path=str(p))
    assert len(runs) == 2
    assert runs[0]["trainer"] == "xgboost"
    assert all("ts" in r for r in runs)  # timestamp auto-added
```

- [ ] **Step 2: Run / expect fail.** `.venv\Scripts\python.exe -m pytest tests/test_run_log.py -q`

- [ ] **Step 3: Implement**

```python
# pipeline/run_log.py
"""Append-only run history (one JSON object per line)."""
import json
import os
from datetime import datetime, timezone

DEFAULT_PATH = "experiments/runs.jsonl"


def append_run(entry: dict, path: str = DEFAULT_PATH) -> dict:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def read_runs(path: str = DEFAULT_PATH) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
```

- [ ] **Step 4: Run / expect pass.** Then commit:

```bash
git add pipeline/run_log.py tests/test_run_log.py
git commit -m "feat: append-only run history (experiments/runs.jsonl)"
```

### Task 5: Log each dashboard run

**Files:** Modify `training-dashboard/server/trainers/sklearn_models.py`, `lgbm.py`

- [ ] **Step 1:** After computing `report` and saving the model, append a compact record:

```python
from pipeline.run_log import append_run
...
append_run({"trainer": self.name,
            "f2": report.get("f2"), "pr_auc": report.get("pr_auc"),
            "brier_skill_score": report.get("brier_skill_score"),
            "threshold": report.get("threshold"),
            "n_provinces": report.get("n_provinces"),
            "config": config or {}})
```
(Do the same in `lgbm.py` with its `report`.)

- [ ] **Step 2: Verify** — run a trainer, then `read_runs()` shows the row. Commit.

```bash
git add training-dashboard/server/trainers/sklearn_models.py training-dashboard/server/trainers/lgbm.py
git commit -m "feat: trainers append each run to the run history"
```

### Task 6: `GET /api/runs` + RunHistory UI

**Files:** Modify `training-dashboard/server/app.py`; create `training-dashboard/web/src/components/RunHistory.tsx`; modify `App.tsx`

- [ ] **Step 1:** Add the endpoint:

```python
from pipeline.run_log import read_runs

@app.get("/api/runs")
async def runs() -> dict:
    return {"runs": list(reversed(read_runs()))[:100]}  # newest first
```

- [ ] **Step 2:** Add `RunHistory.tsx` — fetch `/api/runs`, render a compact table (ts, trainer, F2, PR-AUC, BSS) with a refresh button; mirror `LeaderboardPanel` styling.
- [ ] **Step 3:** Render `<RunHistory />` in `App.tsx` under `<LeaderboardPanel />`.
- [ ] **Step 4: Verify** — `bun run build`, reload, run a model, refresh run history → new row appears; 0 console errors. Commit.

```bash
git add training-dashboard/server/app.py training-dashboard/web/src/components/RunHistory.tsx training-dashboard/web/src/App.tsx
git commit -m "feat: run-history API + panel"
```

---

## Phase 3 — Live progress for non-LightGBM models

RF/MLP fit is a black box; the bar freezes at "fitting". Add an elapsed-time heartbeat thread during `fit` (works for every estimator), and per-iteration where the library supports it (XGBoost/CatBoost).

### Task 7: Heartbeat during fit

**Files:** Modify `training-dashboard/server/trainers/sklearn_models.py`

- [ ] **Step 1:** Wrap the `model.fit` call with a heartbeat thread that emits a status every ~1.5s with elapsed seconds, so the UI shows movement:

```python
import threading, time
...
done = threading.Event()
def _beat():
    t0 = time.time()
    while not done.wait(1.5):
        progress_cb(3, TOTAL, f"fitting {self.name}… {int(time.time()-t0)}s")
hb = threading.Thread(target=_beat, daemon=True); hb.start()
try:
    model.fit(Xtr, ytr)
finally:
    done.set(); hb.join(timeout=2)
```

- [ ] **Step 2:** For `xgboost`/`catboost`, pass a per-iteration callback into `make_model` overrides (optional refinement — see Task 9 overrides plumbing). Keep heartbeat as the universal baseline.
- [ ] **Step 3: Verify** — run `random_forest` in the browser; the status text ticks "fitting random_forest… Ns" while training. Commit.

```bash
git add training-dashboard/server/trainers/sklearn_models.py
git commit -m "feat: elapsed-time heartbeat during black-box model fits"
```

---

## Phase 4 — Hyperparameters from the UI

Let the user tweak key knobs per model and compare (the core of iteration).

### Task 8: Extend the protocol config

**Files:** Modify `training-dashboard/server/protocol.py`, `training-dashboard/web/src/protocol.ts`

- [ ] **Step 1:** Add optional fields to `StartConfig` (pydantic): `n_estimators: Optional[int]`, `max_depth: Optional[int]`, `learning_rate: Optional[float]`, `threshold_beta: Optional[float] = 2.0`. Mirror in `protocol.ts`.
- [ ] **Step 2: Commit.**

```bash
git add training-dashboard/server/protocol.py training-dashboard/web/src/protocol.ts
git commit -m "feat: hyperparameter fields on the start config"
```

### Task 9: `make_model` overrides + apply in trainer

**Files:** Modify `src/model_zoo.py`, `training-dashboard/server/trainers/sklearn_models.py`
- Test: `tests/test_model_zoo.py` (new)

- [ ] **Step 1: Failing test**

```python
# tests/test_model_zoo.py
from src.model_zoo import make_model

def test_overrides_apply():
    m = make_model("random_forest", 1.0, n_estimators=7)
    assert m.get_params()["n_estimators"] == 7
```

- [ ] **Step 2:** Implement `make_model(name, scale_pos_weight=1.0, **overrides)` — build the estimator, then apply `overrides` via `set_params` (map `n_estimators`/`max_depth`/`learning_rate` to each family's param names; for the MLP Pipeline, set on the `mlpclassifier` step). Run/pass. Commit.

- [ ] **Step 3:** In `sklearn_models.py`, pass `config`-derived overrides into `make_model(self.name, spw, **overrides)`.

```bash
git add src/model_zoo.py tests/test_model_zoo.py training-dashboard/server/trainers/sklearn_models.py
git commit -m "feat: per-run hyperparameter overrides"
```

### Task 10: Controls UI inputs

**Files:** Modify `training-dashboard/web/src/components/Controls.tsx`
- [ ] Add small numeric inputs (n_estimators, max_depth, learning_rate) shown for real trainers; include them in the `start` config. `bun run build`; verify a run with a changed value lands in the run-history `config`. Commit.

---

## Phase 5 — Trustworthy evaluation (time-series CV)

Single val/test year has high variance. Add rolling-origin CV and report mean±std.

### Task 11: CV helper

**Files:** Create `evaluation/cv.py`; Test: `tests/test_cv.py`
- [ ] **Step 1: Failing test** — `rolling_origin_folds(years=[2021,2022,2023,2024,2025])` yields ordered (train_max, test_year) folds with no future leakage:

```python
# tests/test_cv.py
from evaluation.cv import rolling_origin_folds
def test_folds_are_causal():
    folds = rolling_origin_folds(first_test=2023, last_test=2025)
    assert folds == [(2022, 2023), (2023, 2024), (2024, 2025)]
    for train_max, test_yr in folds:
        assert train_max < test_yr
```

- [ ] **Step 2: Implement** `rolling_origin_folds(first_test, last_test)` returning `[(test-1, test), ...]`. Run/pass.
- [ ] **Step 3:** Add a `--cv` path to `scripts/bakeoff.py` that, per model, trains on `year<=train_max`, evaluates on `test_yr` across folds, and reports `f2_mean`, `f2_std`. Commit.

```bash
git add evaluation/cv.py tests/test_cv.py scripts/bakeoff.py
git commit -m "feat: rolling-origin time-series CV for the bake-off"
```

---

## Phase 6 — Closing the loop (lighter / partly documented)

### Task 12: Promote a dashboard model to production

**Files:** Modify `training-dashboard/server/app.py`
- [ ] Add `POST /api/promote/{name}` (whitelisted, like `/api/model-file/{name}`): copy `models/dashboard/<name>.pkl` → `models/heatwave_model.pkl` and write `models/model_card.json` from the run record. Add a "Promote to production" button in the run-history/leaderboard UI. Verify the copied file loads via `joblib.load`. Commit.

### Task 13: Coverage + label fidelity (already documented)

These are data tasks tracked in `docs/DATA.md` / `docs/PRODUCTION.md`; no new design needed:
- [ ] Expand dataset to all 77 provinces: re-run `scripts/build_full_dataset.py` across hourly windows → `train_production.py` → `bakeoff.py`.
- [ ] Evaluate the hourly-sWBGT label: build key provinces with `HEATWAVE_HOURLY=1`, re-run the bake-off, compare. Promote if it wins.

### Task 14: Format the live "final metrics" panel

**Files:** Modify `training-dashboard/web/src/components/MetricsPanel.tsx`
- [ ] Render the headline scalars (F2/PR-AUC/BSS/precision/recall) as labeled stat chips instead of the raw dict tree; keep raw nested values collapsible. `bun run build`; verify; commit.

---

## Definition of Done
- All new tests pass; full `pytest` and `vitest` green; `bun run build` clean; in-browser 0 console errors.
- Repeat training runs are visibly faster (frame cache); every run appears in run history with its config + metrics.
- A user can change a hyperparameter in the UI, run, and see the result tracked; CV gives mean±std; a chosen model can be promoted to `models/heatwave_model.pkl`.

## Sequencing & rationale
1 → 2 first (speed unblocks all later iteration), then 4 (traceability), then 3 (live feedback), then 8–10 (hyperparams), then 11 (trust), then 6 (loop closure). Phases are independent enough to ship one at a time; each ends green and useful.
