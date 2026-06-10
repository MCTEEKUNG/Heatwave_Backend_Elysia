# Project-Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every actionable finding from the 2026-06-10 project review (`docs/PROJECT-REVIEW.html`): the data-losing collector task (P1), the stale-route claim (P2), two stale PRs (P2), git hygiene + the dual-lineage trap (P3), and config.yaml confusion (P3).

**Architecture:** These are ops/hygiene fixes, not feature work. The riskiest discovery during planning: `master` and `feat/clean-era5-ndvi-dataset` share **no common ancestor** — master hosts the *active* GitHub-Actions daily-forecast cron (schedules only fire from the default branch) which checks out the feature branch for code. Therefore the original "merge to master" recommendation is REPLACED by: back up the branch, document the dual-lineage so nobody naive-merges, and defer unification to a deliberate migration.

**Tech Stack:** PowerShell `Register-ScheduledTask`, `gh` CLI, git, YAML comment edits.

---

## Pre-verified facts (gathered 2026-06-10, do not re-derive)

- `HeatwaveForecastCollect` task: Status Ready, **Logon Mode: Interactive only**, daily 08:00, action = `.venv\Scripts\python.exe scripts\collect_forecast.py`. Store has 9 issue dates over 11 days (2 lost).
- `git merge-base master HEAD` → **no common ancestor**. `master` additionally carries `Era5-data-2000-2026/*.nc` large binaries and the ACTIVE `.github/workflows/daily-forecast.yml` (timeout-minutes 75, `ref: feat/clean-era5-ndvi-dataset`); HEAD carries a DORMANT copy of the same workflow.
- Current branch backend (`src/index.ts`) has only `/`, `/api/health`, `/api/provinces`, `/api/forecast/province/:id`, `/api/forecast/map`, `/api/thresholds/:id`, one `.post` (LINE webhook). **No `/forecast/latest`** — the stale-route claim must be re-verified against `master` (what Render serves).
- PR #1 (`feat/eda-wbgt-year-split`, +3918/−174) touches the legacy `Heatwave-AI-TRAIN/` layout — superseded by the current flat `src/`+`pipeline/` rebuild (77-prov dataset, temporal split, sWBGT label already shipped).
- PR #2 (`claude/todo-implementation-xxPLO`, +37/−10) implements AsyncStorage settings persistence — **already present** in `HeatMAP-Frontend/hooks/useSettings.tsx` (lines 8, 114, 164–184) on the current branch.
- Untracked: `HeatMAP-Frontend/bun_test_out.txt` (junk), `docs/PROJECT-EXPLAINER.html` (keep), plus new `docs/PROJECT-REVIEW.html` and this plan.
- Test baseline: `pytest tests/ -q` → 161 passed; `bun test` → 40 pass, 0 fail.

---

### Task 1 (P1): Make the forecast collector survive missed 08:00 starts

**Files:** none (Windows Task Scheduler state only)

The collector is append-only and keyed by `(province_id, issue_date, target_date)`; re-running on the same day is safe. The fix is `StartWhenAvailable`: if the 08:00 occurrence is missed (laptop asleep/off), the task fires as soon as it next can.

- [ ] **Step 1: Confirm the collector is idempotent before allowing catch-up runs**

Run: `grep -n "issue_date" scripts/collect_forecast.py | head -20` and read the dedupe/append logic.
Expected: rows are deduplicated or keyed so a second run on the same `issue_date` does not duplicate data. If NOT idempotent, STOP and fix that first (separate task — do not register catch-up triggers on a non-idempotent job).

- [ ] **Step 2: Re-register the task with StartWhenAvailable (keep interactive logon — no password prompt)**

```powershell
$action = New-ScheduledTaskAction `
  -Execute "C:\Users\ASUS\Heatwave_AI\.venv\Scripts\python.exe" `
  -Argument "C:\Users\ASUS\Heatwave_AI\scripts\collect_forecast.py" `
  -WorkingDirectory "C:\Users\ASUS\Heatwave_AI"
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
  -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "HeatwaveForecastCollect" `
  -Action $action -Trigger $trigger -Settings $settings -Force
```

Expected: command echoes the registered task object, `State: Ready`.

- [ ] **Step 3: Verify the setting took**

Run:
```powershell
(Get-ScheduledTask -TaskName "HeatwaveForecastCollect").Settings.StartWhenAvailable
```
Expected: `True`

- [ ] **Step 4: Record the known residual limitation**

Append one line to `docs/MODEL-IMPROVEMENT.md` under the P0 data-engine section: days when the laptop never powers on are still lost; the durable fix is cloud collection (needs a persistence target for `forecast_store.parquet`, e.g. HF or Supabase) — tracked as follow-up, not done here.

- [ ] **Step 5: Commit the doc note**

```powershell
git add docs/MODEL-IMPROVEMENT.md
git commit -m "docs(ops): collector StartWhenAvailable fix + residual-loss caveat"
```

### Task 2 (P2): Verify the stale-route claim against master / prod

**Files:** investigation only; memory file update

- [ ] **Step 1: Search the master lineage for the legacy routes**

```powershell
git grep -n "forecast/latest" master
git grep -n "'/forecast'" master
git grep -n '"/forecast"' master
```
Expected: either hits inside master's backend (then the route is real on prod) or no hits.

- [ ] **Step 2a (if hits in code Render serves):** identify the serving entry (check `git show master:Dockerfile.render` CMD). Create branch `fix/remove-legacy-forecast-route` FROM master, delete/redirect the route, PR to master titled `fix(api): retire stale v1 /forecast/latest (serves balanced_rf)`. Do NOT merge the dev branch into master for this.

- [ ] **Step 2b (if no hits):** the route was already removed; update memory file `prod-render-correctness.md` to drop the stale claim so future sessions stop reporting it.

### Task 3 (P2): Close the two superseded PRs with explanatory notes

**Files:** none (GitHub state)

- [ ] **Step 1: Close PR #1**

```powershell
gh pr close 1 --comment "Closing as superseded: this targeted the legacy Heatwave-AI-TRAIN/ layout. Its goals all shipped in the current flat codebase on feat/clean-era5-ndvi-dataset: temporal (year-based) split = src/splits.py + evaluation/cv.py; humidity-aware Thai labeling (sWBGT >= p95(doy) & >=2-day run) = src/labels.py + src/swbgt.py; EDA/profiling = scripts/profile_dataset.py + docs/DATASET_PROFILE.md. The 77-province 1991-2025 dataset (2026-06-05 rebuild) replaced the data this PR analyzed."
```
Expected: `✓ Closed pull request #1`

- [ ] **Step 2: Close PR #2**

```powershell
gh pr close 2 --comment "Closing as superseded: AsyncStorage settings persistence (theme/language/font size, with validation guards) is already implemented on feat/clean-era5-ndvi-dataset in HeatMAP-Frontend/hooks/useSettings.tsx, and the humidity_pct/heat_index_c forecast-model fields shipped in services/forecastService.ts. Nothing here is lost."
```
Expected: `✓ Closed pull request #2`

### Task 4 (P3): Clean junk + commit the review artifacts

**Files:**
- Delete: `HeatMAP-Frontend/bun_test_out.txt`
- Commit: `docs/PROJECT-EXPLAINER.html`, `docs/PROJECT-REVIEW.html`, `docs/superpowers/plans/2026-06-10-review-remediation.md`

- [ ] **Step 1: Delete the junk file**

```powershell
Remove-Item HeatMAP-Frontend/bun_test_out.txt -Confirm:$false
```

- [ ] **Step 2: Commit the docs**

```powershell
git add docs/PROJECT-EXPLAINER.html docs/PROJECT-REVIEW.html docs/superpowers/plans/2026-06-10-review-remediation.md
git commit -m "docs: project review (animated HTML) + remediation plan"
```

- [ ] **Step 3: Verify clean tree**

Run: `git status --short`
Expected: empty (or only intentionally-unstaged files).

### Task 5 (P3): Mark config.yaml as not-wired

**Files:**
- Modify: `config.yaml:1` (prepend comment block)

- [ ] **Step 1: Prepend the warning header**

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# WARNING — LEGACY / ASPIRATIONAL CONFIG. NOT WIRED INTO THE LIVE PIPELINE.
# The actually-wired data pipeline is documented in docs/DATA.md; the canonical
# training set is data/processed/dataset.parquet built by pipeline scripts.
# This file describes an older ERA5/MODIS-NDVI design kept for reference only.
# (See CLAUDE.md "Data & datasets".)
# ─────────────────────────────────────────────────────────────────────────────
```

- [ ] **Step 2: Verify nothing breaks (some modules may parse this YAML)**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -q`
Expected: `161 passed`

- [ ] **Step 3: Commit**

```powershell
git add config.yaml
git commit -m "docs(config): banner — config.yaml is legacy, not wired (see docs/DATA.md)"
```

### Task 6 (P3, re-scoped): Defuse the dual-lineage trap instead of merging

Merging is rejected for now: histories are unrelated, master carries large .nc binaries, and the ACTIVE cron on master deliberately checks out this branch. The safe fix is backup + documentation.

**Files:**
- Modify: `CLAUDE.md` (add a short "Branch architecture" note)

- [ ] **Step 1: Push the branch so 105 local-only(?) commits are backed up**

```powershell
git status -sb   # check ahead/behind vs origin/feat/clean-era5-ndvi-dataset
git push origin feat/clean-era5-ndvi-dataset
```
Expected: up-to-date or successful push.

- [ ] **Step 2: Document the branch architecture in CLAUDE.md**

Add under the repo-overview section:

```markdown
## Branch architecture (do NOT naive-merge)

`master` and `feat/clean-era5-ndvi-dataset` share **no common ancestor**.
`master` = legacy lineage + deploy host: Render/Vercel configs and the ACTIVE
`.github/workflows/daily-forecast.yml` (schedules only fire from the default
branch), which checks out `feat/clean-era5-ndvi-dataset` for the real ML code.
`feat/clean-era5-ndvi-dataset` = the active development line (flat `src/`,
`pipeline/`, frontend, all tests). Merging them requires a deliberate
default-branch migration (move workflows, retarget Render/Vercel, drop the
legacy `Era5-data-2000-2026/*.nc` blobs) — never a plain `git merge`.
```

- [ ] **Step 3: Commit**

```powershell
git add CLAUDE.md
git commit -m "docs: record dual-lineage branch architecture (master = cron host)"
```

### Task 7: Final verification + push

- [ ] **Step 1: Full test suites**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -q` then `bun test`
Expected: `161 passed` and `40 pass, 0 fail`.

- [ ] **Step 2: Push**

```powershell
git push origin feat/clean-era5-ndvi-dataset
```

- [ ] **Step 3: Update memory**

Update `track-m-ml-progress.md` / `prod-render-correctness.md` memory files to reflect: collector now StartWhenAvailable; PRs #1/#2 closed; route claim resolved per Task 2 outcome; dual-lineage documented.
