#!/usr/bin/env python
# =============================================================================
#                  HRI_lab_Pepper — Inference Device Selection
# =============================================================================
"""
Auto-detects the best available inference backend and returns a device string
understood by both the OpenVINO and ultralytics paths used in this package.

Returned values
---------------
``"cuda"``
    NVIDIA GPU via PyTorch/ultralytics.  Requires ``torch`` (with CUDA build)
    **and** ``ultralytics`` to be installed.

``"GPU"``
    Intel integrated or discrete GPU via the OpenVINO GPU plugin.

``"CPU"``
    OpenVINO CPU backend (always available, the safe fallback).

Priority
--------
1. ``PEPPER_API_DEVICE`` environment variable (``CUDA`` / ``GPU`` / ``CPU`` / ``AUTO``).
2. CUDA — if ``torch.cuda.is_available()`` and ``ultralytics`` is importable.
3. OpenVINO GPU plugin — if ``"GPU"`` appears in ``ov.Core().available_devices``.
4. CPU fallback.
"""

import os


def select_device() -> str:
    """Return the best available inference device string."""

    # ── 1. Explicit override ──────────────────────────────────────────────────
    override = os.environ.get("PEPPER_API_DEVICE", "").strip().upper()
    if override in ("CPU", "GPU", "AUTO", "CUDA"):
        return override

    # ── 2. NVIDIA CUDA (requires torch + ultralytics) ─────────────────────────
    try:
        import torch  # noqa: F401

        if torch.cuda.is_available():
            try:
                import ultralytics  # noqa: F401 – verify it is installed

                return "cuda"
            except ImportError:
                pass
    except ImportError:
        pass

    # ── 3. NVIDIA GPU via ONNX Runtime (onnxruntime-gpu, no torch needed) ──────
    try:
        import onnxruntime as _ort

        if "CUDAExecutionProvider" in _ort.get_available_providers():
            return "ort_gpu"
    except ImportError:
        pass

    # ── 4. Intel GPU via OpenVINO plugin ─────────────────────────────────────
    try:
        import openvino as ov

        if "GPU" in ov.Core().available_devices:
            return "GPU"
    except Exception:
        pass

    # ── 5. Safe CPU fallback ──────────────────────────────────────────────────
    return "CPU"
