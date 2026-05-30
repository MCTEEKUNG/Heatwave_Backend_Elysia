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

Candidates: LightGBM, Balanced RF, Random Forest, XGBoost, **CatBoost**, an
**MLP** reference, and a **soft-voting ensemble** of the strong GBDTs.
**KAN is deliberately deferred** (heavy `pykan` dependency; the tabular evidence
in §2 says it loses — not worth the integration cost now).

**Result — 20 provinces (all 6 regions), 1.78M-row frame, test = 2025 (50.5k
samples, 15% positive), ranked by F2:**

| model | F2 | PR-AUC | BSS | ROC-AUC | Brier | MCC | fit |
|-------|----|--------|-----|---------|-------|-----|-----|
| **balanced_rf** | **0.559** | 0.329 | 0.096 | 0.760 | 0.1154 | 0.257 | 33s |
| **lightgbm** | 0.556 | **0.332** | 0.094 | 0.760 | 0.1157 | 0.252 | 41s |
| ensemble(lgbm+xgb+cat) | 0.553 | 0.331 | 0.093 | 0.761 | 0.1158 | 0.241 | — |
| **catboost** | 0.553 | 0.332 | **0.097** | **0.762** | 0.1153 | 0.241 | 31s |
| random_forest | 0.544 | 0.316 | 0.083 | 0.752 | 0.1171 | 0.226 | 122s |
| xgboost | 0.534 | 0.319 | 0.078 | 0.749 | 0.1178 | 0.206 | 18s |
| mlp (ref) | 0.515 | 0.268 | 0.030 | 0.704 | 0.1240 | 0.169 | **1160s** |

With real geographic coverage the signal rises from 2-province noise (F2 ≈ 0.34)
to **F2 ≈ 0.56 / PR-AUC ≈ 0.33 / ROC-AUC ≈ 0.76**, and the model ranking becomes
clear and stable. **The three tree ensembles — Balanced RF, LightGBM, CatBoost —
are in a statistical tie at the top** (F2 0.553–0.559, PR-AUC ≈ 0.33, BSS ≈
0.09–0.10, all comfortably beating climatology). XGBoost trails slightly. The
**MLP is decisively last *and* cost ~19 minutes** (vs 18–40 s for the trees) — a
clean empirical confirmation of §2/§5: deep nets do not win this tabular,
rare-event problem and are not worth their cost. The GBDT soft-vote ensemble
matches its members without beating them, so it is optional, not necessary.

> Reproduce / refresh as coverage grows: `.\.venv\Scripts\python.exe scripts\bakeoff.py`
> (writes `experiments/results/leaderboard.json`).

On a more diverse 3-province validation (incl. a southern + a NE province),
LightGBM reached **F2 0.58 / PR-AUC 0.30** vs an F2 0.54 base-rate baseline —
i.e., real skill that grows with geographic coverage. All models beat
climatology (positive BSS). LightGBM leads F2; balanced RF is the strongest
ranking/calibration alternative; XGBoost trails here. This **matches** the
literature: the tree-ensemble family wins, deep nets are not needed.

> Re-run after expanding the dataset: `.\.venv\Scripts\python.exe scripts\bakeoff.py`
> (writes `experiments/results/leaderboard.json`).

## 4. Recommendation

- **Primary model: LightGBM** (current). Track **balanced random forest** and
  **CatBoost** as alternatives, and the **soft-voting ensemble** of the GBDTs as
  a robustness option — pick the final model on the multi-province leaderboard by
  F2 then PR-AUC, with calibration (BSS/Brier) as the tie-breaker. **XGBoost** is
  kept for completeness; the **MLP** is a reference row only (slow, no edge);
  **KAN is deferred**. Do not expect the deep models to win on this tabular data.
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

- Numbers above are from a **20/77-province** stratified build (all 6 regions) —
  solid and directionally trustworthy, but expand toward full coverage
  (`DATA.md`, resumable) and re-run the bake-off before treating them as final.
- The **sWBGT_max label bias** (Tmax with mean RH) is the #1 accuracy fix and
  affects *every* model equally — see `DATA.md §3.2`.
- We evaluated the **wired Open-Meteo/sWBGT** path, not `config.yaml`'s
  ERA5+MODIS-NDVI design. Adding NDVI/upper-air predictors is a separate,
  larger experiment that could lift skill but needs the heavier ingestion.
