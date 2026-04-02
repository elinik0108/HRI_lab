# `vision/human_detection.py` — HumanDetector

Detects people in a camera frame using **YOLOv8n** running locally via
**OpenVINO** (no internet, no GPU required).  
Returns bounding boxes and confidence scores for everyone visible in the image.

## Class: `HumanDetector`

### Constructor

```python
HumanDetector(
    model_path=YOLO_DETECT_MODEL,   # from config.py
    conf_threshold=0.50,
    iou_threshold=0.45,
    device="CPU"
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_path` | `str` | `config.YOLO_DETECT_MODEL` | Path to YOLOv8n OpenVINO XML |
| `conf_threshold` | `float` | `0.50` | Minimum confidence to keep a detection |
| `iou_threshold` | `float` | `0.45` | NMS overlap threshold |
| `device` | `str` | `"CPU"` | `"CPU"` or `"GPU"` |

Loading the model takes ~1–2 seconds on first call.

---

### `detect(frame) → list[dict]`

Detect all people visible in *frame*.

```python
people = detector.detect(frame)
```

Each entry in the returned list is a dict:

```python
{
    "bbox":       [x1, y1, x2, y2],   # pixel coordinates (int)
    "confidence": 0.87,                # float 0–1
}
```

Returns `[]` if no people are found or *frame* is `None`.

**Example — draw bounding boxes:**

```python
people = detector.detect(frame)
for p in people:
    x1, y1, x2, y2 = p["bbox"]
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 128), 2)
    cv2.putText(frame, f"{p['confidence']:.0%}", (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2)
```

---

### `is_someone_present(frame) → bool`

True if at least one person is detected above the confidence threshold.

```python
if detector.is_someone_present(frame):
    tts.speak("Hello!")
```

---

## How it Works

1. The frame is **letterboxed** to 640×640 (padded, not distorted).
2. OpenVINO runs inference — model output shape: `[1, 84, 8400]`.
3. Column 4 of each anchor contains the person-class score.
4. Anchors above `conf_threshold` are kept.
5. Non-Maximum Suppression (NMS) removes overlapping boxes.
6. Coordinates are rescaled back to the original frame size.

## Notes

- Only detects class 0 (person). For other objects, see [`object_detection.md`](object_detection.md).
- Does **not** identify *who* the person is — there is no face recognition.
- Inference runs on CPU; expect ~200 ms per frame.
