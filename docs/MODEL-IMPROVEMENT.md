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

  **P0 REAL-DATA run** (`scripts/p0_forecast_real.py`). Replaced the noise model
  with *real* archived forecasts (Open-Meteo Historical Forecast API, 20 provinces,
  2022–25; train 2022–23 / val 2024 / test 2025):

  | features | PR-AUC | F2 | precision | recall |
  |----------|--------|----|-----------|--------|
  | baseline (antecedent) | 0.310 | 0.549 | 0.217 | 0.889 |
  | + REAL forecast covariates | **0.854** | **0.900** | 0.687 | 0.976 |

  Near the oracle (0.877) — **but read it carefully.** The Historical Forecast API
  returns one archived series per date (~analysis / short-lead quality), *not*
  lead-specific forecasts, so per-horizon skill is almost flat (lead-1 0.872 →
  lead-7 0.836). That is **optimistic at long leads** — a real day-7 forecast is
  much worse than a day-1 forecast, which this data doesn't reflect.

  **So the realizable gain is bracketed:**
  | scenario | PR-AUC | F2 |
  |----------|--------|----|
  | baseline | 0.31–0.33 | 0.55 |
  | noise model (lead-decaying, conservative) | 0.48 | 0.63 |
  | real archived forecast (~uniform short-lead, optimistic) | 0.85 | 0.90 |
  | oracle (perfect) | 0.88 | 0.92 |

  Truth per horizon sits between the two middle rows: short leads (1–3 d) land
  near the optimistic row (huge, real gain); long leads (5–7 d) closer to the
  conservative row. **The lever is confirmed real with actual forecast data.**
  The remaining correctness gap is *lead-specific* forecast quality: the proper
  next step is reforecasts that preserve true day-k error (Open-Meteo previous-runs,
  limited history; or ECMWF reforecasts) before wiring into the production pipeline.

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
