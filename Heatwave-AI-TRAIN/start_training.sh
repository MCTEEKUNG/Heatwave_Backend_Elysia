#!/usr/bin/env bash
# ============================================================
#  HEATWAVE-AI  |  Training Quick-Start
#  Linux / macOS version of Start.bat
#
#  Clone the repo, copy your ERA5 + NDVI data next to this
#  directory, then run:
#
#    bash start_training.sh
#
#  Data layout expected (relative to this script):
#    ../Era5-data-2000-2026/era5_surface_YYYY.nc
#    ../ndvi/ndvi_aligned_era5.nc          (optional)
# ============================================================

set -euo pipefail

# ── Always run from the directory containing this script ────
cd "$(dirname "$0")"

# ── Colours ─────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "  ${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "  ${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "  ${RED}[ERROR]${NC} $*"; }
step()  { echo -e "\n  ${CYAN}━━━ $* ━━━${NC}"; }
banner(){
  echo ""
  echo -e "  ${BOLD}============================================================${NC}"
  echo -e "  ${BOLD} HEATWAVE-AI  |  Modular AI Experimentation Framework${NC}"
  echo -e "  ${BOLD}============================================================${NC}"
  echo ""
}

VENV_DIR=".venv"
DEPS_FLAG=".deps_installed"
CUDA_FLAG=".cuda_upgraded"

# ────────────────────────────────────────────────────────────
# SETUP
# ────────────────────────────────────────────────────────────

banner

# ── 1. Find Python 3.9+ ─────────────────────────────────────
step "Checking Python"
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3 python; do
  if command -v "$cmd" &>/dev/null 2>&1; then
    PY_MAJ=$("$cmd" -c 'import sys; print(sys.version_info.major)' 2>/dev/null || echo 0)
    PY_MIN=$("$cmd" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo 0)
    if [ "$PY_MAJ" -ge 3 ] && [ "$PY_MIN" -ge 9 ]; then
      PYTHON_CMD="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  err "Python 3.9+ not found. Install from https://python.org"
  exit 1
fi
info "Found $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"

# ── 2. Virtual environment ───────────────────────────────────
step "Virtual environment"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  rm -f "$DEPS_FLAG" "$CUDA_FLAG"   # force reinstall on fresh venv
  info "Created new virtual environment in $VENV_DIR/"
else
  info "Using existing $VENV_DIR/"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 3. Install / upgrade dependencies ───────────────────────
step "Dependencies"
if [ ! -f "$DEPS_FLAG" ]; then
  echo "  Installing packages (this takes ~2 min on first run)..."
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  touch "$DEPS_FLAG"
  info "All packages installed."
else
  info "Already installed. (Delete $DEPS_FLAG to force reinstall)"
fi

# ── 4. GPU / CUDA detection ──────────────────────────────────
step "GPU detection"
HAS_NVIDIA=false
if command -v nvidia-smi &>/dev/null 2>&1; then
  GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "")
  if [ -n "$GPU_NAME" ]; then
    HAS_NVIDIA=true
    echo "  NVIDIA GPU: $GPU_NAME"
  fi
fi

TORCH_CUDA=$(python -c "import torch; print(torch.cuda.is_available())" 2>/dev/null || echo "False")

if $HAS_NVIDIA && [ "$TORCH_CUDA" = "False" ] && [ ! -f "$CUDA_FLAG" ]; then
  warn "CPU-only PyTorch detected but NVIDIA GPU is present. Upgrading to CUDA build..."
  CUDA_VER=$(nvidia-smi | grep -oP "CUDA Version: \K[\d.]+" 2>/dev/null || echo "")
  if [[ "$CUDA_VER" == 12.* ]]; then
    pip install --quiet --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121
  elif [[ "$CUDA_VER" == 11.* ]]; then
    pip install --quiet --force-reinstall torch --index-url https://download.pytorch.org/whl/cu118
  else
    warn "Could not detect CUDA version — skipping torch upgrade. Install manually if needed."
  fi
  if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    touch "$CUDA_FLAG"
    info "PyTorch CUDA build installed."
  else
    warn "CUDA upgrade attempted but torch.cuda.is_available() still False."
  fi
elif $HAS_NVIDIA && [ "$TORCH_CUDA" = "True" ]; then
  GPU_MEM=$(python -c "import torch; print(round(torch.cuda.get_device_properties(0).total_memory/1024**3,1))" 2>/dev/null || echo "?")
  info "CUDA ready — $GPU_NAME  |  ${GPU_MEM} GB VRAM  |  torch $(python -c 'import torch;print(torch.__version__)')"
elif python -c "import torch; print(torch.backends.mps.is_available())" 2>/dev/null | grep -q True; then
  info "Apple MPS (Metal) available — PyTorch will use MPS."
else
  info "No GPU found — training will run on CPU."
fi

# ── 5. Data check ────────────────────────────────────────────
step "Data check"
DATA_DIR="../Era5-data-2000-2026"
NDVI_FILE="../ndvi/ndvi_aligned_era5.nc"
DATA_OK=true

if [ -d "$DATA_DIR" ]; then
  NC_COUNT=$(find "$DATA_DIR" -name "*.nc" 2>/dev/null | wc -l | tr -d ' ')
  info "ERA5 data: $NC_COUNT .nc files found in $DATA_DIR/"
  if [ "$NC_COUNT" -lt 10 ]; then
    warn "Only $NC_COUNT files found — expected ~52 (surface + upper, 2000-2025)."
  fi
else
  err "ERA5 data directory not found: $DATA_DIR"
  echo ""
  echo "  Copy or symlink your ERA5 data so the layout looks like:"
  echo "    $(pwd)/../Era5-data-2000-2026/era5_surface_2020.nc"
  echo "    $(pwd)/../Era5-data-2000-2026/era5_surface_2025.nc  ← val year"
  echo ""
  DATA_OK=false
fi

if [ -f "$NDVI_FILE" ]; then
  info "NDVI processed file found: $NDVI_FILE"
else
  warn "NDVI file not found: $NDVI_FILE"
  echo "    (Optional — training runs without NDVI if ndvi.enabled: false in config)"
fi

echo ""

# ────────────────────────────────────────────────────────────
# MENU
# ────────────────────────────────────────────────────────────

show_menu() {
  echo ""
  echo -e "  ${BOLD}============================================================${NC}"
  echo -e "  ${BOLD} What would you like to do?${NC}"
  echo -e "  ${BOLD}============================================================${NC}"
  echo ""
  echo "    [0]  Verify data              (check ERA5 + NDVI files)"
  echo "    [1]  Run EDA                  (data quality + drift reports)"
  echo "    [2]  Train ALL models         (balanced_rf, xgb, lgbm, mlp, kan)"
  echo "    [3]  Train SELECTED models    (choose which to train)"
  echo "    [4]  Run prediction (CLI)     (requires trained models)"
  echo "    [5]  Launch dashboard         (requires trained models)"
  echo "    [6]  Exit"
  echo ""
  printf "  Enter choice [0-6]: "
}

do_train() {
  local MODELS_ARG="$1"
  if [ -z "$MODELS_ARG" ]; then
    python main.py --mode train
  else
    # shellcheck disable=SC2086
    python main.py --mode train --models $MODELS_ARG
  fi
}

while true; do
  show_menu
  read -r CHOICE

  case "$CHOICE" in

    0)
      echo ""
      step "Verifying data"
      python import_data.py || warn "Verification script returned errors."
      ;;

    1)
      echo ""
      step "Running EDA pipeline"
      echo "  This processes all ERA5 years — may take 10-30 min on first run."
      echo ""
      python -m eda.run_all || warn "EDA completed with errors. Check output above."
      echo ""
      info "EDA artifacts in: experiments/eda/"
      info "Summary report : experiments/eda/eda_report.md"
      ;;

    2)
      echo ""
      step "Training ALL 5 models"
      do_train "" && info "Training complete." || err "Training failed."
      ;;

    3)
      echo ""
      step "Select models to train"
      echo "    [1]  balanced_rf   Balanced Random Forest (CPU-friendly)"
      echo "    [2]  xgboost       XGBoost (GPU accelerated)"
      echo "    [3]  lightgbm      LightGBM (GPU accelerated)"
      echo "    [4]  mlp           MLP Neural Network (PyTorch)"
      echo "    [5]  kan           KAN Network (PyTorch)"
      echo "    [A]  All models"
      echo ""
      printf "  Enter numbers separated by spaces (e.g. 1 2) or A: "
      read -r MODEL_CHOICE

      if [[ "${MODEL_CHOICE,,}" == "a" ]]; then
        do_train "" && info "Training complete." || err "Training failed."
      else
        SELECTED=""
        for N in $MODEL_CHOICE; do
          case "$N" in
            1) SELECTED="$SELECTED balanced_rf" ;;
            2) SELECTED="$SELECTED xgboost"     ;;
            3) SELECTED="$SELECTED lightgbm"    ;;
            4) SELECTED="$SELECTED mlp"          ;;
            5) SELECTED="$SELECTED kan"          ;;
            *) warn "Unknown model number: $N"  ;;
          esac
        done
        if [ -z "$SELECTED" ]; then
          warn "No valid models selected."
        else
          echo "  Training:$SELECTED"
          do_train "$SELECTED" && info "Training complete." || err "Training failed."
        fi
      fi
      ;;

    4)
      echo ""
      step "Run prediction"
      echo "    [1]  balanced_rf   [2]  xgboost   [3]  lightgbm   [4]  mlp   [5]  kan"
      printf "  Select model [1-5]: "
      read -r PRED_NUM
      case "$PRED_NUM" in
        1) PRED_MODEL="balanced_rf" ;;
        2) PRED_MODEL="xgboost"     ;;
        3) PRED_MODEL="lightgbm"    ;;
        4) PRED_MODEL="mlp"         ;;
        5) PRED_MODEL="kan"         ;;
        *) warn "Invalid selection."; continue ;;
      esac
      printf "  Input CSV path: "
      read -r PRED_INPUT
      printf "  Output CSV path (Enter to skip): "
      read -r PRED_OUTPUT
      printf "  Include probabilities? (y/n): "
      read -r PRED_PROBA

      CMD="python main.py --mode predict --model $PRED_MODEL --input $PRED_INPUT"
      [ -n "$PRED_OUTPUT" ] && CMD="$CMD --output $PRED_OUTPUT"
      [[ "${PRED_PROBA,,}" == "y" ]] && CMD="$CMD --proba"
      $CMD || err "Prediction failed."
      ;;

    5)
      echo ""
      step "Launching dashboard"
      echo "  Dashboard: http://localhost:5000   (Ctrl+C to stop)"
      echo ""
      python main.py --mode dashboard
      ;;

    6|q|Q)
      echo ""
      echo "  Goodbye!"
      echo ""
      exit 0
      ;;

    *)
      warn "Invalid choice. Enter 0-6."
      ;;

  esac

  echo ""
  printf "  Press Enter to return to menu..."
  read -r
done
