#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Object Detection Module
# =============================================================================
"""
Detects any of the 80 COCO objects in a camera frame using YOLOv8s.

Backend is selected automatically by ``config.INFERENCE_DEVICE``:

* ``"cuda"``  — NVIDIA GPU via ultralytics + PyTorch (fastest on CUDA machines).
* ``"GPU"``   — Intel iGPU/dGPU via the OpenVINO GPU plugin.
* ``"CPU"``   — OpenVINO CPU backend (always available, safe fallback).

Usage
-----
    from HRI_lab_Pepper.vision.object_detection import ObjectDetector

    det = ObjectDetector()

    objects = det.detect(frame)
    # [{"bbox": [x1,y1,x2,y2], "confidence": 0.87, "label": "cup", "class_id": 41}, …]

    # Filter to a specific class
    cups = det.detect_class(frame, "cup")
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from HRI_lab_Pepper.config import B, W, R, YOLO_DETECT_MODEL, YOLO_PT_MODEL, INFERENCE_DEVICE

# YOLOv8 input size (must match the exported model)
_YOLO_SIZE = 640

# COCO 80-class label list (indices 0-79)
COCO_LABELS: List[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

# Distinct BGR colours per class for bounding-box drawing
def _class_colour(class_id: int):
    np.random.seed(class_id + 42)
    return tuple(int(c) for c in np.random.randint(80, 230, 3).tolist())


class ObjectDetector:
    """
    Multi-class object detector — auto-selects the best available inference backend.

    Parameters
    ----------
    model_path : str, optional
        Path to the OpenVINO model XML file used by the CPU/GPU (OpenVINO) backend.
        Defaults to ``config.YOLO_DETECT_MODEL``.
    pt_model_path : str, optional
        Path to the YOLOv8 ``.pt`` weights file used by the CUDA backend.
        Defaults to ``config.YOLO_PT_MODEL``.
    conf_threshold : float
        Minimum confidence to keep a detection (default 0.40).
    iou_threshold : float
        NMS IoU threshold (default 0.45).
    device : str, optional
        Target device: ``"cuda"``, ``"GPU"``, or ``"CPU"``.
        Defaults to ``config.INFERENCE_DEVICE`` (auto-detected at import time).
    classes : list of str, optional
        If provided, only return detections whose label appears in this list.
        E.g. ``classes=["cup", "bottle"]``.
    """

    def __init__(
        self,
        model_path: str = YOLO_DETECT_MODEL,
        pt_model_path: str = YOLO_PT_MODEL,
        conf_threshold: float = 0.40,
        iou_threshold: float = 0.45,
        device: str = INFERENCE_DEVICE,
        classes: Optional[List[str]] = None,
    ) -> None:
        self._conf   = conf_threshold
        self._iou    = iou_threshold
        self._filter = set(classes) if classes else None

        if device == "cuda":
            self._backend = self._try_init_cuda(pt_model_path)
        else:
            self._backend = None

        if self._backend is None:
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

            print(f"{B}[ObjectDetector] Loading {pt_model_path} via ultralytics (CUDA) …{W}")
            self._yolo = _YOLO(pt_model_path)
            self._yolo.to("cuda")
            print(f"{B}[ObjectDetector] Ready — ultralytics CUDA{W}")
            return "cuda"
        except ImportError:
            print(f"{R}[ObjectDetector] ultralytics not installed — falling back to OpenVINO CPU.{W}")
            return None
        except Exception as exc:
            print(f"{R}[ObjectDetector] CUDA init failed ({exc}) — falling back to OpenVINO CPU.{W}")
            return None

    def _init_openvino(self, model_path: str, device: str) -> None:
        import openvino as ov

        print(f"{B}[ObjectDetector] Loading {model_path} via OpenVINO …{W}")
        try:
            core     = ov.Core()
            ov_model = core.read_model(model_path)
            compiled = core.compile_model(ov_model, device)
            self._infer   = compiled.create_infer_request()
            self._inp_key = compiled.input(0)
            self._backend = f"openvino_{device.lower()}"
            print(f"{B}[ObjectDetector] Ready — OpenVINO {device}{W}")
        except Exception as exc:
            if device != "CPU":
                print(f"{R}[ObjectDetector] OpenVINO {device} failed ({exc}) — retrying with CPU.{W}")
                self._init_openvino(model_path, "CPU")
            else:
                raise

    # ------------------------------------------------------------------
    # Letterbox preprocessing (identical to HumanDetector)
    # ------------------------------------------------------------------

    def _letterbox(self, bgr_frame: np.ndarray):
        h0, w0 = bgr_frame.shape[:2]
        r      = min(_YOLO_SIZE / h0, _YOLO_SIZE / w0)
        nh, nw = int(round(h0 * r)), int(round(w0 * r))
        resized = cv2.resize(bgr_frame, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((_YOLO_SIZE, _YOLO_SIZE, 3), 114, dtype=np.uint8)
        pad_top  = (_YOLO_SIZE - nh) // 2
        pad_left = (_YOLO_SIZE - nw) // 2
        canvas[pad_top:pad_top + nh, pad_left:pad_left + nw] = resized

        inp = canvas[:, :, ::-1].astype(np.float32) / 255.0
        inp = inp.transpose(2, 0, 1)[np.newaxis]  # [1, 3, H, W]
        return inp, r, pad_top, pad_left, h0, w0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect objects in *frame*.

        Parameters
        ----------
        frame : np.ndarray
            BGR uint8 image (e.g. from ``PepperCamera.get_frame()``).

        Returns
        -------
        list of dict
            Each entry has:

            * ``"bbox"``       — ``[x1, y1, x2, y2]`` pixel coordinates (int)
            * ``"confidence"`` — score (float 0–1)
            * ``"label"``      — COCO class name (str)
            * ``"class_id"``   — COCO class index (int 0–79)

        Examples
        --------
        ::

            objects = detector.detect(frame)
            for obj in objects:
                print(obj["label"], obj["confidence"])
        """
        if frame is None:
            return []

        if self._backend == "cuda":
            return self._detect_ultralytics(frame)
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
        )
        detections: List[Dict[str, Any]] = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label  = COCO_LABELS[cls_id] if cls_id < len(COCO_LABELS) else str(cls_id)
                if self._filter and label not in self._filter:
                    continue
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append({
                    "bbox":       [x1, y1, x2, y2],
                    "confidence": float(box.conf[0]),
                    "label":      label,
                    "class_id":   cls_id,
                })
        return detections

    def _detect_openvino(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        inp, r, pad_top, pad_left, h0, w0 = self._letterbox(frame)

        # Inference — output: [1, 84, 8400]
        # Rows 0-3: cx, cy, w, h  |  Rows 4-83: per-class scores (80 classes)
        self._infer.infer({self._inp_key: inp})
        raw   = self._infer.get_output_tensor(0).data  # [1, 84, 8400]
        preds = raw[0].T  # [8400, 84]

        # Best class score + id for each anchor
        class_scores = preds[:, 4:]                     # [8400, 80]
        class_ids    = np.argmax(class_scores, axis=1)  # [8400]
        best_scores  = class_scores[np.arange(len(class_ids)), class_ids]

        mask = best_scores > self._conf
        if not mask.any():
            return []

        boxes_cxcywh = preds[mask, :4]
        confs        = best_scores[mask]
        ids          = class_ids[mask]
        labels       = [COCO_LABELS[i] for i in ids]

        # Filter by class name if requested
        if self._filter:
            keep = [i for i, lbl in enumerate(labels) if lbl in self._filter]
            if not keep:
                return []
            boxes_cxcywh = boxes_cxcywh[keep]
            confs        = confs[keep]
            ids          = ids[keep]
            labels       = [labels[i] for i in keep]

        # cx,cy,w,h → x1,y1,x2,y2 in letterbox space
        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

        # Remove letterbox padding and scale back to original resolution
        x1 = np.clip((x1 - pad_left) / r, 0, w0)
        y1 = np.clip((y1 - pad_top)  / r, 0, h0)
        x2 = np.clip((x2 - pad_left) / r, 0, w0)
        y2 = np.clip((y2 - pad_top)  / r, 0, h0)

        # NMS per-class (run once over all classes together using class-aware offsets)
        offset       = ids.astype(np.float32) * (_YOLO_SIZE + 1)
        boxes_xywh   = np.stack(
            [x1 + offset, y1 + offset, x2 - x1, y2 - y1], axis=1
        ).tolist()
        nms_indices  = cv2.dnn.NMSBoxes(
            boxes_xywh, confs.tolist(), self._conf, self._iou
        )

        result: List[Dict[str, Any]] = []
        for i in (nms_indices.flatten() if hasattr(nms_indices, "flatten") else nms_indices):
            result.append({
                "bbox":       [int(x1[i]), int(y1[i]), int(x2[i]), int(y2[i])],
                "confidence": float(confs[i]),
                "label":      labels[i],
                "class_id":   int(ids[i]),
            })
        return result


    def detect_class(self, frame: np.ndarray, label: str) -> List[Dict[str, Any]]:
        """
        Convenience wrapper — detect only objects of class *label*.

        Parameters
        ----------
        label : str
            COCO class name (e.g. ``"cup"``, ``"chair"``).
        """
        old_filter   = self._filter
        self._filter = {label}
        try:
            return self.detect(frame)
        finally:
            self._filter = old_filter

    def get_labels(self) -> List[str]:
        """Return all 80 COCO class labels."""
        return list(COCO_LABELS)
