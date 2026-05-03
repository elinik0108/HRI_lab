
from typing import Optional, Tuple

#FOV
PEPPER_TOP_CAM_HFOV_DEG = 56


def find_marker_bearing(frame, detector, label: str) -> Optional[Tuple[float, float]]:
    if frame is None:
        return None

    detections = detector.detect_class(frame, label)
    print(f"[DEBUGG YOLO] requested='{label}' detections={[(d['label'], round(d['confidence'], 2)) for d in detector.detect(frame)]}")
    if not detections:
        return None

    best = max(detections, key=lambda d: d["confidence"])
    x1, y1, x2, y2 = best["bbox"]
    cx = (x1 + x2) / 2

    h, w = frame.shape[:2]
    offset_norm = (cx - w / 2) / (w / 2)
    bearing_deg = -offset_norm * (PEPPER_TOP_CAM_HFOV_DEG / 2)

    return bearing_deg, best["confidence"]