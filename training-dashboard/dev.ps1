# One-command launcher for the Heatwave Training Dashboard (LOCAL dev tool).
# Starts the FastAPI control server (:8000) and the Vite web UI (:5173) in their
# own windows (so you see logs), then opens the dashboard in your browser.
#
# Usage (from anywhere):  powershell -ExecutionPolicy Bypass -File training-dashboard\dev.ps1
# or just:                training-dashboard\dev.cmd
$ErrorActionPreference = 'Stop'

$here = $PSScriptRoot
$repo = Split-Path -Parent $here
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$web  = Join-Path $here 'web'

if (-not (Test-Path $py)) {
  Write-Error ".venv not found at $py`nRun:  python -m venv .venv ; .\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt"
  exit 1
}
if (-not (Test-Path (Join-Path $web 'node_modules'))) {
  Write-Host "web/node_modules missing - running 'bun install'..." -ForegroundColor Yellow
  Push-Location $web; bun install; Pop-Location
}

function Stop-Port([int]$p) {
  Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

Write-Host "Freeing ports 8000 / 5173 (if in use)..." -ForegroundColor Cyan
Stop-Port 8000; Stop-Port 5173

# FastAPI control server -- MUST run from the repo root so `pipeline` and `src` import.
Start-Process -FilePath $py `
  -ArgumentList '-m','uvicorn','server.app:app','--app-dir','training-dashboard','--host','127.0.0.1','--port','8000' `
  -WorkingDirectory $repo | Out-Null

# Vite web UI (served on 127.0.0.1:5173).
Start-Process -FilePath 'bun' -ArgumentList 'run','dev' -WorkingDirectory $web | Out-Null

Start-Sleep -Seconds 2
Start-Process 'http://127.0.0.1:5173' | Out-Null

Write-Host ""
Write-Host "Heatwave Training Dashboard is up:" -ForegroundColor Green
Write-Host "  Web UI : http://127.0.0.1:5173"
Write-Host "  API    : http://127.0.0.1:8000  (health: /healthz)"
Write-Host ""
Write-Host "Two windows opened (server + web) -- close them to stop, or run:" -ForegroundColor Yellow
Write-Host "  training-dashboard\stop.ps1"
