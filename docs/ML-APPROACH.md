# Heatwave-AI — ML Approach (research + empirical bake-off)

**TL;DR:** The project's current choice — **gradient-boosted trees (LightGBM)**
with **keep-data-unbalanced + isotonic calibration + F2 threshold tuning** on a
**temporal split** — is the right approach and is backed by both the literature
and an empirical bake-off on the project's own data. Keep it. The two
highest-value additions are a **Brier Skill Score / persistence baseline** in
the metric set and fixing the **sWBGT label bias** (see `DATA.md`).

## 1. Problem framing

Per-`(province, horizon 1–7 days)` binary classification of a heatwave day
(sWBGT ≥ day-of-year p95 **and** ≥2-day run), ~3–4% positive. Inputs are ~25
**engineered tabular** features (leakage-safe rolling mean/max over 3/7/14/30 d
of sWBGT/Tmax/RH, climatology anomaly, seasonal sin/cos of day-of-year, static
lat/lon/province_id, horizon). ~1M rows at full coverage. Split: train ≤2023,
validate 2024, test 2025.

## 2. What the literature says (2022–2026)

1. **Model family — tree ensembles win on tabular.** GBDTs (LightGBM/XGBoost/
   CatBoost) remain the evidence-based default for medium tabular data; deep
   tabular nets (TabNet/FT-Transformer) and KANs underperform and cost more
   ([Grinsztajn 2022](https://arxiv.org/abs/2207.08815);
   [2024 benchmark](https://arxiv.org/html/2408.14817v1)). TabPFN is strong but
   capped (~10k rows) — out for ~1M rows. Heatwave-specific ML studies favor
   RF/XGBoost/LightGBM/CatBoost ([Nature 2025](https://www.nature.com/articles/s41598-025-04634-9)).
2. **Imbalance — don't resample; calibrate.** SMOTE / heavy cost-weighting
   systematically wreck rare-event probability calibration; the durable fix is
   leaving data unbalanced + **post-hoc calibration** + threshold tuning
   ([van den Goorbergh 2022](https://arxiv.org/pdf/2202.09101)). This vindicates
   the current design.
3. **Calibration — isotonic, kept pooled.** Isotonic is fine pooled across all
   provinces/horizons (thousands of validation positives), but overfits on thin
   slices — do **not** calibrate per-province/horizon; consider beta calibration
   if you ever must ([sklearn calibration](https://scikit-learn.org/stable/modules/calibration.html)).
4. **Metrics — PR-AUC / F2 / Brier, not accuracy/ROC.** At ~4% positives ROC-AUC
   looks optimistic; PR-AUC and F2 measure positive retrieval (what a heat
   warning cares about). Report a **Brier Skill Score vs the climatological base
   rate** (a proper scoring rule + skill baseline in one). Temporal (not random)
   splits are mandatory — rolling features autocorrelate and random splits leak
   ([PR-AUC guide](https://coralogix.com/ai-blog/ultimate-guide-to-pr-auc-calculations-uses-and-limitations/)).
5. **KAN/MLP unlikely to win** here; keep them as reference only
   ([KAN vs GBDT](https://arxiv.org/pdf/2406.14529)).
6. **One global, multi-horizon model** (province_id + lat/lon + horizon as
   features) beats 77 per-province or 7 per-horizon models — it pools the scarce
   positives. Sequence models (LSTM/TCN/Transformer) on raw daily series are
   worth trying only as a later hybrid; engineered-tabular GBDT is the SOTA
   default here.

## 3. Empirical bake-off (this repo's data + metrics)

`scripts/bakeoff.py` trains each candidate on the **same** frame, temporal
split, isotonic calibration, and F2 tuning as production, then scores with
`evaluation/heatwave_metrics` + a Brier Skill Score. Ranked by F2 on test-2025.

**Preliminary (2 provinces — Bangkok + Samut Prakan; adjacent/central, low
diversity → weak signal; refresh on expanded data):**

| model | F2 | PR-AUC | BSS | ROC-AUC | Brier | MCC |
|-------|----|--------|-----|---------|-------|-----|
| **lightgbm** | **0.339** | 0.122 | 0.026 | 0.651 | 0.0651 | 0.167 |
| random_forest | 0.324 | 0.122 | 0.020 | 0.668 | 0.0655 | 0.128 |
| balanced_rf | 0.323 | 0.139 | 0.032 | 0.689 | 0.0647 | 0.173 |
| xgboost | 0.320 | 0.107 | 0.008 | 0.613 | 0.0663 | 0.131 |

On a more diverse 3-province validation (incl. a southern + a NE province),
LightGBM reached **F2 0.58 / PR-AUC 0.30** vs an F2 0.54 base-rate baseline —
i.e., real skill that grows with geographic coverage. All models beat
climatology (positive BSS). LightGBM leads F2; balanced RF is the strongest
ranking/calibration alternative; XGBoost trails here. This **matches** the
literature: the tree-ensemble family wins, deep nets are not needed.

> Re-run after expanding the dataset: `.\.venv\Scripts\python.exe scripts\bakeoff.py`
> (writes `experiments/results/leaderboard.json`).

## 4. Recommendation

- **Primary model: LightGBM** (current). Keep **balanced random forest** as the
  tracked alternative — it competes on ranking/calibration and is a useful
  ensemble/robustness check. Keep XGBoost in the bake-off for completeness; do
  not expect MLP/KAN to win.
- **Keep the imbalance/calibration design as-is**: unbalanced data +
  `scale_pos_weight`, isotonic calibration **pooled**, F2-tuned threshold.
- **Add to evaluation**: Brier Skill Score vs climatology (done in `bakeoff.py`)
  and a **persistence baseline** (predict heatwave(t+k) = heatwave(t)) so leads
  are judged against the obvious naive forecast.
- **Validate per split × horizon**, not just global base rate (positive counts
  per 2024/2025 year × horizon) — they are currently healthy (~200+/horizon).
- **Then** consider: mild `scale_pos_weight` tuning for F2 (check it doesn't hurt
  post-calibration Brier), and a single-multi-horizon vs per-horizon check at
  lead 7.

## 5. Flags (don't bury)

- Numbers above are **preliminary** (few provinces, hourly API limit). Expand the
  dataset (`DATA.md`) and re-run the bake-off before quoting them anywhere.
- The **sWBGT_max label bias** (Tmax with mean RH) is the #1 accuracy fix and
  affects *every* model equally — see `DATA.md §3.2`.
- We evaluated the **wired Open-Meteo/sWBGT** path, not `config.yaml`'s
  ERA5+MODIS-NDVI design. Adding NDVI/upper-air predictors is a separate,
  larger experiment that could lift skill but needs the heavier ingestion.
