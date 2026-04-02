#!/usr/bin/env bash
# =============================================================================
#  HRI_lab_Pepper — Student Install Script
#
#  Minimal install — no PyTorch, no CUDA stack, no cuDNN.
#  Uses OpenVINO for inference — Intel's own engine, ~2–3× faster than
#  plain ONNX Runtime on the i7-8700 (AVX2, Coffee Lake).
#
#  Approximate download sizes
#  --------------------------
#    openvino                   ~100 MB
#    opencv-python-headless      ~25 MB
#    vosk + model                ~5 MB + 50 MB
#    fastapi + uvicorn            ~5 MB
#    numpy, psutil               ~25 MB
#    yolov8n_openvino_model/     ~12 MB  (one-time, uses existing project venv)
#  --------------------------
#  Total:   ~220 MB
#  GPU (A4000/RTX-class with cuDNN): use install_gpu.sh instead.
#
#  Can be run from any directory:
#      bash HRI_lab_Pepper/install.sh
#      # or:
#      cd HRI_lab_Pepper && bash install.sh
#
#  After installation:
#      source .venv/bin/activate   (from the project root)
#      python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559
# =============================================================================
set -euo pipefail

# Resolve paths early so the script works regardless of where it is called from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VENV_DIR="$REPO_ROOT/.venv"
PYTHON=${PYTHON:-python3}

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

log()  { echo -e "${BLUE}[install]${RESET} $*"; }
ok()   { echo -e "${GREEN}[ok]${RESET}     $*"; }
warn() { echo -e "${YELLOW}[warn]${RESET}   $*"; }
err()  { echo -e "${RED}[error]${RESET}  $*" >&2; exit 1; }

# ── Require Python 3.9+ ───────────────────────────────────────────────────────
log "Checking Python version …"
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    err "Python 3.9+ required (found $PY_VER). Install a newer Python and re-run."
fi
ok "Python $PY_VER"

# ── No GPU branch needed — OpenVINO runs on CPU ─────────────────────────────────
# OpenVINO uses AVX2 + FMA on the i7-8700, giving ~2–3× the throughput of
# plain ONNX Runtime CPU.  No cuDNN or CUDA runtime required.
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    warn "GPU detected ($GPU_NAME) — using OpenVINO CPU (best choice for GT 1030 without cuDNN)."
fi

# ── Create virtual environment ────────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment '$VENV_DIR' already exists — skipping creation."
else
    log "Creating virtual environment in $VENV_DIR …"
    # Check that ensurepip is available (requires python3.X-venv on Debian/Ubuntu).
    # Note: `python -m venv --help` succeeds even without ensurepip, so we
    # must test the module directly.
    if ! $PYTHON -c "import ensurepip" &>/dev/null; then
        DEB_PKG="python${PY_VER}-venv"
        warn "ensurepip not available — python3-venv not installed."
        warn "Trying: sudo apt install -y $DEB_PKG"
        sudo apt install -y "$DEB_PKG" || err "Could not install $DEB_PKG — run: sudo apt install $DEB_PKG"
    fi
    $PYTHON -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
log "Virtual environment activated."
pip install --upgrade pip --quiet

# ── [1/5] OpenVINO ─────────────────────────────────────────────────────────
log "[1/5] Installing OpenVINO (~100 MB) …"
pip install "openvino>=2024.0" --quiet
ok "OpenVINO installed."
#check if python 3.12 or  3.13, then install the appropriate qi wheel
if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 12 ]; then 
    pip install https://github.com/Maelic/libqi-python/releases/download/qi-python-v3.1.5-cp312-cp313/qi-3.1.5-cp312-cp312-manylinux_2_28_x86_64.whl  --quiet
elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 13 ]; then
    pip install https://github.com/Maelic/libqi-python/releases/download/qi-python-v3.1.5-cp312-cp313/qi-3.1.5-cp313-cp313-manylinux_2_28_x86_64.whl  --quiet
fi

ok "Naoqi Python SDK installed."

# ── [2/5] Computer vision & speech ────────────────────────────────────────────
log "[2/5] Installing vision and speech libraries …"
pip install \
    "opencv-python-headless>=4.9.0,<5.0" \
    "numpy>=1.26,<3.0" \
    "vosk>=0.3.45" \
    --quiet
ok "Vision and speech libraries installed."

# ── [3/5] Web server for dashboard ────────────────────────────────────────────
log "[3/5] Installing dashboard dependencies …"
pip install \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "psutil>=5.9" \
    "paramiko>=3.0" \
    --quiet
ok "Dashboard dependencies installed."

# ── [4/5] Install the HRI_lab_Pepper package itself ──────────────────────
log "[4/5] Installing HRI_lab_Pepper package …"
pip install -e "$REPO_ROOT" --quiet 2>/dev/null || true
ok "Package installed."

# ── [5a/5] Export YOLOv8n → OpenVINO IR (one-time, ~12 MB output) ────────────
OV_MODEL_DIR="$REPO_ROOT/yolov8n_openvino_model"
OV_XML="$OV_MODEL_DIR/yolov8n.xml"
PT_MODEL="$REPO_ROOT/yolov8n.pt"

log "[5/5] Checking YOLOv8n OpenVINO model …"

if [ -f "$OV_XML" ]; then
    ok "yolov8n_openvino_model already exists — skipping export."
else
    # Search for a Python env that has ultralytics; conda envs are checked too
    EXPORTER=""
    for candidate in \
        "$REPO_ROOT/.venv/bin/python" \
        "$REPO_ROOT/../.venv/bin/python" \
        "$HOME/miniconda3/envs/pepper/bin/python" \
        "$HOME/anaconda3/envs/pepper/bin/python" \
        "$(command -v python3 2>/dev/null)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ] && \
           "$candidate" -c "import ultralytics" 2>/dev/null; then
            EXPORTER="$candidate"
            break
        fi
    done

    if [ -n "$EXPORTER" ] && [ -f "$PT_MODEL" ]; then
        log "Exporting $PT_MODEL → OpenVINO IR using $EXPORTER …"
        "$EXPORTER" - <<PYEOF
from ultralytics import YOLO
import os, shutil
model = YOLO("$PT_MODEL")
model.export(format="openvino", imgsz=640, dynamic=False)
src_dir = "$PT_MODEL".replace(".pt", "_openvino_model")
dst_dir = "$OV_MODEL_DIR"
if os.path.abspath(src_dir) != os.path.abspath(dst_dir) and os.path.isdir(src_dir):
    shutil.move(src_dir, dst_dir)
    print(f"Moved {src_dir} -> {dst_dir}")
print("Export complete:", os.listdir(dst_dir))
PYEOF
        ok "yolov8n_openvino_model exported."
    elif ! [ -f "$PT_MODEL" ]; then
        warn "yolov8n.pt not found — cannot export automatically."
        warn "Place yolov8n.pt in $REPO_ROOT and re-run, OR export manually:"
        warn "  python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='openvino')\""
        warn "Then move the output folder to: $OV_MODEL_DIR"
    else
        warn "ultralytics not found in any Python environment."
        warn "Export manually: python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='openvino')\""
        warn "Then move the output folder to: $OV_MODEL_DIR"
    fi
fi

# ── [5b/5] Download Vosk speech model ─────────────────────────────────────────
VOSK_NAME="vosk-model-small-en-us-0.15"
VOSK_DIR="$REPO_ROOT/dialog_pepper/$VOSK_NAME"
VOSK_URL="https://alphacephei.com/vosk/models/${VOSK_NAME}.zip"
VOSK_ZIP="$REPO_ROOT/dialog_pepper/${VOSK_NAME}.zip"

if [ -d "$VOSK_DIR" ]; then
    ok "Vosk model already present."
else
    log "Downloading Vosk speech model (~50 MB) …"
    if command -v curl &>/dev/null; then
        curl -L --progress-bar "$VOSK_URL" -o "$VOSK_ZIP"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress "$VOSK_URL" -O "$VOSK_ZIP"
    else
        err "Neither curl nor wget found. Download $VOSK_URL manually."
    fi
    log "Extracting Vosk model …"
    python3 -c "
import zipfile, os
with zipfile.ZipFile('$VOSK_ZIP', 'r') as zf:
    zf.extractall('$REPO_ROOT/dialog_pepper')
os.remove('$VOSK_ZIP')
"
    ok "Vosk model ready."
fi

# ── Sanity check ──────────────────────────────────────────────────────────────
log "Running sanity checks …"
python - <<'PYEOF'
import sys
from importlib.metadata import version, PackageNotFoundError

def get_ver(pkg):
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None

checks = [
    ("openvino",           "openvino"),
    ("cv2 (opencv)",       "opencv-python-headless"),
    ("vosk",               "vosk"),
    ("fastapi",            "fastapi"),
    ("uvicorn",            "uvicorn"),
    ("psutil",             "psutil"),
    ("numpy",              "numpy"),
]

all_ok = True
for label, pkg in checks:
    ver = get_ver(pkg)
    if ver is None:
        try:
            m = __import__(pkg.split("-")[0])
            ver = getattr(m, "__version__", "installed")
        except ImportError:
            ver = None
    if ver:
        print(f"  \033[32m✓\033[0m  {label:<28} {ver}")
    else:
        print(f"  \033[31m✗\033[0m  {label:<28} MISSING", file=sys.stderr)
        all_ok = False

try:
    import openvino as ov
    core = ov.Core()
    devs = core.available_devices
    tag  = ", ".join(devs) if devs else "CPU"
    print(f"  \033[32m✓\033[0m  {'OpenVINO devices':<28} {tag}")
except Exception as e:
    print(f"  \033[31m✗\033[0m  OpenVINO devices        ERROR: {e}", file=sys.stderr)
    all_ok = False

if not all_ok:
    sys.exit(1)
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  Installation complete!${RESET}"
echo -e "${GREEN}════════════════════════════════════════════════════${RESET}"
echo ""
echo "  Activate the environment:"
echo "      source $VENV_DIR/bin/activate"
echo ""
echo "  Start the dashboard (replace ROBOT_IP):"
echo "      python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559"
echo ""
