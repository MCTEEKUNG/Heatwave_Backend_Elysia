# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Heatwave-AI is a full-stack AI system for heatwave prediction and forecasting. It consists of:
- **HeatMAP-Frontend** — React Native/Expo mobile + web app
- **Heatwave-AI-Backend-Elysia** — Bun + Elysia TypeScript API server
- **Heatwave-AI-TRAIN** — Python ML training and prediction pipeline
- **Era5-data-2000-2026** — Historical ERA5 climate data (NetCDF)
- **ndvi** — NDVI vegetation index processing

## Commands

### Frontend (`HeatMAP-Frontend/`)
```bash
npm install
npm start          # Expo dev server
npm run web        # Web browser
npm run android    # Android emulator
npm run ios        # iOS simulator
npm run lint       # ESLint
```

### Backend (`Heatwave-AI-Backend-Elysia/`)
```bash
bun install
bun run dev        # Watch mode: bun run --watch src/index.ts
bun run src/index.ts  # Production
```

### ML System (`Heatwave-AI-TRAIN/`)
```bash
pip install -r requirements.txt
python main.py --mode train                              # Train all models
python prediction/forecast.py --model balanced_rf --days 30 --cycles 3  # Generate forecast
python prediction/predict.py                            # Single prediction
```

### Docker (full stack)
```bash
docker-compose up -d   # Backend on port 3000, mounts ML system
```

## Architecture

### Data Flow
```
User selects model/days/cycles in ForecastScreen
→ POST /api/forecast {model, days, cycles, startDate}
→ Backend spawns Python: prediction/forecast.py --model balanced_rf --days 30 --cycles 1
→ Python writes forecast JSON to experiments/forecasts/
→ Backend reads output and returns to frontend
→ Frontend renders calendar heatmap with risk levels
```

### Backend API (`src/index.ts`)
Key endpoints:
- `GET /api/health` — health check (used by Render)
- `POST /api/forecast` — generate new forecast (spawns Python subprocess)
- `GET /api/forecast/latest` — latest cached forecast
- `GET /api/results/leaderboard` — model performance comparison
- `GET /api/predict` / `POST /api/predict` — direct prediction on CSV input
- `GET /api/predict/models` — available models (currently only `balanced_rf`)

The backend bridges TypeScript (Elysia) and Python: it validates requests with Elysia's type system, spawns Python processes via `child_process.spawn()`, reads output files, and returns JSON responses.

### Frontend Services
- `services/apiService.ts` — base API client with retry logic (2 retries, exponential backoff, 15s timeout)
- `services/forecastService.ts` — forecast-specific calls; risk level thresholds: low <0.4, moderate <0.6, high <0.8, extreme ≥0.8
- `components/forecast/ForecastScreen.tsx` — main forecast UI with model selector and calendar heatmap

### ML Models (in `Heatwave-AI-TRAIN/`)
Five models trained: Balanced Random Forest, XGBoost, LightGBM, MLP, KAN. Only `balanced_rf` is currently active in the prediction API. Trained models are serialized as `.pkl` files in `models/` and downloaded from Hugging Face during Docker builds.

## Environment Variables

### Frontend (`.env` in `HeatMAP-Frontend/`)
```
EXPO_PUBLIC_API_URL=https://heatwave-backend-elysia.onrender.com
EXPO_PUBLIC_GOOGLE_MAPS_API_KEY=   # optional
```

### Backend
```
PORT=3000   # or 10000 on Render
NODE_ENV=production
```

## Deployment

- **Backend**: Deployed on Render via `render.yaml` using `Heatwave-AI-Backend-Elysia/Dockerfile.render`. The Dockerfile installs both Bun and Python 3, sets up a venv, and downloads pre-trained models from Hugging Face.
- **Frontend**: Deployed on Vercel. Set `EXPO_PUBLIC_API_URL` to the Render backend URL.
- Health check path used by Render: `/api/health`
- Production port: `10000` (Render), `3000` (local/Docker)
