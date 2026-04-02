#!/usr/bin/env bash
# =============================================================================
#  HRI_lab_Pepper — GPU Install Script  (RTX / Ampere+ with cuDNN)
#
#  Installs onnxruntime-gpu.  Requires:
#    • NVIDIA driver   ≥ 525
#    • CUDA 12.*       (toolkit or runtime libraries)
#    • cuDNN 9.*       (auto-installed via apt if missing)
#
#  For GT 1030 / machines without cuDNN, use install.sh (CPU-only).
#
#  Approximate download sizes
#  --------------------------
#    onnxruntime-gpu            ~180 MB
#    cuDNN 9 (if missing)       ~500 MB
#    opencv-python-headless      ~25 MB
#    vosk + model                ~5 MB + 50 MB
#    fastapi + uvicorn            ~5 MB
#    numpy, psutil               ~25 MB
#    yolov8n.onnx (export)       ~12 MB  (one-time, uses existing project venv)
#  --------------------------
#  Total (cuDNN already installed):   ~300 MB
#  Total (first run, cuDNN missing):  ~800 MB
#
#  Can be run from any directory:
#      bash HRI_lab_Pepper/install_gpu.sh
#      # or:
#      cd HRI_lab_Pepper && bash install_gpu.sh
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

# ── Require NVIDIA GPU ────────────────────────────────────────────────────────
if ! command -v nvidia-smi &>/dev/null; then
    err "No NVIDIA GPU detected (nvidia-smi not found).  Use install.sh for CPU-only."
fi
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
ok "GPU: $GPU_NAME  (driver $DRIVER_VER)"

# ── cuDNN 9 check (required by onnxruntime-gpu 1.18+) ────────────────────────
log "Checking cuDNN 9 …"

cudnn_found() {
    ldconfig -p 2>/dev/null | grep -q "libcudnn.so.9" && return 0
    local f
    for f in /usr/lib/x86_64-linux-gnu/libcudnn.so.9 \
              /usr/local/cuda/lib64/libcudnn.so.9; do
        [ -f "$f" ] && return 0
    done
    return 1
}

if cudnn_found; then
    ok "cuDNN 9 already installed."
else
    log "cuDNN 9 not found — trying: sudo apt install -y libcudnn9-cuda-12 …"
    sudo apt update -qq 2>/dev/null || true
    if sudo apt install -y --no-install-recommends libcudnn9-cuda-12 2>/dev/null; then
        ok "cuDNN 9 installed."
    else
        # NVIDIA apt repo not configured — show step-by-step instructions
        OS_VER=$(. /etc/os-release 2>/dev/null && echo "${VERSION_ID:-22.04}" || echo "22.04")
        REPO_TAG="ubuntu${OS_VER//./}/x86_64"
        warn "──────────────────────────────────────────────────────────────────────"
        warn "Automatic cuDNN install failed. Add the NVIDIA apt repo then retry:"
        warn ""
        warn "  wget https://developer.download.nvidia.com/compute/cuda/repos/${REPO_TAG}/cuda-keyring_1.1-1_all.deb"
        warn "  sudo dpkg -i cuda-keyring_1.1-1_all.deb"
        warn "  sudo apt update"
        warn "  sudo apt install -y libcudnn9-cuda-12"
        warn ""
        warn "  Then re-run:  bash HRI_lab_Pepper/install_gpu.sh"
        warn "──────────────────────────────────────────────────────────────────────"
        err "cuDNN 9 required for onnxruntime-gpu.  See instructions above."
    fi
fi

# ── Create virtual environment ────────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment '$VENV_DIR' already exists — skipping creation."
else
    log "Creating virtual environment in $VENV_DIR …"
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

# ── [1/5] ONNX Runtime GPU ────────────────────────────────────────────────────
log "[1/5] Installing onnxruntime-gpu (~180 MB) …"
pip install "onnxruntime-gpu" --quiet
ok "onnxruntime-gpu installed."

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
    --quiet
ok "Dashboard dependencies installed."

# ── [4/5] Install the HRI_lab_Pepper package itself ──────────────────────
log "[4/5] Installing HRI_lab_Pepper package …"
pip install -e "$REPO_ROOT" --quiet 2>/dev/null || true
ok "Package installed."

# ── [5a/5] Export YOLOv8n → ONNX (one-time, ~12 MB output) ───────────────────
ONNX_MODEL="$REPO_ROOT/yolov8n.onnx"
PT_MODEL="$REPO_ROOT/yolov8n.pt"

log "[5/5] Checking YOLOv8n ONNX model …"

if [ -f "$ONNX_MODEL" ]; then
    ok "yolov8n.onnx already exists — skipping export."
else
    EXPORTER=""
    for candidate in \
        "$REPO_ROOT/.venv/bin/python" \
        "$REPO_ROOT/../.venv/bin/python" \
        "$(command -v python3 2>/dev/null)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ] && \
           "$candidate" -c "import ultralytics" 2>/dev/null; then
            EXPORTER="$candidate"
            break
        fi
    done

    if [ -n "$EXPORTER" ] && [ -f "$PT_MODEL" ]; then
        log "Exporting $PT_MODEL → yolov8n.onnx using $EXPORTER …"
        "$EXPORTER" - <<PYEOF
from ultralytics import YOLO
import os, shutil
model = YOLO("$PT_MODEL")
model.export(format="onnx", imgsz=640, dynamic=False, simplify=True)
src = "$PT_MODEL".replace(".pt", ".onnx")
dst = "$ONNX_MODEL"
if src != dst and os.path.exists(src):
    shutil.move(src, dst)
    print(f"Moved {src} -> {dst}")
print("Export complete.")
PYEOF
        ok "yolov8n.onnx exported."
    elif ! [ -f "$PT_MODEL" ]; then
        warn "yolov8n.pt not found — cannot export automatically."
        warn "Place yolov8n.pt in $REPO_ROOT and re-run, OR"
        warn "download yolov8n.onnx from https://github.com/ultralytics/assets/releases"
        warn "and save it to: $ONNX_MODEL"
    else
        warn "ultralytics not found in any Python environment."
        warn "Export manually: python -c \"from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx')\""
        warn "Then copy yolov8n.onnx to: $ONNX_MODEL"
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

# onnxruntime-gpu metadata name varies by version; check both
ort_ver = get_ver("onnxruntime-gpu") or get_ver("onnxruntime")
if ort_ver is None:
    try:
        import onnxruntime as _ort
        ort_ver = getattr(_ort, "__version__", "installed")
    except ImportError:
        pass

all_ok = True

if ort_ver:
    print(f"  \033[32m✓\033[0m  {'onnxruntime-gpu':<28} {ort_ver}")
else:
    print(f"  \033[31m✗\033[0m  {'onnxruntime-gpu':<28} MISSING", file=sys.stderr)
    all_ok = False

checks = [
    ("cv2 (opencv)",       "opencv-python-headless"),
    ("vosk",               "vosk"),
    ("fastapi",            "fastapi"),
    ("uvicorn",            "uvicorn"),
    ("psutil",             "psutil"),
    ("numpy",              "numpy"),
]

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
    import onnxruntime as ort
    providers = ort.get_available_providers()
    cuda = "CUDAExecutionProvider" in providers
    if cuda:
        tag = "\033[32mCUDA + CPU\033[0m"
    else:
        tag = "\033[31mCPU only\033[0m  ← cuDNN not visible at runtime"
    print(f"  \033[32m✓\033[0m  {'ORT providers':<28} {tag}")
    if not cuda:
        print("  [warn] CUDAExecutionProvider inactive — verify cuDNN 9 is on LD_LIBRARY_PATH.", file=sys.stderr)
except Exception:
    pass

if not all_ok:
    sys.exit(1)
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}  GPU Installation complete!${RESET}"
echo -e "${GREEN}════════════════════════════════════════════════════${RESET}"
echo ""
echo "  Activate the environment:"
echo "      source $VENV_DIR/bin/activate"
echo ""
echo "  Start the dashboard (replace ROBOT_IP):"
echo "      python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559"
echo ""
