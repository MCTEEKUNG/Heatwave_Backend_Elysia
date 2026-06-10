# Model Improvement Roadmap — how to push past F2 ≈ 0.56

How a senior engineer reasons about "the score isn't production-grade yet." The
point is to **find the ceiling first**, then spend effort on the lever that
moves it — not to tune models blindly.

## 1. Reframe: is the score even the right question?
Current production-candidate (20 provinces, test 2025): **F2 0.556, PR-AUC 0.332,
ROC 0.76, recall 0.86, precision 0.23**. It already **beats the baselines**
(climatology F2 0.47, persistence 0.42) — it has real skill. "Production-ready"
is **not** an abstract score; it's *"beats the baseline you'd otherwise deploy,
at an operating point whose false-alarm vs missed-heatwave cost the stakeholders
accept."* Decide that with the people who act on the alert, not against a number.

## 2. Diagnosis: the ceiling is SIGNAL-bound (measured, not guessed)
Two pieces of evidence:
- **All 7 model families converge at F2 ≈ 0.53–0.56.** When RF, XGB, CatBoost,
  LightGBM, MLP, and the ensemble all land in the same place, the algorithm is
  not the bottleneck — the *information in the features* is.
- **Leaky-oracle headroom test** (`scripts/oracle_headroom.py`, diagnostic only):
  add the target day's *actual* weather as features →

  | features | PR-AUC | F2 | ROC |
  |----------|--------|----|-----|
  | antecedent-only (current) | 0.332 | 0.556 | 0.760 |
  | + oracle target-day weather | **0.877** | **0.915** | 0.983 |

  The label is **highly learnable** once you know the target-day weather. The
  current model can't — its features are **antecedent-only** (rolling stats of
  *past* sWBGT/Tmax/RH + season + geography). It is essentially a
  climatology-plus-recent-trend model, **blind to the forecast of the day it is
  predicting.** That gap (0.33 → 0.88) is the headroom.

## 3. Prioritized levers (why + expected impact)

**P0 — Give the model the future: NWP forecast covariates for the target day.**
This is the headroom above. At inference the forecast is *already fetched*
(`run_forecast` pulls Open-Meteo forecast for the target days) but **thrown away
as a feature**. Add predicted Tmax/RH/sWBGT for `target_time` to the feature set.
- *Impact:* the largest available lever; bounded by **NWP forecast error** and
  by **lead time** — short leads (1–3 d) gain a lot, lead-7 stays weaker (your
  per-horizon curve 0.62→0.53 is partly irreducible physics). Expect a big jump
  at short leads, diminishing with horizon — not uniform.
- *The trap (train/serve skew):* you must train on **archived forecasts /
  hindcasts** for the target days, NOT on ERA5/reanalysis actuals (that would
  train on information unavailable at serve time and collapse in production).
  Source: Open-Meteo "previous runs"/historical-forecast API (probed — returns
  archived forecasts, HTTP 200), or ECMWF reforecasts. This is the real work —
  sourcing the data, not the modeling.

  **P0 PROTOTYPE — realizable headroom measured** (`scripts/p0_forecast_prototype.py`).
  The oracle (0.88) is a *perfect* forecast; real forecast error grows with lead.
  Adding target-day weather degraded by a per-lead NWP-error model (≈1 °C day-1 →
  ≈3 °C day-7) gives the realistic estimate:

  | features | PR-AUC | F2 | precision | recall |
  |----------|--------|----|-----------|--------|
  | baseline (antecedent) | 0.332 | 0.556 | 0.229 | 0.864 |
  | + perfect forecast (oracle) | 0.877 | 0.915 | 0.719 | 0.981 |
  | **+ realistic forecast** | **0.481** | **0.632** | **0.316** | 0.843 |

  Realistic forecast captures **~27% of the headroom**: **F2 0.556→0.632** and
  **precision 0.229→0.316 (+38%)** at roughly equal recall — i.e. materially
  fewer false alarms. Lift is concentrated at short leads (physics, as predicted):

  | lead | base PR-AUC | + realistic |
  |------|-------------|-------------|
  | 1 d | 0.429 | **0.633** |
  | 3 d | 0.330 | 0.488 |
  | 7 d | 0.285 | 0.368 |

  Conclusion: **P0 is worth building.** Even a conservative forecast meaningfully
  improves precision and short-lead skill.

  **P0 REAL-DATA run — FAILED to measure forecast skill (oracle in disguise).**
  (`scripts/p0_forecast_real.py`.) Pulled "archived forecasts" from the Open-Meteo
  Historical Forecast API (20 provinces, 2022–25) and trained with them. Result
  was near-oracle (F2 0.900, PR-AUC 0.854) with an almost-flat per-horizon curve
  (lead-1 0.872 → lead-7 0.836). **That flatness is the red flag**, and a direct
  check confirms it: fetched `fc_swbgt`/`fc_tmax`/`fc_rh` vs the dataset actuals
  have **corr = 1.0000, MAE = 0.000** — the API returns the *same* near-analysis
  values for past dates, not genuine forecasts issued k days earlier. So this run
  is the oracle again (the small gap vs 0.877 is just the thinner 2022–23 training
  window), and it instantiates the very **train/serve-skew trap** P0 warns about:
  training on analysis-quality values the model can never get at serve time.

  **It does NOT provide a realizable estimate.** The only honest realizable number
  remains the noise model:
  | scenario | PR-AUC | F2 | status |
  |----------|--------|----|--------|
  | baseline | 0.31–0.33 | 0.55 | measured |
  | **noise model (lead-decaying)** | **0.48** | **0.63** | **realizable estimate (assumption-based)** |
  | oracle / "real archived forecast" | 0.85–0.88 | 0.90–0.92 | ceiling only — NOT realizable |

  What the real-data run *did* earn: the fetch/join plumbing works and is reusable,
  and it re-confirms the label is near-deterministic in target-day weather.

  **Real next step for an assumption-free per-lead number:** lead-specific
  reforecasts that preserve true day-k error — Open-Meteo previous-runs
  (`temperature_2m_previous_dayN`, limited history) or ECMWF reforecasts — before
  wiring forecast covariates into the production pipeline.

**P1 — Label fidelity: hourly → daily-max sWBGT.** The label is built from daily
`Tmax` + daily-*mean* RH; physically the daily max temp coincides with min RH,
so `sWBGT_max` is biased. A biased target caps *every* model. (`HEATWAVE_HOURLY=1`
path exists; ~24× heavier — do it for the signal that matters.)

**P1 — Coverage + history.** 20→77 provinces (generalization, more positives);
ERA5 reaches back to 1940, so the record can extend well before 1991 for more
rare-event examples.

**P2 — Error-driven regional work.** Skill is wildly uneven: South F2 0.70 vs
Northeast 0.39, West 0.40; **Chiang Rai 0.10** (base rate 1.4%). Per-region
thresholds, region-specific features (arid North differs), or pooling decisions
for ultra-low-base-rate provinces.

**P2 — Operating point with stakeholders.** Precision 0.23 = many false alarms
at the recall-leaning F2 point. Pick the point from the real cost of a false
alarm vs a missed heatwave; consider a two-tier (watch / warning) alert.

**Low — Model/HP tuning.** Real but **low-single-digit** given the convergence;
worth a pass *after* the signal levers, not before. Use **time-series CV**
(`evaluation/cv.py`, rolling origin) so you trust the deltas instead of chasing
single-year noise.

## 4. Methodology (how to actually do it)
- **Ablate, don't guess:** add ONE signal, measure ΔPR-AUC on a fixed temporal
  split. Keep what moves the needle.
- **Trust the number:** rolling-origin CV (mean±std), not one val/test year.
- **Stop rule:** "good enough" = beats the deployment baseline at the chosen
  operating point — defined by decision cost, re-checked each iteration.

## TL;DR
The model isn't weak because of the algorithm or the label — it's **blind to the
forecast of the day it predicts.** Wire in NWP forecast covariates (trained on
hindcasts to avoid serve-skew); that's where the measured 0.33→0.88 headroom
lives. Everything else (label fidelity, coverage, regional fixes, operating
point) is real but secondary.

---

## 5. v2 clean ERA5 dataset — built, and the honest result

Per `docs/superpowers/plans/2026-05-31-clean-era5-ndvi-dataset.md` we rebuilt the
dataset from **real** ERA5 (CDS, 6-hourly) with full integrity: correct daily-max
heat-index label, 77 provinces, temporal split, leakage-safe antecedent features,
NO leakage (sanity gate passed). Canonical dataset: `data/processed/dataset_era5.parquet`
(281k daily rows, 2016–2025, relative p95+run label ~4.3%). Model `era5_lgbm`:

| model | features | train yrs | test | PR-AUC | F2 | ROC |
|-------|----------|-----------|------|--------|----|----|
| old (Open-Meteo) | 2-var antecedent | 1991–2023 (33) | 2025 | 0.332 | 0.556 | 0.760 |
| **era5_lgbm** | 45 ERA5 antecedent | 2016–2021 (6) | 2024–25 | **0.117** | **0.317** | **0.624** |

**The clean v2 scored LOWER — and the diagnosis is honest and instructive:**
1. **Train→test distribution shift.** Positive rate climbs **2.6% (train ≤2021) →
   5.3% (val 22–23) → 8.1% (test 24–25)** — the 6 humidity-bearing training years
   (2016–2021) are systematically *cooler* than the hot 2024–25 test years. The old
   dataset's 33-year history spanned the warming, so 2025 was less out-of-distribution.
   **Requiring humidity (ERA5 2016+) cost us 27 years of history** — a worse tradeoff
   than the richer features bought back.
2. **Antecedent signal is weak (ROC 0.624).** Exactly the oracle lesson: past-only
   features can't see the target day. Richer antecedent variables don't change that.

**This is not a failure of the rebuild — it is the truth about this data.** The
foundation (clean, real, leakage-free, correct label, 77 provinces, reproducible) is
sound and reusable. The score didn't improve because (a) the humidity constraint
shrank history and (b) antecedent features hit the same ceiling P0 was designed to break.

**Implications / next options (for the user to choose):**
- **More history:** combine long-record t2m (Open-Meteo/ERA5 back to 1991) for the
  antecedent backbone with humidity-rich features only where available — multi-fidelity.
- **Label robustness:** fit per-province p95 on a fixed baseline (train years) so the
  threshold doesn't absorb the warming trend (reduces the train→test label shift).
- **P0 remains the real lever:** forecast covariates (genuine lead-k forecasts) — the
  only thing the oracle showed can reach the headroom. ERA5 reanalysis ≠ forecast.
- NDVI ablation deferred: a slow antecedent feature won't recover a history/​shift deficit.

### Trustworthy evaluation: rolling-origin CV (`scripts/cv_era5.py`)

The single-split numbers above are volatile (year-to-year base rate swings 3%→13%).
The honest read is rolling-origin CV (test 2021–2025, train on all prior years),
with **threshold-independent primary metrics** and a **fixed operating point**
(threshold set on val to hit recall ≈ 0.80, NOT per-year F2-max — that removes the
threshold-transfer artifact):

| fold (test) | train yrs | ROC | PR-AUC lift (×prev) | prec @rec≈.80 |
|---|---|---|---|---|
| 2021 | 4 | 0.500 | 1.0× | 0.05 |
| 2022 | 5 | 0.564 | 1.2× | 0.03 |
| 2023 | 6 | 0.639 | 1.6× | 0.09 |
| 2024 | 7 | 0.579 | 1.2× | 0.15 |
| 2025 | 8 | 0.719 | 2.5× | 0.04 |
| **mean ± std** | | **0.601 ± 0.083** | **1.49× ± 0.60** | **0.074 ± 0.05** |

**Verdict (decisive): the clean antecedent model is a weak ranker (mean ROC ≈ 0.60,
PR-AUC only ~1.5× the no-skill floor).** The 0.72 fold was optimistic; averaged
honestly it is near-chance. One real signal stands out: **skill rises monotonically
with training history (ROC 0.50 at 4 yrs → 0.72 at 8 yrs)** — but the humidity
requirement caps ERA5 history at 2016. HP tuning and richer antecedent variables
(wind/pressure/NDVI) cannot cross the ceiling the oracle already measured
(PR-AUC 0.33→0.88 ONLY when target-day weather enters).

### Conclusion of the clean antecedent track → the data fork (needs the user)

The clean-data rebuild is complete and correct, and it has now answered its question:
**antecedent-only features — however clean, rich, or well-evaluated — cannot reach
production-grade skill for this rare-event task.** Production requires **forecast
covariates** (genuine lead-k forecasts of the target day), which need forecast
**hindcast** data we do not have cleanly. The three honest paths are all external-data
decisions only the user can make:
1. **Forward-collect** real Open-Meteo forecasts daily from now → clean hindcast in ~2–3 months (free, correct, but waits).
2. **ECMWF reforecasts** → multi-year true lead-k forecasts now (CDS account + ingestion engineering).
3. **User supplies** an archived-forecast dataset.

Until one is chosen, the model cannot cross ROC ≈ 0.6–0.76. This is a genuine
external-data blocker, not an algorithmic one.

### P0 data engine — BUILT and RUNNING (`scripts/collect_forecast.py`)

Decision taken: **forward-collect** (the only clean, credential-free path; the probe
confirmed `past_days`/Historical-Forecast return analysis = leakage, so there is no
honest backfill). The engine fetches Open-Meteo's 7-day-ahead daily forecast (Tmax +
mean RH → `fc_heat_index`) for all 77 provinces and appends rows keyed by
`(province_id, issue_date, target_date, lead_k)` to `data/processed/forecast_store.parquet`.
Leakage-safe by construction (`issue_date < target_date`), append-only, idempotent.
**Seeded 2026-05-31: 539 rows (77 provinces × leads 0–6).**

**Run it daily** so the clean forecast-hindcast accumulates (Windows Task Scheduler):
```
schtasks /Create /TN HeatwaveForecastCollect /SC DAILY /ST 08:00 ^
  /TR "C:\Users\ASUS\Heatwave_AI\.venv\Scripts\python.exe C:\Users\ASUS\Heatwave_AI\scripts\collect_forecast.py"
```
After ~2–3 months (enough issue dates spanning a hot season) the store can be joined
at `target_date` into the forecasting frame as P0 covariates and retrained — the first
configuration that can realistically approach the oracle headroom (PR-AUC 0.33→0.88).
This is the path to production; the clock is now running.

**Reliability fix (2026-06-10):** the task originally ran "Interactive only" at a
fixed 08:00 and silently skipped days the laptop was asleep (9/11 issue dates in the
first 11 days). Re-registered with `StartWhenAvailable` so a missed 08:00 fires as
soon as the machine is next usable (the collector is idempotent per issue_date, so
catch-up runs are safe). **Residual limitation:** a day the laptop never powers on is
still lost forever. The durable fix is cloud collection — needs a persistence target
for `forecast_store.parquet` (HF repo or a Supabase table) before the GH-Actions cron
can host it; tracked as follow-up, not done yet.

### P0 unblocked NOW with REAL multi-year forecasts: NOAA GEFS reforecast

The forward-collector waits months; we don't have to. **NOAA GEFSv12 reforecast**
(`scripts/fetch_gefs_reforecast.py`) provides GENUINE lead-k forecasts 2000–2019,
free, no credentials, on AWS Open Data — proven readable here (`cfgrib` on Windows).
Ingestion is built + tested end-to-end: downloaded 52 inits (2018–2019 hot seasons),
extracted per-province daily-max forecast tmax → 28,028 leakage-safe rows
(`issue_date < target_date`). The full P0 measurement pipeline (`scripts/train_p0.py`)
joins these into the frame and trains A (antecedent) vs B (+forecast) on identical rows.

**First honest real-data P0 measurement (no oracle, no noise model, no analysis-leak):**

| model (identical 2018→2019 matched rows) | ROC | PR-AUC lift |
|---|---|---|
| A antecedent only | 0.486 | 0.98× |
| B + GEFS forecast **tmax** | 0.499 | 1.00× |

**≈ no lift — and the reason is specific, not a dead end:**
1. **Wrong covariate.** The label is *heat-index* (humidity-driven); I joined forecast
   *temperature only*. The oracle's power came from target-day **heat-index** (temp **+**
   humidity). A temperature-only forecast cannot reproduce it.
2. **Underpowered subset.** Matched rows are GEFS-init origin days only (2 yrs, 1.6%
   positives); even the antecedent baseline collapses to ~random (0.486) here vs
   0.60–0.72 on the full frame. Too little data to resolve a modest effect.

This is *consistent* with the noise model (realistic forecast error → **modest** lift,
not the perfect-oracle 0.88). **Exact next experiment (specified + runnable):** pull
GEFS `spfh_2m` (+`tmp_2m`/`pres_sfc`) for the same inits, compute a forecast
**heat-index** covariate (matches the label and the oracle signal), expand to
2016–2019 with denser inits for power, and re-run `train_p0.py`.

**State of the P0 path:** fully built and PROVEN on real data (ingest → join → train,
all tested) — not "wait months." Reaching a production number is now bounded
compute + the humidity-covariate step above, with an honest expectation (per oracle
vs noise model) of a *modest* real-forecast lift, largest at short lead.

### P0 humidity-covariate experiment — DONE, and it gives REAL lift (confirmed 2026-06-02)

The "exact next experiment" above was executed. `scripts/build_gefs_store.py` pulled a
**powered** GEFS store — 114 inits, dense across the 2016–2019 Mar–Jun heat seasons, all
77 provinces, with BOTH `fc_tmax` (daily-max) and `fc_spfh` (daily-mean) → **100% humidity
coverage** (`data/processed/gefs_forecast_store.parquet`, 61,446 rows). `scripts/train_p0.py`
builds a forecast **heat-index** covariate (`rh_from_specific_humidity` → `heat_index_c`,
matching the label + oracle signal) and trains A vs B on identical matched rows
(train origin <2018, test ≥2018):

| model (identical rows, 2016–17 → 2018–19) | ROC | PR-AUC lift |
|---|---|---|
| A antecedent only | 0.578 | 1.22× |
| **B + GEFS forecast heat-index** | **0.657** | **1.82×** |

**Real lift: ROC +0.079, PR-AUC lift 1.22×→1.82× (+49% rel).** This is the first honest,
real-data P0 result with genuine lift — not the leaky oracle, not the noise model, not
analysis-disguised-as-forecast. It confirms the thesis: target-day **heat-index** (temp +
humidity) is the lever; the earlier temperature-only run (≈no lift) failed because it
dropped humidity, not because forecasts don't help.

**Per-lead ROC (where the lift lives):**

| lead | n | pos | ROC A | ROC B | ΔROC |
|---|---|---|---|---|---|
| 1 | 4004 | 58 | 0.754 | 0.739 | −0.015 |
| 2 | 4004 | 40 | 0.581 | 0.628 | +0.047 |
| 3 | 4004 | 82 | 0.531 | 0.674 | **+0.143** |
| 4 | 4004 | 91 | 0.531 | 0.665 | **+0.134** |
| 5 | 4004 | 82 | 0.579 | 0.661 | +0.081 |
| 6 | 4004 | 59 | 0.596 | 0.623 | +0.027 |
| 7 | 4004 | 40 | 0.468 | 0.550 | +0.082 |

The lift is **concentrated at leads 3–5**, NOT lead 1 — because antecedent/persistence
already handles lead 1 (ROC 0.754) while it decays by lead 3 (0.531), exactly where the
forecast covariate restores skill. Practically: **forecasts extend useful lead time from
~1–2 days (persistence) out to ~5 days.**

**Productionization blocker (the real one now):** the lift is proven on GEFS reforecasts,
but GEFSv12 reforecast ends 2019 and is a *different NWP system* than what's available at
serve time (Open-Meteo). Wiring forecast covariates into production needs a **serve-time-
matched** forecast hindcast → the forward-collector (`scripts/collect_forecast.py`,
accumulating Open-Meteo forecasts daily) is the clean path; train on it once it spans a
hot season. GEFS proved the lever works; forward-collection makes it deployable.

### Antecedent soil moisture — MEASURED, and it confirms the ceiling thesis (2026-06-07)

Question: do other *indices* help? Tested the highest-evidence one (soil moisture; Domeisen
2022, Felsche 2023, Benson 2020) as a **leakage-safe antecedent** feature. Fetched real
Open-Meteo archive soil moisture (`soil_moisture_0_to_7cm`, ERA5-Land) per province
2016–2019 (`scripts/fetch_archive_soil_moisture.py` → `data/processed/era5_soil_moisture.parquet`,
95,942 rows), built antecedent features (`sm_lag1`, `sm_mean_7d`; strictly < origin), and ran
A/B/C/D on identical GEFS-matched + soil-covered rows (`scripts/train_p0_soil.py`,
train origin<2018 / test ≥2018, 61,446 rows, 452 test positives):

| model (identical rows) | ROC | PR-AUC lift |
|---|---|---|
| A antecedent base | 0.578 | 1.22× |
| B + antecedent soil moisture | **0.570 (−0.008)** | 1.22× |
| C + forecast heat-index (P0) | 0.657 (+0.079) | 1.82× |
| **D + forecast HI + soil** | **0.665 (+0.008)** | **1.97× (+0.15)** |

**Significance check (`scripts/p0_soil_robustness.py`) — because ±0.008 with 452 positives
is near the noise floor (SE≈0.02), and §4 mandates "trust the number".** LightGBM is
deterministic here (seed variance = 0.000), so the only uncertainty is test-set sampling;
1000× bootstrap of the test ΔROC:

| comparison | ΔROC median | 90% CI | verdict |
|---|---|---|---|
| B−A (soil **alone** over base) | −0.0076 | [−0.018, +0.003] | **includes 0 → noise** |
| D−C (soil **on top of** P0) | +0.0080 | [+0.002, +0.014] | **excludes 0 → small real effect** |

**Verdict (empirical + significance-tested):**
1. **Antecedent soil moisture ALONE does not help** — ΔROC indistinguishable from zero
   (CI includes 0). It cannot cross the signal ceiling the oracle measured; same lesson as
   every other antecedent variable (§2).
2. **Soil moisture is a SMALL but bootstrap-significant complement *on top of* the forecast
   covariate** (D vs C: ΔROC +0.008, 90% CI excludes 0; PR-AUC lift 1.82×→1.97×). Real but
   minor next to the forecast covariate itself (+0.079 ROC). **Caveat: single temporal split
   (train<2018/test 2018–19); the bootstrap covers within-split sampling only — confirm with
   rolling-origin CV (`evaluation/cv.py`) before banking it across years.**

**Takeaway:** lever ranking unchanged — **forecast covariates dominate (+0.079); antecedent
indices (soil moisture, and by extension NDVI/drought) are marginal and only earn their keep
*on top of* the forecast.** Plumbing to carry soil moisture as a *forecast* covariate is built
(`scripts/collect_forecast.py` now records `fc_soil_moisture`); a serve-time soil-moisture
*forecast* (not just antecedent) is the version most likely to add more, once the forward store matures.
