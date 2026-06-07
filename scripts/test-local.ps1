# Local-prod test (maintainer inner-loop sub-2) — test a promoted candidate in the
# REAL app, isolated from Supabase.
#
# 1) Generates forecasts with the current production model (models/heatwave_model.pkl,
#    i.e. whatever you just promoted) into a LOCAL staging file.
# 2) Starts the backend in STAGING mode (reads the file, never touches Supabase).
# 3) Starts the Expo web app pointed at the staging backend.
#
# Usage (from repo root):  powershell -ExecutionPolicy Bypass -File scripts\test-local.ps1
# Stop:  close the two spawned windows (backend :3001, web :8082).
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$stg  = Join-Path $repo 'data\processed\forecast_store_staging.json'
$front = Join-Path $repo 'HeatMAP-Frontend'

Write-Host "[1/3] Generating staging forecasts (LOCAL — Supabase NOT touched)..." -ForegroundColor Cyan
Write-Host "      (all 77 provinces; set `$env:HEATWAVE_SLEEP=2 to go faster on a paid Open-Meteo plan)"
& $py (Join-Path $repo 'scripts\run_daily_forecast.py') --staging --staging-out $stg --state-file (Join-Path $repo 'staging_state.json')

Write-Host "[2/3] Starting backend in STAGING mode on :3001..." -ForegroundColor Cyan
$env:HEATWAVE_FORECAST_FILE = $stg
$env:PORT = '3001'
$env:ALLOWED_ORIGINS = 'http://localhost:8082,http://localhost:8081'
Start-Process -FilePath 'bun' -ArgumentList 'run','src/index.ts' -WorkingDirectory $repo | Out-Null

Write-Host "[3/3] Starting Expo web on :8082 (pointed at the staging backend)..." -ForegroundColor Cyan
$env:EXPO_PUBLIC_API_URL = 'http://localhost:3001'
$env:CI = '1'
Start-Process -FilePath 'bun' -ArgumentList 'run','web','--','--port','8082' -WorkingDirectory $front | Out-Null

Start-Sleep -Seconds 3
Write-Host "`nLocal-prod test up:" -ForegroundColor Green
Write-Host "  backend (staging) : http://localhost:3001/api/forecast/map"
Write-Host "  app               : http://localhost:8082"
Write-Host "If it looks right, deploy for real (sub-3). Supabase was never touched."
