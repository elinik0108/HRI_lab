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

MODELS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".", "models")
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL  = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"

# ── DL Models ─────────────────────────────────────────────────────────────────
# YOLOv8s exported to OpenVINO IR format (CPU/Intel-GPU path)
# The model directory contains yolov8s.xml + yolov8s.bin
_REPO_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLO_DETECT_MODEL = os.path.join(_REPO_ROOT, "HRI_lab_Pepper/yolov8s_openvino_model", "yolov8s.xml")
# Original PyTorch weights used by the ultralytics/CUDA path
YOLO_PT_MODEL     = os.path.join(_REPO_ROOT, "HRI_lab_Pepper/models", "yolov8s.pt")
# ONNX model used by the onnxruntime-gpu path (GPU install)
YOLO_ONNX_MODEL   = os.path.join(_REPO_ROOT, "HRI_lab_Pepper/models", "yolov8s.onnx")

# Inference device — auto-detected at import time.
# Override with PEPPER_API_DEVICE env var: CPU / GPU / CUDA / AUTO
from HRI_lab_Pepper.utils.device import select_device as _select_device  # noqa: E402
INFERENCE_DEVICE = _select_device()

# ── Terminal colours ──────────────────────────────────────────────────────────
W    = "\033[0m"
R    = "\033[31m"
G    = "\033[32m"
O    = "\033[33m"
B    = "\033[34m"
P    = "\033[35m"
CYAN = "\033[96m"
