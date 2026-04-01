# HEATWAVE-AI-Prediction — Project Context

**Version**: 1.0.0  
**Date**: 2026-03-05  
**Status**: ✅ Initial Implementation Complete

---

## Project Goal

Build a modular AI experimentation platform that:
- Trains 5 ML models for heatwave prediction using ERA5 climate data
- Benchmarks models automatically on a leaderboard ranked by F1 Score
- Persists trained models for future prediction
- Visualizes results via a premium web dashboard
- Launches with a single click via `Start.bat`

---

## System Architecture

```
HEATWAVE-AI-Prediction/
│
├── Era5-data-2000-2026/     ← Raw ERA5 NetCDF files (2000–2015)
│
├── config/config.yaml       ← Central settings (paths, thresholds, hyperparams)
├── requirements.txt         ← Python dependencies
│
├── utils/
│   ├── data_loader.py       ← Loads ERA5 NetCDF → pandas DataFrame
│   └── preprocessing.py    ← Feature engineering, labels, StandardScaler, splits
│
├── models/
│   ├── base_model.py        ← Abstract BaseModel interface
│   ├── balanced_random_forest.py
│   ├── xgboost_model.py
│   ├── lightgbm_model.py
│   ├── mlp_model.py         ← PyTorch MLP with early stopping
│   └── kan_model.py         ← KAN with learnable B-spline activations (PyTorch)
│
├── evaluation/
│   ├── metrics.py           ← compute_metrics() → accuracy, precision, recall, F1, ROC-AUC
│   └── benchmark.py         ← Leaderboard builder from result JSONs
│
├── training/
│   ├── trainer.py           ← Train → evaluate → save cycle
│   ├── cross_validation.py  ← StratifiedKFold CV helper
│   └── hyperparameter_tuning.py  ← GridSearch / RandomSearch helpers
│
├── pipelines/
│   └── training_pipeline.py ← Orchestrates all 5 models end-to-end
│
├── prediction/
│   ├── predictor.py         ← Loads model + scaler, runs inference
│   └── predict.py           ← CLI: python predict.py --model xgboost --input data.csv
│
├── dashboard/
│   ├── app.py               ← Flask app factory
│   ├── routes.py            ← API routes (/api/leaderboard, /api/best, /api/results)
│   └── templates/index.html ← Premium dark-mode dashboard (Chart.js)
│
├── experiments/
│   ├── results/             ← Per-model JSON results + leaderboard.json
│   └── models/              ← Saved model .pkl files + scaler.pkl
│
├── main.py                  ← Unified entry point (--mode train|dashboard|predict)
└── Start.bat                ← One-click launcher
```

---

## Models Implemented

| Model | Algorithm | Key Feature |
|---|---|---|
| Balanced Random Forest | `imbalanced-learn` BRF | Handles class imbalance natively |
| XGBoost | Gradient Boosting | Eval set with early stopping |
| LightGBM | Gradient Boosting | Fast training, early stopping |
| MLP Neural Network | PyTorch | 3-layer MLP, ReLU, dropout, Adam |
| KAN | PyTorch (custom) | Learnable B-spline activations per edge |

---

## Data Pipeline

- **Source**: ERA5 surface NetCDF files, 2000–2015 (`era5_surface_YYYY.nc`)
- **Variables**: `t2m`, `d2m`, `sp`, `u10`, `v10`
- **Features**: `t2m_c`, `d2m_c`, `heat_index`, `wind_speed`, `sp`
- **Label**: Heatwave = 1 if `t2m ≥ 35°C`, else 0
- **Split**: Train 70% / Val 15% / Test 15% — stratified

---

## Training Pipeline Status

✅ Complete — `pipelines/training_pipeline.py`

Steps:
1. Load ERA5 data via `ERA5DataLoader`
2. Preprocess & generate labels via `HeatwavePreprocessor`
3. Stratified train/val/test split
4. Train each of 5 models
5. Evaluate → compute metrics
6. Save result JSON to `experiments/results/`
7. Save model `.pkl` to `experiments/models/`
8. Update `experiments/results/leaderboard.json`

---

## Prediction System Status

✅ Complete — `prediction/predict.py`

```bash
python prediction/predict.py --model xgboost --input new_data.csv
python prediction/predict.py --model lightgbm --input data.csv --output results.csv --proba
python main.py --mode predict --model kan --input data.csv
```

---

## Dashboard Status

✅ Complete — `dashboard/` (Flask + Chart.js)

- URL: `http://localhost:5000`
- Features: Best model hero card, leaderboard table, 5 comparison charts, training timeline
- Auto-refresh every 60 seconds

---

## Current Progress

- [x] Directory structure
- [x] Configuration (`config.yaml`)
- [x] Data loader (ERA5 NetCDF)
- [x] Preprocessing pipeline
- [x] All 5 models implemented
- [x] Metrics computation
- [x] Leaderboard benchmark
- [x] Trainer
- [x] Cross-validation helper
- [x] Hyperparameter tuning helper
- [x] Training pipeline (full orchestration)
- [x] Prediction system (CLI + Predictor class)
- [x] Flask dashboard (app + routes + premium HTML)
- [x] Main entry point
- [x] Start.bat launcher

---

## Next Development Tasks

1. **GPU training** — Enable CUDA for PyTorch models when GPU is available (already scaffolded in `mlp_model.py` and `kan_model.py`)
2. **Hyperparameter tuning** — Run `training/hyperparameter_tuning.py` per model then retrain
3. **Cross-validation report** — Add CV metrics to leaderboard
4. **More data years** — Add ERA5 2016–2025 data when available
5. **SHAP explainability** — Add feature importance plots to dashboard
6. **Mobile dashboard** — Improve responsive layout for small screens
7. **Email notifications** — Send leaderboard updates on training completion
8. **REST API prediction** — Add `/api/predict` endpoint to dashboard for web-based inference
