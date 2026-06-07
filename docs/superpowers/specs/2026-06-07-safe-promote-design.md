# Safe Promote (Maintainer Inner-Loop, Sub-project 1 of 3) — Design

**Date:** 2026-06-07
**Vision:** a production-grade, easy-to-maintain maintainer loop —
*train in the dashboard → promote safely → test on a local-prod stack (isolated)
→ one-click deploy*. This spec covers **sub-project 1: Safe Promote** (the
foundation). Sub-2 (local-prod staging test) and sub-3 (one-click deploy) follow.

## 1. Problem
Promotion (dashboard model → `models/heatwave_model.pkl`) exists in **two places
that disagree**:
- `training-dashboard/server/ops_api.py::promote_model` — used by the dashboard
  OpsPanel. **No coverage guard, no backup, no rollback.** A click can silently
  replace the 77-province production model with a 20-province one, unrecoverably.
- `scripts/promote_model.py` (CLI) — HAS a province-coverage guard, backup, and
  `--dry-run`, but is a *separate* implementation.

Two implementations = drift + double-maintenance. Not production-grade.

## 2. Goal / non-goals
**Goal:** one shared, tested promotion core used by BOTH the dashboard and the CLI,
with a coverage guard, automatic backup, and rollback.
**Non-goals (later sub-projects):** generating/serving candidate forecasts to a
local staging store (sub-2); pushing/redeploying to real production + regenerating
Supabase (sub-3).

## 3. Architecture

### 3.1 `src/promote.py` (NEW — the single source of truth)
Pure file + JSON operations (no model load needed — provenance comes from the
sidecar), all paths injectable so the dashboard and tests pass their own.

- `promote(name, *, dashboard_dir, prod_model_path, model_card_path, force=False, dry_run=False) -> dict`
  1. Whitelist `name` against existing `dashboard_dir/*.pkl` (reject otherwise).
  2. Read candidate sidecar `name.json` → `class`, `model_version`, `metrics.n_provinces`.
  3. **Coverage guard:** if `force` is False AND both candidate and production
     `n_provinces` are known AND candidate < production → **refuse** (return
     `{"ok": False, "reason": ...}`). If either is unknown → **allow with a warning**
     (block only a *known* regression; never silently shrink coverage).
  4. Build the new model card (promoted_from / promoted_at / source_metrics /
     n_provinces / class / model_version).
  5. `dry_run` → return the planned card + warnings, change nothing.
  6. Otherwise: back up existing `prod_model_path` and `model_card_path` to
     `*.bak-<UTCstamp>`; copy candidate `.pkl` into place; write the card.
  7. Return `{"ok": True, "promoted": name, "backups": [...], "warnings": [...]}`.
- `rollback(*, prod_model_path, model_card_path) -> dict`
  Restore the most-recent `*.bak-<stamp>` for both files; return what was restored
  (or `{"ok": False}` if no backup exists).
- `latest_backup(path) -> str | None` helper.

### 3.2 `training-dashboard/server/ops_api.py` (refactor)
- `POST /api/ops/promote` calls `src.promote.promote(...)`, passing the module
  path constants (`DASHBOARD_DIR`, `PRODUCTION_MODEL_PATH`, `MODEL_CARD_PATH`) so
  existing test monkeypatching still works. Accepts optional `force`. On guard
  refusal return HTTP 409 with the reason. Response surfaces `warnings`.
- `POST /api/ops/rollback` (NEW) → `src.promote.rollback(...)`.

### 3.3 `scripts/promote_model.py` (refactor)
Becomes a thin CLI over `src.promote.promote` / `rollback` (keep `--model`,
`--dry-run`, `--force`; add `--rollback`). Drops its duplicated logic.

### 3.4 Web — OpsPanel
Add a **Rollback** action and show guard refusals / warnings as a toast. (Minimal;
the richer "Test on Local" + "Deploy" buttons are sub-2/sub-3.)

## 4. Data flow
`OpsPanel "Promote"` → `POST /api/ops/promote {name, force?}` →
`src.promote.promote()` → guard → backup → copy → write card → result/warnings.
`OpsPanel "Rollback"` → `POST /api/ops/rollback` → restore latest backups.

## 5. Error handling
- Unknown model name → 404 (dashboard) / clear error (CLI).
- Known coverage regression without `force` → refuse (HTTP 409 / non-zero exit),
  no files touched.
- Backup write failure → abort before copy (never leave prod half-replaced).
- Rollback with no backup → `{"ok": False}` / clear message.

## 6. Testing (TDD)
`tests/test_promote.py` (core, tmp_path, dummy files — no joblib):
- guard refuses a known regression (cand 20 < prod 77) without force;
- guard allows + warns when coverage unknown (no n_provinces);
- `force=True` overrides the guard;
- promote backs up existing prod files and copies the candidate + writes card;
- `dry_run` changes nothing;
- `rollback` restores the latest backup; no-backup returns ok=False.
Keep `training-dashboard/server/tests/test_ops_api.py` green (promote path now
delegates; add a rollback test).

## 7. Success criteria
1. Dashboard and CLI promote via ONE core (`src/promote.py`); no duplicated logic.
2. A known coverage regression is blocked (unless forced); every promote is backed
   up; rollback works.
3. All new + existing tests pass.

## 8. Follow-ups (next sub-projects)
- **Sub-2 Local-prod test:** `run_daily_forecast --staging` → local
  `forecast_store_staging.json`; backend reads it when `HEATWAVE_FORECAST_FILE`
  is set (else Supabase); a dashboard "Test on Local" action.
- **Sub-3 One-click deploy:** git push (Render auto-deploy) + regenerate live
  Supabase with the promoted model + rollback; confirmation-gated.
