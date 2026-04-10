#!/usr/bin/env bash
# =============================================================================
#  HRI_lab_Pepper — Install Script  (CPU / OpenVINO)
#
#  Run from inside the cloned repo:
#      cd HRI_lab_Pepper
#      bash install.sh
#
#  What this script does:
#    1. Creates .venv/ in the repo root
#    2. Installs all Python dependencies
#    3. Downloads the OpenVINO model from Google Drive (~45 MB)
#    4. Downloads the Vosk speech model (~50 MB)
#
#  Approximate download sizes
#  --------------------------
#    openvino                   ~100 MB
#    qi (Naoqi SDK)              ~20 MB
#    opencv-python-headless      ~25 MB
#    vosk + model                ~5 MB + 50 MB
#    fastapi + uvicorn            ~5 MB
#    numpy, psutil               ~25 MB
#    yolov8s_openvino_model      ~45 MB  (Google Drive)
#  --------------------------
#  Total:   ~275 MB
#
#  For RTX / Ampere GPU machines use install_gpu.sh instead.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

VENV_DIR="$REPO_ROOT/.venv"
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

# ── [1/5] OpenVINO + Naoqi SDK ───────────────────────────────────────────────
log "[1/5] Installing OpenVINO (~100 MB) …"
pip install "openvino>=2024.0" --quiet
ok "OpenVINO installed."

log "       Installing Naoqi (qi) SDK …"
if   [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 12 ]; then
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
    --quiet
ok "Dashboard dependencies installed."

# ── [4/5] Install the package itself ─────────────────────────────────────────
log "[4/5] Installing HRI_lab_Pepper package …"
pip install -e "$REPO_ROOT" --quiet
ok "Package installed."

# ── [4b] Build tablet pages for Pepper's embedded browser ────────────────────
TABLET_DIR="$REPO_ROOT/dashboard/static/tablet"
log "[4b] Compiling tablet pages for Pepper's old Chromium browser …"

if ! command -v node &>/dev/null; then
    warn "Node.js not found — attempting automatic install via NodeSource …"
    if command -v apt &>/dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - \
            && sudo apt install -y nodejs
    else
        err "Node.js is required for the tablet build step. Install it from https://nodejs.org and re-run."
    fi
fi

pushd "$TABLET_DIR" >/dev/null
npm install --silent
node build.js
popd >/dev/null
ok "Tablet pages compiled to $TABLET_DIR/dist/"

# ── [5a/5] Download OpenVINO model from Google Drive (~45 MB) ─────────────────
OV_MODEL_DIR="$REPO_ROOT/yolov8s_openvino_model"
GDRIVE_FOLDER_ID="1aIGlLoDuyGId6dDP9E5JICDADGyDX-4G"

log "[5/5] Checking OpenVINO model …"
if [ -f "$OV_MODEL_DIR/yolov8s.xml" ]; then
    ok "yolov8s_openvino_model already present — skipping download."
else
    log "       Downloading yolov8s_openvino_model from Google Drive …"
    pip install "gdown>=4.7" --quiet
    OV_TMP="$REPO_ROOT/_ov_tmp"
    rm -rf "$OV_TMP"
    python - <<PYEOF
import gdown, os, shutil, sys
try:
    gdown.download_folder(
        id="$GDRIVE_FOLDER_ID",
        output="$OV_TMP",
        quiet=False,
        use_cookies=False,
    )
except Exception as e:
    print(f"gdown error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
    # gdown may place files directly in OV_TMP or inside a subdirectory
    if [ -f "$OV_TMP/yolov8s.xml" ]; then
        mv "$OV_TMP" "$OV_MODEL_DIR"
    else
        # find the subdirectory that contains the .xml
        XML_PATH=$(find "$OV_TMP" -name "*.xml" 2>/dev/null | head -1)
        if [ -n "$XML_PATH" ]; then
            mv "$(dirname "$XML_PATH")" "$OV_MODEL_DIR"
            rm -rf "$OV_TMP"
        else
            rm -rf "$OV_TMP"
            err "OpenVINO model download failed — no .xml found. Check the Google Drive link."
        fi
    fi
    ok "yolov8s_openvino_model downloaded."
fi

# ── [5b/5] Download Vosk speech model ─────────────────────────────────────────
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

checks = [
    ("openvino",               "openvino"),
    ("cv2 (opencv)",           "opencv-python-headless"),
    ("vosk",                   "vosk"),
    ("fastapi",                "fastapi"),
    ("uvicorn",                "uvicorn"),
    ("psutil",                 "psutil"),
    ("numpy",                  "numpy"),
]
all_ok = True
for label, pkg in checks:
    ver = get_ver(pkg)
    if ver:
        print(f"  \033[32m✓\033[0m  {label:<30} {ver}")
    else:
        print(f"  \033[31m✗\033[0m  {label:<30} MISSING", file=sys.stderr)
        all_ok = False

try:
    import openvino as ov
    devs = ", ".join(ov.Core().available_devices) or "CPU"
    print(f"  \033[32m✓\033[0m  {'OpenVINO devices':<30} {devs}")
except Exception as e:
    print(f"  \033[31m✗\033[0m  OpenVINO devices              ERROR: {e}", file=sys.stderr)
    all_ok = False

if not all_ok:
    sys.exit(1)
PYEOF

# ── Done ─────────────────────────────────────────────────────────────────────
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
