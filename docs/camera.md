# `vision/camera.py` — PepperCamera

Captures frames from Pepper's front camera in a background thread, so your
main loop can call `get_frame()` at any time without waiting.

## Class: `PepperCamera`

### Constructor

```python
PepperCamera(session, *, fps=10, resolution="VGA")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `qi.Session` | — | Active session from `PepperSession.get()` |
| `fps` | `int` | `10` | Target capture rate (frames per second) |
| `resolution` | `str` | `"VGA"` | `"VGA"` (640×480) or `"QVGA"` (320×240) |

---

### `start() → None`

Start the background capture thread. Call once before using `get_frame()`.

```python
cam = PepperCamera(session)
cam.start()
```

---

### `stop() → None`

Stop the capture thread and unsubscribe from the camera.

```python
cam.stop()
```

---

### `get_frame() → np.ndarray | None`

Return the most recently captured frame as a BGR NumPy array, or `None` if
no frame has arrived yet.

```python
frame = cam.get_frame()
if frame is not None:
    # frame.shape == (480, 640, 3)
    cv2.imwrite("photo.jpg", frame)
```

---

### `wait_for_frame(timeout=5.0) → np.ndarray | None`

Block until a frame is available or *timeout* seconds elapse.

```python
frame = cam.wait_for_frame(timeout=3.0)
```

---

### `wait_for_next_frame(timeout=5.0) → np.ndarray | None`

Block until a **new** frame arrives (useful when you need a fresh image after
something changed — e.g. Pepper just moved its head).

```python
# guarantee a fresh image
tracker.look_at(1.0, 0.0, 1.2)
time.sleep(0.5)
frame = cam.wait_for_next_frame()
```

---

### `get_stats() → dict`

Return camera performance counters.

```python
stats = cam.get_stats()
# {
#   "actual_fps": 9.8,
#   "requested_fps": 10,
#   "resolution": "VGA",
#   "frames_captured": 1234
# }
```

---

### Context Manager

`PepperCamera` supports `with` syntax that automatically calls `start()` and
`stop()`:

```python
with PepperCamera(session) as cam:
    frame = cam.wait_for_frame()
    # cam.stop() is called automatically when the block exits
```

---

## Notes

- Frames are BGR (OpenCV format), not RGB.
- `get_frame()` is non-blocking and can return `None` on the first few calls
  while the camera is warming up. Use `wait_for_frame()` if you need to
  guarantee a result.
- Resolution `"VGA"` (640×480) is recommended for computer vision tasks.
