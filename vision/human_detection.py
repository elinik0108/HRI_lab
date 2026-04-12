#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Human Detection Module
# =============================================================================
"""
Detects people in a camera frame using YOLOv8s.

Backend is selected automatically by ``config.INFERENCE_DEVICE``:

* ``"cuda"``  — NVIDIA GPU via ultralytics + PyTorch (fastest on CUDA machines).
* ``"GPU"``   — Intel iGPU/dGPU via the OpenVINO GPU plugin.
* ``"CPU"``   — OpenVINO CPU backend (always available, safe fallback).

Usage
-----
    from HRI_lab_Pepper.vision.human_detection import HumanDetector

    det = HumanDetector()

    # Detect people in a BGR frame (from PepperCamera)
    people = det.detect(frame)
    # [{"bbox": [x1, y1, x2, y2], "confidence": 0.92}, …]

    if people:
        print("Someone is in front of the robot!")
        x1, y1, x2, y2 = people[0]["bbox"]
"""

from typing import Any, Dict, List

import cv2
import numpy as np

from HRI_lab_Pepper.config import (
    B, W, R,
    YOLO_DETECT_MODEL,
    YOLO_PT_MODEL,
    YOLO_ONNX_MODEL,
    INFERENCE_DEVICE,
)

# YOLOv8 input size
_YOLO_SIZE = 640


class HumanDetector:
    """
    People detector — auto-selects the best available inference backend.

    Parameters
    ----------
    model_path : str, optional
        Path to the OpenVINO model XML file used by the CPU/GPU (OpenVINO)
        backend.  Defaults to ``config.YOLO_DETECT_MODEL``.
    pt_model_path : str, optional
        Path to the YOLOv8 ``.pt`` weights file used by the CUDA backend.
        Defaults to ``config.YOLO_PT_MODEL``.
    conf_threshold : float
        Minimum confidence to keep a detection (default 0.45).
    iou_threshold : float
        NMS IoU threshold (default 0.45).
    device : str, optional
        Target device: ``"cuda"``, ``"GPU"``, or ``"CPU"``.
        Defaults to ``config.INFERENCE_DEVICE`` (auto-detected at import time).
    """

    def __init__(
        self,
        model_path: str = YOLO_DETECT_MODEL,
        pt_model_path: str = YOLO_PT_MODEL,
        onnx_model_path: str = YOLO_ONNX_MODEL,
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        device: str = INFERENCE_DEVICE,
    ) -> None:
        self._conf = conf_threshold
        self._iou  = iou_threshold

        if device == "cuda":
            self._backend = self._try_init_cuda(pt_model_path)
        elif device == "ort_gpu":
            self._backend = self._try_init_ort(onnx_model_path)
        else:
            self._backend = None

        if self._backend is None:
            # Fall back to OpenVINO (GPU or CPU)
            ov_device = device if device in ("GPU", "AUTO") else "CPU"
            self._init_openvino(model_path, ov_device)

    # ------------------------------------------------------------------
    # Backend initialisation helpers
    # ------------------------------------------------------------------

    def _try_init_cuda(self, pt_model_path: str) -> str | None:
        """Try to load the ultralytics YOLO model on CUDA. Returns ``"cuda"`` on
        success, or ``None`` if the required libraries are not available."""
        try:
            from ultralytics import YOLO as _YOLO

            print(f"{B}[HumanDetector] Loading {pt_model_path} via ultralytics (CUDA) …{W}")
            self._yolo = _YOLO(pt_model_path)
            self._yolo.to("cuda")
            print(f"{B}[HumanDetector] Ready — ultralytics CUDA{W}")
            return "cuda"
        except ImportError:
            print(f"{R}[HumanDetector] ultralytics not installed — falling back to OpenVINO CPU.{W}")
            return None
        except Exception as exc:
            print(f"{R}[HumanDetector] CUDA init failed ({exc}) — falling back to OpenVINO CPU.{W}")
            return None

    def _try_init_ort(self, onnx_model_path: str) -> "str | None":
        """Try to load the ONNX model via onnxruntime-gpu. Returns ``"ort_gpu"`` on
        success, or ``None`` if not available."""
        try:
            import onnxruntime as ort

            print(f"{B}[HumanDetector] Loading {onnx_model_path} via onnxruntime-gpu …{W}")
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._ort_session    = ort.InferenceSession(onnx_model_path, providers=providers)
            self._ort_input_name = self._ort_session.get_inputs()[0].name
            print(f"{B}[HumanDetector] Ready — ONNX Runtime GPU{W}")
            return "ort_gpu"
        except ImportError:
            print(f"{R}[HumanDetector] onnxruntime not installed — falling back to OpenVINO CPU.{W}")
            return None
        except Exception as exc:
            print(f"{R}[HumanDetector] ORT GPU init failed ({exc}) — falling back to OpenVINO CPU.{W}")
            return None

    def _init_openvino(self, model_path: str, device: str) -> None:
        import openvino as ov

        print(f"{B}[HumanDetector] Loading {model_path} via OpenVINO …{W}")
        try:
            core     = ov.Core()
            ov_model = core.read_model(model_path)
            compiled = core.compile_model(ov_model, device)
            self._infer   = compiled.create_infer_request()
            self._inp_key = compiled.input(0)
            self._backend = f"openvino_{device.lower()}"
            print(f"{B}[HumanDetector] Ready — OpenVINO {device}{W}")
        except Exception as exc:
            if device != "CPU":
                print(f"{R}[HumanDetector] OpenVINO {device} failed ({exc}) — retrying with CPU.{W}")
                self._init_openvino(model_path, "CPU")
            else:
                raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _letterbox(self, bgr_frame: np.ndarray):
        """Letterbox-resize to _YOLO_SIZE × _YOLO_SIZE and return metadata."""
        h0, w0 = bgr_frame.shape[:2]
        r      = min(_YOLO_SIZE / h0, _YOLO_SIZE / w0)
        nh, nw = int(round(h0 * r)), int(round(w0 * r))
        resized = cv2.resize(bgr_frame, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((_YOLO_SIZE, _YOLO_SIZE, 3), 114, dtype=np.uint8)
        pad_top  = (_YOLO_SIZE - nh) // 2
        pad_left = (_YOLO_SIZE - nw) // 2
        canvas[pad_top:pad_top + nh, pad_left:pad_left + nw] = resized

        # BGR → RGB, HWC → NCHW, uint8 → float32 [0-1]
        inp = canvas[:, :, ::-1].astype(np.float32) / 255.0
        inp = inp.transpose(2, 0, 1)[np.newaxis]  # [1, 3, H, W]
        return inp, r, pad_top, pad_left, h0, w0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect people in *frame*.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 image (e.g. from ``PepperCamera.get_frame()``).

        Returns
        -------
        list of dict
            Each entry has:

            * ``"bbox"``       — ``[x1, y1, x2, y2]`` pixel coordinates (int)
            * ``"confidence"`` — detection confidence score (float 0–1)

        Example
        -------
        ::

            people = detector.detect(frame)
            if people:
                print(f"{len(people)} person(s) detected.")
                x1, y1, x2, y2 = people[0]["bbox"]
        """
        if frame is None:
            return []

        if self._backend == "cuda":
            return self._detect_ultralytics(frame)
        if self._backend == "ort_gpu":
            return self._detect_ort(frame)
        return self._detect_openvino(frame)

    # ------------------------------------------------------------------
    # Backend-specific inference
    # ------------------------------------------------------------------

    def _detect_ultralytics(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        results = self._yolo.predict(
            frame,
            verbose=False,
            conf=self._conf,
            iou=self._iou,
            classes=[0],  # person only
        )
        detections: List[Dict[str, Any]] = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append({
                    "bbox":       [x1, y1, x2, y2],
                    "confidence": float(box.conf[0]),
                })
        return detections

    def _detect_ort(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        inp, r, pad_top, pad_left, h0, w0 = self._letterbox(frame)

        raw   = self._ort_session.run(None, {self._ort_input_name: inp})[0]  # [1, 84, 8400]
        preds = raw[0].T  # [8400, 84]

        person_conf = preds[:, 4]
        mask = person_conf > self._conf
        if not mask.any():
            return []

        boxes_cxcywh = preds[mask, :4]
        confs        = person_conf[mask]

        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

        x1 = np.clip((x1 - pad_left) / r, 0, w0)
        y1 = np.clip((y1 - pad_top)  / r, 0, h0)
        x2 = np.clip((x2 - pad_left) / r, 0, w0)
        y2 = np.clip((y2 - pad_top)  / r, 0, h0)

        boxes_xywh = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        indices    = cv2.dnn.NMSBoxes(
            boxes_xywh, confs.tolist(), self._conf, self._iou
        )

        result: List[Dict[str, Any]] = []
        for i in (indices.flatten() if hasattr(indices, "flatten") else indices):
            result.append({
                "bbox":       [int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])],
                "confidence": float(confs[i]),
            })
        return result

    def _detect_openvino(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        inp, r, pad_top, pad_left, h0, w0 = self._letterbox(frame)

        # Run OpenVINO inference — output shape: [1, 84, 8400]
        # First 4 rows: cx, cy, w, h in 640×640 space
        # Rows 4+: per-class confidence scores (80 COCO classes)
        self._infer.infer({self._inp_key: inp})
        raw   = self._infer.get_output_tensor(0).data  # [1, 84, 8400]
        preds = raw[0].T  # [8400, 84]

        person_conf = preds[:, 4]  # class 0 = person

        mask = person_conf > self._conf
        if not mask.any():
            return []

        boxes_cxcywh = preds[mask, :4]
        confs        = person_conf[mask]

        # cx,cy,w,h → x1,y1,x2,y2 (still in 640×640 letterbox space)
        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

        # Remove letterbox padding and scale back to original resolution
        x1 = np.clip((x1 - pad_left) / r, 0, w0)
        y1 = np.clip((y1 - pad_top)  / r, 0, h0)
        x2 = np.clip((x2 - pad_left) / r, 0, w0)
        y2 = np.clip((y2 - pad_top)  / r, 0, h0)

        # Non-maximum suppression (cv2, no torch)
        boxes_xywh = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        indices    = cv2.dnn.NMSBoxes(
            boxes_xywh, confs.tolist(), self._conf, self._iou
        )

        result: List[Dict[str, Any]] = []
        for i in (indices.flatten() if hasattr(indices, "flatten") else indices):
            result.append({
                "bbox":       [int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])],
                "confidence": float(confs[i]),
            })
        return result


    def is_someone_present(self, frame: np.ndarray) -> bool:
        """
        Return ``True`` if at least one person is detected in *frame*.

        This is a convenience wrapper around :meth:`detect` for the common
        "wait until a user appears" pattern used in all assignments.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 image.
        """
        return len(self.detect(frame)) > 0
