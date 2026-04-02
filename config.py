#!/usr/bin/env python
# =============================================================================
#                         HRI_lab_Pepper — Global Configuration
# =============================================================================
import os

# ── Robot connection ──────────────────────────────────────────────────────────
CONNECTION_URL = "tcp://172.18.48.50:9559"

# ── Camera ────────────────────────────────────────────────────────────────────
# Naoqi camera constants
CAM_TOP         = 0         # Top camera
CAM_BOTTOM      = 1         # Bottom camera
CAM_STEREO      = 2         # Stereo camera
CAM_DEFAULT     = CAM_TOP

# Resolution: 0=QQVGA, 1=QVGA, 2=VGA, 3=4VGA
CAM_RESOLUTION  = 2         # VGA 640×480
CAM_COLORSPACE  = 13        # kBGRColorSpace (for direct OpenCV use)
CAM_FPS         = 15        # Safe rate for remote streaming

# ── Audio / STT ───────────────────────────────────────────────────────────────
STT_SAMPLE_RATE = 16000
STT_MIC_CHANNEL = 3         # 3 = front mic
STT_TIMEOUT_SEC = 15
STT_VAD_RMS_MIN = 100       # Minimum RMS to consider as speech

MODELS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dialog_pepper")
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL  = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"

# ── DL Models — OpenVINO (no PyTorch / cuDNN required) ───────────────────────
# YOLOv8n exported to OpenVINO IR format by the install script.
# The model directory contains yolov8n.xml + yolov8n.bin
_REPO_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLO_DETECT_MODEL = os.path.join(_REPO_ROOT, "yolov8n_openvino_model", "yolov8n.xml")

# OpenVINO device — override with PEPPER_API_DEVICE env var (CPU / GPU)
def _ov_device() -> str:
    override = os.environ.get("PEPPER_API_DEVICE", "").strip().upper()
    return override if override in ("CPU", "GPU", "AUTO") else "CPU"

INFERENCE_DEVICE = _ov_device()

# ── Terminal colours ──────────────────────────────────────────────────────────
W    = "\033[0m"
R    = "\033[31m"
G    = "\033[32m"
O    = "\033[33m"
B    = "\033[34m"
P    = "\033[35m"
CYAN = "\033[96m"
