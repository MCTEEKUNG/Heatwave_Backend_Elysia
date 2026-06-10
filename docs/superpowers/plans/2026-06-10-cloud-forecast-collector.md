# Cloud Forecast Collector (Supabase) — Spec + Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the P0 forward-collector runs in the cloud daily, so forecast issue dates are never lost to the laptop being off; local and cloud collections union into one deduplicated store.

**Architecture (user-approved 2026-06-10):** new `heatwave.forecast_store` Supabase table (PK = province_id, issue_date, target_date) is the durable store. `collect_forecast.py` gains an opt-in DB push (active only when `DATABASE_URL` is in the env — i.e. CI; local behavior unchanged). A new GitHub-Actions cron on master (same pattern as the GREEN `daily-forecast.yml`: schedule on default branch, checkout feat branch, existing `DATABASE_URL` secret) runs it at ~07:45 Asia/Bangkok. A two-way `sync_forecast_store.py` uploads local-only rows (seeds the existing 4,851) and writes the union back to `data/processed/forecast_store.parquet` for training. Idempotency is layered: collector no-ops per issue_date locally, DB PK + `ON CONFLICT DO NOTHING` in the cloud.

**Tech Stack:** psycopg v3 (pattern: `src/db_write.py`), pandas/pyarrow, GitHub Actions, `scripts/db_apply.py` for the migration, `src/openmeteo_client._get_with_retry` for CI-grade fetch resilience.

---

### Task A: Migration — `heatwave.forecast_store`

**Files:** Create `supabase/migrations/0002_forecast_store.sql`

- [ ] Write table DDL: columns matching the parquet schema (`province_id int REFERENCES heatwave.provinces(id)`, `issue_date date`, `target_date date`, `lead_k smallint`, `fc_tmax real`, `fc_rh real`, `fc_heat_index real`, `fc_soil_moisture real NULL`, `collected_at timestamptz DEFAULT now()`), `PRIMARY KEY (province_id, issue_date, target_date)`, `CHECK (target_date >= issue_date)` (lead 0 exists).
- [ ] Apply: `.venv\Scripts\python.exe scripts\db_apply.py supabase\migrations\0002_forecast_store.sql` → "applied".

### Task B: `src/forecast_store_db.py` (mirror of db_write.py)

**Files:** Create `src/forecast_store_db.py`; Test `tests/test_forecast_store_db.py`

- [ ] TDD: tests for `rows_for_upsert(df)` (pure: DataFrame → list[dict] with NaN→None) — NaN soil moisture becomes None; key columns preserved.
- [ ] Implement: `rows_for_upsert`, `upsert_rows(rows)` (lazy psycopg, executemany `INSERT … ON CONFLICT (province_id, issue_date, target_date) DO NOTHING`, returns inserted count), `fetch_df()` (SELECT * → DataFrame with ISO-string dates to match the parquet dtypes).
- [ ] `pytest tests/test_forecast_store_db.py -q` → pass; commit.

### Task C: collector — CI resilience + opt-in DB push

**Files:** Modify `scripts/collect_forecast.py`; Test `tests/test_collect_forecast.py`

- [ ] TDD: test that `collect(..., push_db=True)` calls the upsert hook with the new rows (monkeypatched fetch + hook); test that without DATABASE_URL main() does NOT push.
- [ ] Replace `requests.get` in `_fetch` with `openmeteo_client._get_with_retry` (429/5xx survival on shared CI IPs).
- [ ] In `collect()`: after writing parquet, if `os.environ.get("DATABASE_URL")` → `upsert_rows(rows_for_upsert(new))`, print count.
- [ ] Full `pytest tests/ -q` → 161+new pass; commit.

### Task D: `scripts/sync_forecast_store.py` (two-way sync, also the seeder)

**Files:** Create `scripts/sync_forecast_store.py`; Test `tests/test_sync_forecast_store.py`

- [ ] TDD: tests for pure `merge_stores(local_df, db_df)` — union without duplicate keys, local wins on identical keys, column order stable, empty-frame edges.
- [ ] Implement main(): load .env → read local parquet (tolerate missing) → upsert local rows to DB (seeds) → `fetch_df()` → `merge_stores` → write parquet → print summary.
- [ ] `pytest -q` → pass; commit.

### Task E: cron workflow on master (activation user-gated via PR)

**Files (worktree `..\Heatwave_AI_master-fix`, new branch `ci/collect-forecast-cron` from master):** Create `.github/workflows/collect-forecast.yml`

- [ ] Workflow: `schedule: "45 0 * * *"` (07:45 BKK) + `workflow_dispatch`, concurrency group, `timeout-minutes: 30`, checkout `ref: feat/clean-era5-ndvi-dataset`, python 3.12, `pip install "numpy>=1.24" "pandas>=2.0" "pyarrow>=14" "requests>=2.31" "psycopg[binary]>=3.1"`, run `python scripts/collect_forecast.py` with `DATABASE_URL: ${{ secrets.DATABASE_URL }}`.
- [ ] Push branch, `gh pr create` to master, do NOT merge (merge = activation; user-gated).

### Task F: seed + verify end-to-end

- [ ] Run `.venv\Scripts\python.exe scripts\sync_forecast_store.py` locally → uploads existing ~4,851 rows; re-run → "0 uploaded" (idempotent).
- [ ] Verify DB row count == parquet row count via a one-off query.

### Task G: docs, memory, push

- [ ] Update `docs/MODEL-IMPROVEMENT.md` P0 section: cloud collection staged (PR), residual laptop-off loss closes when merged.
- [ ] Commit + push feat branch; update memory files.

---

## Execution log — COMPLETED 2026-06-10 (inline, same session)

- Task A ✅ migration `0002_forecast_store.sql` applied to Supabase.
- Task B ✅ TDD: 4 tests → `src/forecast_store_db.py` (`6fb4d8a`).
- Task C ✅ TDD: 2 tests → DB-push hook + `_get_with_retry` fetch; full suite 167 passed (`21a70f4`).
- Task D ✅ TDD: 4 tests → `scripts/sync_forecast_store.py` (`00c7965`).
- Task F ✅ (run before E): seeded 4,851 rows / 9 issue dates; second run 0 uploaded (idempotent); DB count == parquet count by construction (down-fetch matched).
- Task E ✅ `collect-forecast.yml` on branch `ci/collect-forecast-cron` → **PR #11, NOT merged (merge = activation, user-gated)**.
- Task G ✅ docs + memory updated; final pytest 171 passed, bun test 40 pass.
