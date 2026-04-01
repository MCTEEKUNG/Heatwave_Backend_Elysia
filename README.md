# Heatwave AI Backend (Elysia + Bun)

Fast backend service built with Elysia and Bun to retrieve prediction results from Heatwave AI.

## Setup

```bash
cd Heatwave-AI-Backend-Elysia
bun install
```

## Run

```bash
bun run src/index.ts
```

Or with hot reload:

```bash
bun run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/api/health` | Health check |
| GET | `/api/predict/models` | List available models |
| GET | `/api/predict/status` | Check prediction service status |
| POST | `/api/predict` | Run prediction |

### POST `/api/predict`

**Request:**
```json
{
  "model": "xgboost",
  "inputData": "temperature,humidity,pressure,wind_speed\n35.2,45,1013,12.5",
  "includeProba": true
}
```

**Response:**
```json
{
  "success": true,
  "predictions": [
    {
      "temperature": "35.2",
      "predicted_heatwave": "1",
      "heatwave_probability": "0.85"
    }
  ],
  "model": "xgboost"
}
```

## Available Models

- `xgboost`
- `lightgbm`
- `balanced_rf`
- `mlp`
- `kan`
