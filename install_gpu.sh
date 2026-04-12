#!/usr/bin/env bash
# =============================================================================
#  HRI_lab_Pepper — GPU Install Script  (RTX / Ampere+ with cuDNN)
#
#  Run from inside the cloned repo:
#      cd HRI_lab_Pepper
#      bash install_gpu.sh
#
#  Requires:
#    • NVIDIA driver ≥ 525
#    • CUDA 12.*  (toolkit or runtime libraries)
#    • cuDNN 9.*  (auto-installed via apt if missing)
#
#  For CPU-only or machines without cuDNN, use install.sh instead.
#
#  Approximate download sizes
#  --------------------------
#    onnxruntime-gpu            ~180 MB
#    yolov8s.onnx (gdrive)        ~30 MB
#    qi (Naoqi SDK)              ~20 MB
#    opencv-python-headless      ~25 MB
#    vosk + model                ~5 MB + 50 MB
#    fastapi + uvicorn            ~5 MB
#    gdown                        ~1 MB
#    numpy, psutil               ~25 MB
#  --------------------------
#  Total (cuDNN present):   ~340 MB
#  Total (first run):       ~840 MB
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

VENV_DIR="$REPO_ROOT/.venv_gpu"
PYTHON=${PYTHON:-python3}

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN="\033[32m"; BLUE="\033[34m"; YELLOW="\033[33m"; RED="\033[31m"; RESET="\033[0m"
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
    err "Python 3.9+ required (found $PY_VER)."
fi
ok "Python $PY_VER"

# ── Require NVIDIA GPU ────────────────────────────────────────────────────────
if ! command -v nvidia-smi &>/dev/null; then
    err "No NVIDIA GPU detected (nvidia-smi not found). Use install.sh for CPU-only."
fi
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
ok "GPU: $GPU_NAME  (driver $DRIVER_VER)"

# ── cuDNN 9 check ─────────────────────────────────────────────────────────────
log "Checking cuDNN 9 …"
cudnn_found() {
    ldconfig -p 2>/dev/null | grep -q "libcudnn.so.9" && return 0
    for f in /usr/lib/x86_64-linux-gnu/libcudnn.so.9 /usr/local/cuda/lib64/libcudnn.so.9; do
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
        OS_VER=$(. /etc/os-release 2>/dev/null && echo "${VERSION_ID:-22.04}" || echo "22.04")
        REPO_TAG="ubuntu${OS_VER//./}/x86_64"
        warn "────────────────────────────────────────────────────────────────────"
        warn "Automatic cuDNN install failed. Add the NVIDIA apt repo then retry:"
        warn ""
        warn "  wget https://developer.download.nvidia.com/compute/cuda/repos/${REPO_TAG}/cuda-keyring_1.1-1_all.deb"
        warn "  sudo dpkg -i cuda-keyring_1.1-1_all.deb"
        warn "  sudo apt update && sudo apt install -y libcudnn9-cuda-12"
        warn "  Then re-run:  bash install_gpu.sh"
        warn "────────────────────────────────────────────────────────────────────"
        err "cuDNN 9 required for onnxruntime-gpu. See instructions above."
    fi
fi

# ── Create virtual environment ────────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists — skipping creation."
else
    log "Creating virtual environment in $VENV_DIR …"
    if ! $PYTHON -c "import ensurepip" &>/dev/null; then
        DEB_PKG="python${PY_VER}-venv"
        warn "ensurepip not available. Trying: sudo apt install -y $DEB_PKG"
        sudo apt install -y "$DEB_PKG" || err "Could not install $DEB_PKG — run: sudo apt install $DEB_PKG"
    fi
    $PYTHON -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
log "Virtual environment activated."
pip install --upgrade pip --quiet

# ── [1/5] onnxruntime-gpu + Naoqi SDK ────────────────────────────────────────
log "[1/5] Installing onnxruntime-gpu (~180 MB) …"
pip install "onnxruntime-gpu" --quiet
ok "onnxruntime-gpu installed."

log "       Installing Naoqi (qi) SDK …"
elif   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 8 ]; then
    pip install https://github.com/aldebaran/libqi-python/releases/download/qi-python-v3.1.5/qi-3.1.5-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl --quiet
elif   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 9 ]; then
    pip install https://github.com/aldebaran/libqi-python/releases/download/qi-python-v3.1.5/qi-3.1.5-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl --quiet
elif   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 10 ]; then
    pip install https://github.com/aldebaran/libqi-python/releases/download/qi-python-v3.1.5/qi-3.1.5-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl --quiet
elif   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 11 ]; then
    pip install https://github.com/aldebaran/libqi-python/releases/download/qi-python-v3.1.5/qi-3.1.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl --quiet
elif   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 12 ]; then
    pip install https://github.com/Maelic/libqi-python/releases/download/qi-python-v3.1.5-cp312-cp313/qi-3.1.5-cp312-cp312-manylinux_2_28_x86_64.whl --quiet
elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 13 ]; then
    pip install https://github.com/Maelic/libqi-python/releases/download/qi-python-v3.1.5-cp312-cp313/qi-3.1.5-cp313-cp313-manylinux_2_28_x86_64.whl --quiet
else
    warn "No pre-built qi wheel for Python $PY_VER — you may need to build it manually."
fi
ok "Naoqi SDK installed."

# ── [2/5] Computer vision & speech ────────────────────────────────────────────
log "[2/5] Installing vision and speech libraries …"
pip install \
    "opencv-python-headless>=4.9.0,<5.0" \
    "numpy>=1.26,<3.0" \
    "vosk>=0.3.45" \
    --quiet
ok "Vision and speech libraries installed."

# ── [3/5] Dashboard dependencies ─────────────────────────────────────────────
log "[3/5] Installing dashboard dependencies …"
pip install \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "psutil>=5.9" \
    "paramiko>=3.0" \
    "gdown>=5.1" \
    --quiet
ok "Dashboard dependencies installed."

# ── [4/5] Install the package itself ─────────────────────────────────────────
log "[4/5] Installing HRI_lab_Pepper package …"
pip install -e "$REPO_ROOT" --quiet
ok "Package installed."

# ── [5/5] Download YOLOv8s ONNX model ───────────────────────────────────────
ONNX_MODEL="$REPO_ROOT/models/yolov8s.onnx"
ONNX_GDRIVE_ID="1ni4JDZ3LY2aDW23snswUfJBKx8RedEKn"

log "[5/5] Checking yolov8s ONNX model …"
if [ -f "$ONNX_MODEL" ]; then
    ok "yolov8s.onnx already exists — skipping download."
else
    mkdir -p "$REPO_ROOT/models"
    log "Downloading yolov8s.onnx from Google Drive …"
    python - <<PYEOF
import sys
try:
    import gdown
except ImportError:
    print("gdown not found", file=sys.stderr)
    sys.exit(1)
gdown.download(id="$ONNX_GDRIVE_ID", output="$ONNX_MODEL", quiet=False)
PYEOF
    ok "yolov8s.onnx downloaded."
fi

# ── Download Vosk speech model ────────────────────────────────────────────────
VOSK_NAME="vosk-model-small-en-us-0.15"
VOSK_DIR="$REPO_ROOT/models/$VOSK_NAME"
VOSK_URL="https://alphacephei.com/vosk/models/${VOSK_NAME}.zip"
VOSK_ZIP="$REPO_ROOT/models/${VOSK_NAME}.zip"

if [ -d "$VOSK_DIR" ]; then
    ok "Vosk model already present."
else
    log "Downloading Vosk speech model (~50 MB) …"
    mkdir -p "$REPO_ROOT/models"
    if command -v curl &>/dev/null; then
        curl -L --progress-bar "$VOSK_URL" -o "$VOSK_ZIP"
    elif command -v wget &>/dev/null; then
        wget -q --show-progress "$VOSK_URL" -O "$VOSK_ZIP"
    else
        err "Neither curl nor wget found. Download $VOSK_URL manually to $VOSK_DIR"
    fi
    log "Extracting Vosk model …"
    python -c "
import zipfile, os
with zipfile.ZipFile('$VOSK_ZIP', 'r') as zf:
    zf.extractall('$REPO_ROOT/models')
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
    try: return version(pkg)
    except PackageNotFoundError: return None

ort_ver = get_ver("onnxruntime-gpu") or get_ver("onnxruntime")
if ort_ver is None:
    try:
        import onnxruntime as _ort
        ort_ver = getattr(_ort, "__version__", "installed")
    except ImportError:
        pass

all_ok = True
if ort_ver:
    print(f"  \033[32m✓\033[0m  {'onnxruntime-gpu':<30} {ort_ver}")
else:
    print(f"  \033[31m✗\033[0m  {'onnxruntime-gpu':<30} MISSING", file=sys.stderr)
    all_ok = False

for label, pkg in [
    ("cv2 (opencv)",           "opencv-python-headless"),
    ("vosk",                   "vosk"),
    ("fastapi",                "fastapi"),
    ("uvicorn",                "uvicorn"),
    ("psutil",                 "psutil"),
    ("numpy",                  "numpy"),
]:
    ver = get_ver(pkg)
    if ver:
        print(f"  \033[32m✓\033[0m  {label:<30} {ver}")
    else:
        print(f"  \033[31m✗\033[0m  {label:<30} MISSING", file=sys.stderr)
        all_ok = False

try:
    import onnxruntime as ort
    cuda = "CUDAExecutionProvider" in ort.get_available_providers()
    tag = "\033[32mCUDA + CPU\033[0m" if cuda else "\033[31mCPU only\033[0m  ← verify cuDNN 9 is visible"
    print(f"  \033[32m✓\033[0m  {'ORT providers':<30} {tag}")
except Exception:
    pass

if not all_ok:
    sys.exit(1)
PYEOF

# ── Done ─────────────────────────────────────────────────────────────────────
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
