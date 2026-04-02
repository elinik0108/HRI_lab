# `interaction/tablet.py` — TabletService

Controls the 10.1-inch Android tablet mounted on Pepper's chest.  
You can display images, web pages, and videos, and receive touch coordinates
from the user.

## Class: `TabletService`

### Constructor

```python
TabletService(session)
```

The constructor calls `enableWifi()` automatically.

---

### `show_image(url) → None`

Display an image from a URL.

```python
tablet.show_image("http://192.168.1.10:8000/welcome.jpg")
```

The URL must be reachable **from the robot's network**. To serve files from
your laptop:

```bash
cd ~/my_project/images
python -m http.server 8000
# URL: http://YOUR_LAPTOP_IP:8000/filename.jpg
```

---

### `show_webview(url, retries=3, retry_delay=0.6) → bool`

Open a web page on the tablet. Returns `True` if the page loaded successfully.

```python
tablet.show_webview("http://192.168.1.10:8000/menu.html")
```

The method retries up to *retries* times if the tablet doesn't respond
immediately, which is common when the tablet wakes from sleep.

---

### `show_video(url) → None`

Start playing a video from a URL.

---

### `stop_video() → None`

Stop any playing video.

---

### `hide() → None`

Blank the tablet screen (show nothing).

---

### `set_brightness(brightness) → None`

Set screen brightness.

| Parameter | Range | Default |
|-----------|-------|---------|
| `brightness` | `0.0–1.0` | `0.8` |

---

### `get_brightness() → float`

Return the current brightness.

---

### `enable_wifi(enabled=True) → None`

Enable or disable the tablet's WiFi radio.

---

### `set_on_touch_callback(callback) → None`

Register a function to be called when the user touches the tablet screen.

```python
def on_touch(x, y):
    # x, y are floats in [0, 1] (relative to screen size)
    print(f"Touched at {x:.2f}, {y:.2f}")

tablet.set_on_touch_callback(on_touch)
```

The callback runs in a background thread.

---

## Serving HTML Pages

The simplest tablet UI is a static HTML file:

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Choice</title></head>
<body style="background:#000;color:#fff;font-size:40px;text-align:center">
  <button onclick="fetch('/api/tablet_input?v=yes')">Yes</button>
  <button onclick="fetch('/api/tablet_input?v=no')">No</button>
</body>
</html>
```

> The dashboard server already exposes `/api/tablet_input` — tablet button
> clicks are forwarded to your Python code via the command queue.

---

## Notes

- After Pepper sleeps, the tablet screen turns off. `show_webview()` wakes it
  up automatically.
- Web pages loaded from an external laptop over WiFi can be slow. For
  production demos, consider copying the pages to the robot (the dashboard
  does this automatically during `robot_loop()` startup).
