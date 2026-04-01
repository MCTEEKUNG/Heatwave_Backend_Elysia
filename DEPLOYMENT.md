# Heatwave AI - Deployment Guide

## Overview

This app has 3 components:
1. **Backend API** (Elysia + Bun) - Serves forecast data
2. **Python ML System** (Heatwave-AI-TRAIN) - Runs predictions
3. **Frontend** (Expo/React Native) - User interface

---

## Option 1: Deploy to VPS (Recommended)

### Prerequisites
- Ubuntu 22.04+ VPS (2GB+ RAM)
- Domain name (optional)
- Python 3.9+
- Bun runtime

### Step 1: Setup Server

```bash
# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install Python dependencies
cd Heatwave-AI-TRAIN
pip install -r requirements.txt

# Train models (if not done)
python main.py --mode train

# Generate forecast
python prediction/forecast.py --model balanced_rf --days 30 --cycles 3
```

### Step 2: Start Backend

```bash
cd Heatwave-AI-Backend-Elysia
bun install

# Run in background
nohup bun run src/index.ts > backend.log 2>&1 &

# Or use PM2
npm install -g pm2
pm2 start "bun run src/index.ts" --name heatwave-backend
pm2 save
pm2 startup
```

### Step 3: Setup Nginx (Optional)

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/heatwave

# Add:
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

sudo ln -s /etc/nginx/sites-available/heatwave /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 4: Build Frontend

```bash
cd HeatMAP-Frontend

# Update API URL in .env
echo "EXPO_PUBLIC_API_URL=https://your-domain.com" > .env

# Build for web
npx expo export --platform web

# Deploy to Vercel
npx vercel --prod
```

---

## Option 2: Deploy with Docker

```bash
# Build and run
docker compose up -d

# Check logs
docker compose logs -f backend
```

---

## Option 3: Deploy to Cloud Platforms

### Backend (Railway/Render)
1. Push code to GitHub
2. Connect repo to Railway/Render
3. Set build command: `bun install`
4. Set start command: `bun run src/index.ts`
5. Add volume for `Heatwave-AI-TRAIN` data

### Frontend (Vercel)
1. Push to GitHub
2. Connect to Vercel
3. Set `EXPO_PUBLIC_API_URL` env var
4. Deploy

---

## Update Frontend API URL

Edit `HeatMAP-Frontend/services/forecastService.ts`:

```typescript
const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000';
```

---

## Production Checklist

- [ ] Backend running on public URL
- [ ] CORS configured for frontend domain
- [ ] SSL certificate (Let's Encrypt)
- [ ] Environment variables set
- [ ] Models trained and forecasts generated
- [ ] Frontend API URL updated
- [ ] App tested on production URL
