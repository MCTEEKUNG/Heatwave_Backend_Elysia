@echo off
title HEATWAVE-AI Prediction System
color 0A

echo.
echo  ============================================================
echo   HEATWAVE-AI  ^|  Modular AI Experimentation Framework
echo  ============================================================
echo.

:: ── Activate virtual environment ──────────────────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo  [WARN] No virtual environment found. Using system Python.
)

:: ── Check Python ──────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found in PATH. Please install Python 3.9+.
    pause
    exit /b 1
)

:: ── Install dependencies if needed ────────────────────────────────
if not exist ".deps_installed" (
    echo  [Step 0] Installing base dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo  [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo  [OK] Dependencies installed.
    echo.
)

:: ── GPU / PyTorch CUDA Check (single Python spawn) ────────────────
echo  ============================================================
echo   GPU / Device Detection
echo  ============================================================

if not exist ".cuda_upgraded" (
    python -c "import torch,shutil,sys; cpu='+cpu' in torch.__version__; gpu=shutil.which('nvidia-smi') is not None; avail=torch.cuda.is_available(); n=torch.cuda.get_device_name(0) if avail else 'N/A'; v=round(torch.cuda.get_device_properties(0).total_memory/1024**3,1) if avail else 0; print(f'  [GPU] {n}  |  {v} GB VRAM  |  torch {torch.__version__}') if avail else (print('  [WARN] CPU-only PyTorch detected. Upgrading...') if (cpu and gpu) else print(f'  [CPU] No CUDA GPU  |  torch {torch.__version__}')); sys.exit(2 if (cpu and gpu) else 0)" 2>nul
    if errorlevel 2 (
        echo  [INFO] Installing CUDA 12.6 PyTorch build...
        pip install --force-reinstall "torch==2.10.0+cu126" torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126 -q
        if not errorlevel 1 (
            echo. > .cuda_upgraded
            echo  [OK] PyTorch CUDA build installed.
            python -c "import torch; avail=torch.cuda.is_available(); n=torch.cuda.get_device_name(0) if avail else 'N/A'; v=round(torch.cuda.get_device_properties(0).total_memory/1024**3,1) if avail else 0; print(f'  [GPU] {n}  |  {v} GB VRAM  |  torch {torch.__version__}')" 2>nul
        ) else (
            echo  [WARN] CUDA install failed. Continuing with CPU build.
        )
    )
) else (
    python -c "import torch; avail=torch.cuda.is_available(); n=torch.cuda.get_device_name(0) if avail else 'N/A'; v=round(torch.cuda.get_device_properties(0).total_memory/1024**3,1) if avail else 0; print(f'  [GPU] {n}  |  {v} GB VRAM  |  torch {torch.__version__}') if avail else print(f'  [CPU] No CUDA GPU  |  torch {torch.__version__}')" 2>nul
)
echo.

:: ── Interactive Menu ───────────────────────────────────────────────
:MENU
echo  ============================================================
echo   What would you like to do?
echo  ============================================================
echo.
echo    [0]  Import & verify data       (check ERA5 + NDVI)
echo    [1]  Train ALL models           (all 5 models)
echo    [2]  Train SELECTED models      (choose which models)
echo    [3]  Launch dashboard only      (requires trained models)
echo    [4]  Train ALL + Launch dashboard
echo    [5]  Run prediction (CLI)
echo    [6]  Exit
echo.
set /p CHOICE=  Enter choice [0-6]:

if "%CHOICE%"=="0" goto IMPORT_DATA
if "%CHOICE%"=="1" goto TRAIN_ALL
if "%CHOICE%"=="2" goto TRAIN_SELECT
if "%CHOICE%"=="3" goto DASHBOARD
if "%CHOICE%"=="4" goto TRAIN_THEN_DASH
if "%CHOICE%"=="5" goto PREDICT
if "%CHOICE%"=="6" goto END

echo  [WARN] Invalid choice. Please enter 0-6.
echo.
goto MENU

:: ── Import Data ────────────────────────────────────────────────────
:IMPORT_DATA
echo.
echo  ============================================================
echo   Import & Verify Data
echo  ============================================================
echo.
python import_data.py
if errorlevel 1 (
    echo.
    echo  [ERROR] Data import/verification failed.
    pause
    goto MENU
)
echo.
echo  [OK] Data verification complete.
pause
goto MENU

:: ── Train ALL ──────────────────────────────────────────────────────
:TRAIN_ALL
echo.
echo  ============================================================
echo   Training All 5 AI Models
echo  ============================================================
echo.
python main.py --mode train
if errorlevel 1 (
    echo.
    echo  [ERROR] Training pipeline failed.
    pause
    goto MENU
)
echo.
echo  [OK] Training complete.
pause
goto MENU

:: ── Train SELECTED ─────────────────────────────────────────────────
:TRAIN_SELECT
echo.
echo  ============================================================
echo   Select Models to Train
echo  ============================================================
echo.
echo   Available models:
echo     [1]  balanced_rf   - Balanced Random Forest
echo     [2]  xgboost       - XGBoost (GPU accelerated)
echo     [3]  lightgbm      - LightGBM (GPU accelerated)
echo     [4]  mlp           - MLP Neural Network (GPU + AMP)
echo     [5]  kan           - KAN Network (GPU + AMP)
echo     [A]  All models
echo.
echo   Enter model numbers separated by spaces (e.g.: 2 4 5)
echo   or enter A for all models.
echo.
set /p MODEL_CHOICE=  Your selection:

set TRAIN_MODELS=

:: Check for "A" (all)
if /i "%MODEL_CHOICE%"=="A" (
    echo.
    echo  Training all 5 models...
    python main.py --mode train
    goto TRAIN_SELECT_DONE
)

:: Build model list from numbers
for %%N in (%MODEL_CHOICE%) do (
    if "%%N"=="1" set TRAIN_MODELS=%TRAIN_MODELS% balanced_rf
    if "%%N"=="2" set TRAIN_MODELS=%TRAIN_MODELS% xgboost
    if "%%N"=="3" set TRAIN_MODELS=%TRAIN_MODELS% lightgbm
    if "%%N"=="4" set TRAIN_MODELS=%TRAIN_MODELS% mlp
    if "%%N"=="5" set TRAIN_MODELS=%TRAIN_MODELS% kan
)

if "%TRAIN_MODELS%"=="" (
    echo  [WARN] No valid models selected.
    pause
    goto MENU
)

echo.
echo  Training:%TRAIN_MODELS%
echo.
python main.py --mode train --models%TRAIN_MODELS%

:TRAIN_SELECT_DONE
if errorlevel 1 (
    echo.
    echo  [ERROR] Training failed.
    pause
    goto MENU
)
echo.
echo  [OK] Training complete.
pause
goto MENU

:: ── Dashboard only ─────────────────────────────────────────────────
:DASHBOARD
echo.
echo  ============================================================
echo   Launching Dashboard
echo  ============================================================
echo.
echo  Dashboard: http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python main.py --mode dashboard
pause
goto MENU

:: ── Train ALL then dashboard ───────────────────────────────────────
:TRAIN_THEN_DASH
echo.
echo  ============================================================
echo   Step 1/2 : Training All AI Models
echo  ============================================================
echo.
python main.py --mode train
if errorlevel 1 (
    echo.
    echo  [ERROR] Training pipeline failed.
    pause
    goto MENU
)
echo.
echo  ============================================================
echo   Step 2/2 : Launching Dashboard
echo  ============================================================
echo.
echo  Dashboard: http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python main.py --mode dashboard
pause
goto MENU

:: ── Predict ────────────────────────────────────────────────────────
:PREDICT
echo.
echo  ============================================================
echo   Run Prediction
echo  ============================================================
echo.
echo   Available models:
echo     [1]  balanced_rf
echo     [2]  xgboost
echo     [3]  lightgbm
echo     [4]  mlp
echo     [5]  kan
echo.
set /p PRED_NUM=  Select model number [1-5]:
set PRED_MODEL=
if "%PRED_NUM%"=="1" set PRED_MODEL=balanced_rf
if "%PRED_NUM%"=="2" set PRED_MODEL=xgboost
if "%PRED_NUM%"=="3" set PRED_MODEL=lightgbm
if "%PRED_NUM%"=="4" set PRED_MODEL=mlp
if "%PRED_NUM%"=="5" set PRED_MODEL=kan

if "%PRED_MODEL%"=="" (
    echo  [WARN] Invalid selection.
    pause
    goto MENU
)

set /p PRED_INPUT=  Input CSV path:
set /p PRED_OUTPUT=  Output CSV path (press Enter to skip):
set /p PRED_PROBA=  Include probabilities? (y/n):

set PRED_ARGS=--mode predict --model %PRED_MODEL% --input %PRED_INPUT%
if not "%PRED_OUTPUT%"=="" set PRED_ARGS=%PRED_ARGS% --output %PRED_OUTPUT%
if /i "%PRED_PROBA%"=="y" set PRED_ARGS=%PRED_ARGS% --proba

echo.
python main.py %PRED_ARGS%
if errorlevel 1 (
    echo  [ERROR] Prediction failed.
)
pause
goto MENU

:: ── End ────────────────────────────────────────────────────────────
:END
echo.
echo  Goodbye!
echo.
exit /b 0
