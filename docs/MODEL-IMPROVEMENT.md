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
