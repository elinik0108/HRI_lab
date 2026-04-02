# `vision/object_detection.py` — ObjectDetector

Detects any of the **80 COCO object classes** in a camera frame using the same
YOLOv8n model as `HumanDetector`.

Common detectable classes include: `person`, `chair`, `cup`, `bottle`,
`laptop`, `book`, `cell phone`, `backpack`, `bicycle`, `car`, and 70 more.

## Class: `ObjectDetector`

### Constructor

```python
ObjectDetector(
    model_path=YOLO_DETECT_MODEL,
    conf_threshold=0.40,
    iou_threshold=0.45,
    device="CPU",
    classes=None
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_path` | `str` | `config.YOLO_DETECT_MODEL` | Path to OpenVINO XML |
| `conf_threshold` | `float` | `0.40` | Minimum confidence |
| `iou_threshold` | `float` | `0.45` | NMS overlap threshold |
| `device` | `str` | `"CPU"` | `"CPU"` or `"GPU"` |
| `classes` | `list[str] \| None` | `None` | Restrict to these labels only |

If `classes` is provided, only those class names are returned even though
detection runs over all 80 classes internally.

---

### `detect(frame) → list[dict]`

Detect all objects in *frame*.

```python
objects = detector.detect(frame)
```

Each entry:

```python
{
    "bbox":       [x1, y1, x2, y2],   # pixel coordinates (int)
    "confidence": 0.82,                # float 0–1
    "label":      "cup",               # COCO class name
    "class_id":   41,                  # COCO class index (0–79)
}
```

Returns `[]` if nothing is detected or *frame* is `None`.

**Example — draw all detections:**

```python
objects = detector.detect(frame)
for obj in objects:
    x1, y1, x2, y2 = obj["bbox"]
    text = f"{obj['label']} {obj['confidence']:.0%}"
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
    cv2.putText(frame, text, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
```

---

### `detect_class(frame, label) → list[dict]`

Convenience wrapper — detect only objects of class *label*.

```python
cups = detector.detect_class(frame, "cup")
```

This temporarily overrides the `classes` filter for this single call.

---

### `get_labels() → list[str]`

Return all 80 COCO class names as a list (indices 0–79).

```python
labels = detector.get_labels()
print(labels[0])   # "person"
print(labels[41])  # "cup"
```

---

### Full COCO Label List

```
0:  person        1:  bicycle       2:  car          3:  motorcycle
4:  airplane      5:  bus           6:  train         7:  truck
8:  boat          9:  traffic light 10: fire hydrant  11: stop sign
12: parking meter 13: bench         14: bird          15: cat
16: dog           17: horse         18: sheep         19: cow
20: elephant      21: bear          22: zebra         23: giraffe
24: backpack      25: umbrella      26: handbag       27: tie
28: suitcase      29: frisbee       30: skis          31: snowboard
32: sports ball   33: kite          34: baseball bat  35: baseball glove
36: skateboard    37: surfboard     38: tennis racket 39: bottle
40: wine glass    41: cup           42: fork          43: knife
44: spoon         45: bowl          46: banana        47: apple
48: sandwich      49: orange        50: broccoli      51: carrot
52: hot dog       53: pizza         54: donut         55: cake
56: chair         57: couch         58: potted plant  59: bed
60: dining table  61: toilet        62: tv            63: laptop
64: mouse         65: remote        66: keyboard      67: cell phone
68: microwave     69: oven          70: toaster       71: sink
72: refrigerator  73: book          74: clock         75: vase
76: scissors      77: teddy bear    78: hair drier    79: toothbrush
```

---

## Notes

- Do not run both `HumanDetector` and `ObjectDetector` simultaneously — they
  use the same model and CPU, which will halve the frame rate.
- Use `HumanDetector` if you only need person detection (it is slightly faster
  because it filters to one class before NMS).
- NMS is applied per-class so nearby objects of different types don't suppress
  each other.
