# Heatwave-AI — Architecture & System Overview

> A full-stack AI system for heatwave prediction in Thailand.
> Built with React Native (frontend), Bun + Elysia (backend), and Python ML (inference).

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Repository Structure](#2-repository-structure)
3. [Data Flow — Forecast Request](#3-data-flow--forecast-request)
4. [Backend API Map](#4-backend-api-map)
5. [ML Pipeline — Training](#5-ml-pipeline--training)
6. [ML Pipeline — Inference (Forecast)](#6-ml-pipeline--inference-forecast)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Environment Variables & Config](#9-environment-variables--config)
10. [Risk Level Thresholds](#10-risk-level-thresholds)

---

## 1. System Overview

```mermaid
graph TB
    subgraph "User Devices"
        APP["📱 Mobile App\n(iOS / Android)"]
        WEB["🌐 Web Browser"]
    end

    subgraph "Frontend — Vercel"
        EXPO["HeatMAP-Frontend\nExpo / React Native\nTypeScript"]
    end

    subgraph "Backend — Render.com"
        API["Heatwave-AI-Backend-Elysia\nBun + Elysia\nTypeScript"]
        PY["Python ML Runtime\nprediction/forecast.py\nprediction/predict.py"]
        MODELS["Trained Models\n.pkl files\n(HuggingFace)"]
    end

    subgraph "External APIs"
        OM["☁️ Open-Meteo API\nReal weather data\n(free, no key)"]
    end

    APP --> EXPO
    WEB --> EXPO
    EXPO -->|"REST API calls"| API
    API -->|"spawn subprocess"| PY
    PY -->|"urllib.request"| OM
    PY --> MODELS
    PY -->|"writes JSON"| API
    API -->|"JSON response"| EXPO
```

---

## 2. Repository Structure

```
Heatwave-AI/                          ← Monorepo root
│
├── HeatMAP-Frontend/                 ← React Native / Expo app
│   ├── app/
│   │   ├── (tabs)/                   ← 5 main screens (tabs)
│   │   │   ├── map.tsx               ← Heatwave map view
│   │   │   ├── forecast.tsx          ← 30-day AI forecast
│   │   │   ├── alerts.tsx            ← Push alerts
│   │   │   ├── index.tsx             ← Safety guidelines
│   │   │   └── settings.tsx          ← App settings
│   │   └── _layout.tsx               ← Root layout + providers
│   ├── components/
│   │   ├── forecast/ForecastScreen.tsx  ← Forecast calendar UI
│   │   └── map/MapGrid.tsx           ← Map heat grid
│   ├── hooks/
│   │   ├── useForecast.ts            ← Forecast state + calendar logic
│   │   └── useWeather.ts             ← Open-Meteo current weather
│   └── services/
│       ├── apiService.ts             ← Base HTTP client (retry, timeout)
│       └── forecastService.ts        ← Forecast API calls
│
├── Heatwave-AI-Backend-Elysia/       ← API server
│   ├── src/index.ts                  ← All 11 endpoints
│   ├── prediction/
│   │   ├── forecast.py               ← Open-Meteo fetch → ML inference
│   │   ├── predict.py                ← Batch CSV prediction
│   │   └── predictor.py              ← Model loader class
│   ├── models/                       ← Downloaded .pkl files
│   ├── experiments/
│   │   ├── results/                  ← Model evaluation JSON
│   │   └── forecasts/                ← Generated forecast JSON/CSV
│   ├── config.yaml                   ← Model hyperparams + thresholds
│   ├── requirements.txt              ← Python dependencies
│   ├── Dockerfile.render             ← Docker build (Bun + Python3)
│   └── package.json
│
├── Heatwave-AI-TRAIN/                ← ML training pipeline
│   ├── pipelines/training_pipeline.py
│   ├── models/                       ← Model class implementations
│   ├── training/                     ← Trainer, cross-val, HPO
│   ├── evaluation/                   ← Metrics, leaderboard
│   ├── utils/                        ← Data loader, preprocessing
│   └── main.py                       ← CLI entry point
│
├── Era5-data-2000-2026/              ← ERA5 NetCDF climate data
├── ndvi/                             ← NDVI vegetation index data
├── render.yaml                       ← Render.com service config
├── docker-compose.yml                ← Local Docker dev setup
└── ARCHITECTURE.md                   ← This file
```

---

## 3. Data Flow — Forecast Request

```mermaid
sequenceDiagram
    actor User
    participant App as Frontend<br/>(Expo)
    participant Backend as Backend<br/>(Elysia / Bun)
    participant Python as Python<br/>(forecast.py)
    participant OpenMeteo as Open-Meteo<br/>API
    participant Model as ML Model<br/>(.pkl)

    User->>App: Tap "Run Forecast"<br/>(model=balanced_rf, days=7)
    App->>Backend: POST /api/forecast<br/>{ model, days, lat, lon }

    Backend->>Backend: Validate model whitelist<br/>Rate limit check (60/min)
    Backend->>Python: spawn python3 forecast.py<br/>--model balanced_rf --days 7<br/>--latitude 13.75 --longitude 100.50

    Python->>OpenMeteo: GET /v1/forecast<br/>hourly: temp, dewpoint,<br/>humidity, pressure, wind<br/>timeout=30s

    OpenMeteo-->>Python: 7 days × 24h hourly data

    Python->>Python: Aggregate hourly → daily<br/>Compute Heat Index (Rothfusz)<br/>Add NDVI seasonal climatology<br/>Build feature vector

    Python->>Model: predict(features)<br/>predict_proba(features)

    Model-->>Python: heatwave labels [0/1]<br/>probabilities [0.0–1.0]

    Python->>Python: Write forecast JSON<br/>experiments/forecasts/forecast_*.json

    Python-->>Backend: exit 0 (stdout log)

    Backend->>Backend: Read latest .json file<br/>Cleanup old files (keep 50)

    Backend-->>App: { success, forecast[], totalDays }

    App->>App: Build calendar grid<br/>Color cells by risk level

    App-->>User: Calendar heatmap<br/>🟢 Low  🟡 Moderate<br/>🟠 High  🔴 Extreme
```

---

## 4. Backend API Map

```mermaid
graph LR
    subgraph "GET endpoints"
        G1["GET /\nService info"]
        G2["GET /api/health\nHealth check (Render)"]
        G3["GET /api/results/leaderboard\nAll models ranked by F1"]
        G4["GET /api/results/best\nTop model"]
        G5["GET /api/results/all\nAll result JSONs"]
        G6["GET /api/results/:model\nSingle model result"]
        G7["GET /api/predict/models\nAvailable .pkl models"]
        G8["GET /api/predict/status\nConfig + models present?"]
        G9["GET /api/forecast/latest\nLatest cached forecast"]
    end

    subgraph "POST endpoints"
        P1["POST /api/predict\nBatch CSV prediction\n→ spawns predict.py"]
        P2["POST /api/forecast\nGenerate forecast\n→ spawns forecast.py"]
    end

    subgraph "Middleware"
        M1["CORS (all origins)"]
        M2["Rate Limit\n60 req / 60s / IP"]
        M3["Request Logger\nJSON structured logs"]
        M4["120s Process Timeout\nKills hung Python"]
    end
```

**Rate limiting:** 60 requests per IP per minute (in-memory, resets on restart).

---

## 5. ML Pipeline — Training

```mermaid
flowchart TD
    A["ERA5 NetCDF Data\n2000–2025\nt2m, d2m, sp, u10, v10"] --> B

    subgraph PREP["Data Preparation"]
        B["ERA5DataLoader\nLoad NetCDF files"] --> C
        C["HeatwavePreprocessor\nCompute Heat Index\nAdd NDVI lags\nLabel heatwave days"] --> D
        D["Year-based Split\nTrain: 2020–2024\nVal / Test: 2025\n(no temporal leakage)"]
    end

    D --> E["StandardScaler\nFit on train set only"]
    E --> F["Save scaler.pkl\nSave feature_names.pkl"]

    subgraph TRAIN["Parallel Training (5 models)"]
        G1["Balanced Random Forest\n200 trees, max_depth=15\nclass_weight='balanced_subsample'"]
        G2["XGBoost\n300 trees, max_depth=6\nlr=0.1, logloss"]
        G3["LightGBM\n300 trees, 63 leaves\nleaf-wise growth"]
        G4["MLP (PyTorch)\n256→128→64 neurons\n30% dropout, early stop"]
        G5["KAN (PyTorch)\n64→32 B-spline layers\nearly stop patience=8"]
    end

    F --> TRAIN

    TRAIN --> H["Evaluation\nPrecision, Recall, F1, ROC-AUC\non test set"]
    H --> I["leaderboard.json\nRanked by F1 score"]
    H --> J["Save *_model.pkl\nfor each trained model"]

    subgraph LABEL["Heatwave Label Definition"]
        L1["WBGT ≥ 32°C\nAND ≥ 2 consecutive days\n→ heatwave = 1\n(ISO 7243 / Thai MoPH standard)\nConfigurable: wbgt | heat_index | ehf | tropical_night"]
    end
```

**Heatwave label (default):** WBGT ≥ 32 °C for ≥ 2 consecutive days = `heatwave = 1`.
WBGT (Wet-Bulb Globe Temperature) is used because Thailand's hot-humid climate makes
pure temperature thresholds insufficient — sweat evaporates poorly at high RH. The 32 °C
threshold matches Thailand's MoPH public-advisory level. Formula: ABoM outdoor approximation
(Lemke & Kjellstrom 2012): `WBGT = 0.567·T + 0.393·e + 3.94` where `e` is vapor pressure.

**Data split:** 2000–2019 used as climatology baseline (percentile labels only),
2020–2024 as training data, 2025 as the held-out validation year.

---

## 6. ML Pipeline — Inference (Forecast)

```mermaid
flowchart LR
    subgraph INPUT["Inputs"]
        A1["--model balanced_rf"]
        A2["--days 7"]
        A3["--latitude 13.75\n--longitude 100.50"]
        A4["--config config.yaml"]
    end

    subgraph FETCH["1. Fetch Weather"]
        B["Open-Meteo API\nhourly data\n7 days × 24h"]
        B --> C["Aggregate to daily\ntemp=MAX\nothers=MEAN"]
    end

    subgraph ENGINEER["2. Feature Engineering"]
        D["Heat Index\n(Rothfusz regression)\nonly if T≥26.7°C AND RH≥40%"]
        E["Wind Components\nu10, v10\nfrom speed + direction"]
        F["NDVI Seasonal\nClimatology\n(MODIS long-term mean)"]
        G["Kelvin conversions\nt2m = t2m_c + 273.15\nd2m = d2m_c + 273.15"]
    end

    subgraph PREDICT["3. Predict"]
        H["Load scaler.pkl\nLoad model.pkl"]
        I["scaler.transform(features)"]
        J["model.predict()\nmodel.predict_proba()"]
    end

    subgraph OUTPUT["4. Output"]
        K["experiments/forecasts/\nforecast_balanced_rf_YYYYMMDD_7d.json\nforecast_balanced_rf_YYYYMMDD_7d.csv"]
    end

    INPUT --> FETCH
    C --> ENGINEER
    ENGINEER --> PREDICT
    H --> I --> J --> OUTPUT
```

**Feature vector (8 features):** `t2m`, `d2m`, `sp`, `u10`, `v10`, `ndvi`, `ndvi_lag1`, `ndvi_lag2`

---

## 7. Frontend Architecture

```mermaid
graph TB
    subgraph "Navigation (Expo Router)"
        TAB1["map\nHeatwave Map"]
        TAB2["forecast\nAI Forecast"]
        TAB3["alerts\nPush Alerts"]
        TAB4["index\nSafety Guide"]
        TAB5["settings\nPreferences"]
    end

    subgraph "Hooks (State)"
        H1["useForecast()\n- fetch from API\n- build calendar grid\n- compute stats"]
        H2["useWeather()\n- Open-Meteo direct\n- 10min cache\n- current + 7-day"]
        H3["useLocation()\n- GPS permission\n- fallback: Bangkok"]
        H4["useSettings()\n- theme dark/light\n- language EN/TH\n- font size"]
    end

    subgraph "Services (API)"
        S1["apiService.ts\n- 15s timeout\n- 2 retries\n- exponential backoff"]
        S2["forecastService.ts\n- POST /api/forecast\n- GET /api/forecast/latest\n- GET /api/predict/models"]
        S3["weatherService.ts\n- Open-Meteo direct\n- AQI data"]
    end

    subgraph "Key Components"
        C1["ForecastScreen.tsx\n- Model selector\n- Days selector\n- Calendar heatmap"]
        C2["MapGrid.tsx\n- Heat risk grid\n- Location overlay"]
    end

    TAB2 --> H1
    TAB1 --> H2
    H1 --> S2
    S2 --> S1
    H2 --> S3
    H3 --> TAB2
    H4 --> TAB5
    C1 --> TAB2
    C2 --> TAB1
```

**Supported platforms:** iOS, Android, Web (same codebase via Expo).

**Localization:** English + Thai (`i18n/` directory).

---

## 8. Deployment Architecture

```mermaid
graph TB
    subgraph "GitHub"
        REPO["github.com/MCTEEKUNG/\nHeatwave_Backend_Elysia\nbranch: main"]
    end

    subgraph "Render.com (Backend)"
        BUILD["Docker Build\noven/bun:1-slim\n+ python3 + venv"]
        DL["Download from HuggingFace\nbalanced_random_forest_model.pkl\nscaler.pkl\nfeature_names.pkl"]
        RUN["Container\nPort 10000\nWORKDIR /app"]
        HC["Health Check\nGET /api/health\nevery 30s"]
    end

    subgraph "Vercel (Frontend)"
        FE["React Native Web\nEXPO_PUBLIC_API_URL=\nhttps://heatwave-backend-elysia.onrender.com"]
    end

    subgraph "Local Docker"
        DC["docker-compose up -d\nPort 3000\nVolume: experiments/"]
    end

    REPO -->|"autoDeploy: true\ngit push triggers"| BUILD
    BUILD --> DL --> RUN
    RUN --> HC
    FE -->|"REST calls"| RUN
    DC -->|"same Dockerfile.render"| RUN
```

**Render free tier note:** First request after idle may take ~30s to wake up. The frontend uses a 45s timeout on `getLatestForecast` to handle this.

---

## 9. Environment Variables & Config

| Variable | Where | Value | Purpose |
|----------|-------|-------|---------|
| `PORT` | Backend | `10000` (Render) / `3000` (local) | Server listen port |
| `NODE_ENV` | Backend | `production` | Enables prod optimizations |
| `EXPO_PUBLIC_API_URL` | Frontend `.env` | `https://heatwave-backend-elysia.onrender.com` | Backend base URL |
| `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` | Frontend `.env` | *(optional)* | Maps integration |

**`config.yaml` key settings:**

| Setting | Value | Notes |
|---------|-------|-------|
| `heatwave_heat_index_threshold` | `35.0 °C` | Trigger threshold |
| `heatwave_min_consecutive_days` | `2` | Min days in a row |
| `features` | `t2m, d2m, sp, u10, v10, ndvi, ndvi_lag1, ndvi_lag2` | 8 model features |
| `split` | `70/15/15` | train/val/test |
| `gpu` | `false` | CPU inference only |

---

## 10. Risk Level Thresholds

| Level | Probability Range | Color | Meaning |
|-------|------------------|-------|---------|
| Low | < 0.40 | `#22C55E` Green | Safe conditions |
| Moderate | 0.40 – 0.59 | `#EAB308` Yellow | Caution advised |
| High | 0.60 – 0.79 | `#F97316` Orange | Avoid outdoor activity |
| Extreme | ≥ 0.80 | `#EF4444` Red | Dangerous heat risk |

These thresholds are defined in `HeatMAP-Frontend/services/forecastService.ts` and used to color each calendar day in `ForecastScreen.tsx`.

---

## Quick Start

```bash
# 1. Backend (local Docker)
docker-compose up --build

# 2. Frontend
cd HeatMAP-Frontend
npm install
npm run web          # Browser
npm run android      # Android emulator
npm run ios          # iOS simulator

# 3. Test the API
curl http://localhost:3000/api/health
curl -X POST http://localhost:3000/api/forecast \
  -H "Content-Type: application/json" \
  -d '{"model":"balanced_rf","days":7}'

# 4. Train models (Google Colab or GPU machine)
cd Heatwave-AI-TRAIN
pip install -r requirements.txt
python main.py --mode train
```

---

*Last updated: May 2026*
