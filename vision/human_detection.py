#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Human Detection Module
# =============================================================================
"""
Detects people in a camera frame using YOLOv8n via OpenVINO.

No PyTorch or cuDNN required.  OpenVINO is Intel's own inference engine and
gives ~2–3× faster throughput than plain ONNX Runtime on Intel CPUs (AVX2).

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
    B, W,
    YOLO_DETECT_MODEL,
)

# YOLOv8 input size
_YOLO_SIZE = 640


class HumanDetector:
    """
    People detector — YOLOv8n exported to OpenVINO IR, run via ``openvino``.

    Parameters
    ----------
    model_path : str, optional
        Path to the OpenVINO model XML file (``yolov8n_openvino_model/yolov8n.xml``).
        Defaults to the value in ``config.py``.
    conf_threshold : float
        Minimum confidence to keep a detection (default 0.45).
    iou_threshold : float
        NMS IoU threshold (default 0.45).
    device : str, optional
        OpenVINO device string — ``"CPU"`` (default) or ``"GPU"`` if an
        Intel iGPU is present.  Ignored on student GT 1030 machines.
    """

    def __init__(
        self,
        model_path: str = YOLO_DETECT_MODEL,
        conf_threshold: float = 0.45,
        iou_threshold: float = 0.45,
        device: str = "CPU",
    ) -> None:
        import openvino as ov

        self._conf = conf_threshold
        self._iou  = iou_threshold

        print(f"{B}[HumanDetector] Loading {model_path} via OpenVINO …{W}")
        core = ov.Core()
        model = core.read_model(model_path)
        # Set inference precision to FP32 for correctness on AVX2 (no tensor cores)
        compiled = core.compile_model(model, device)
        self._infer   = compiled.create_infer_request()
        self._inp_key = compiled.input(0)
        print(f"{B}[HumanDetector] Ready — OpenVINO {device}{W}")

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
