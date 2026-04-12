# `tablet/` — TabletService & Deployment

Controls the 10.1-inch Android tablet mounted on Pepper's chest.  
You can display images, web pages, and videos, and receive touch coordinates
from the user.

The tablet module lives in `HRI_lab_Pepper/tablet/` and exposes two things:

| Symbol | File | Purpose |
|--------|------|---------|
| `TabletService` | `tablet/service.py` | Controls the on-robot tablet (display, webview, brightness, …) |
| `deploy_tablet_pages` | `tablet/deploy.py` | Copies compiled HTML pages to the robot via SSH/SFTP |

```python
from HRI_lab_Pepper.tablet import TabletService, deploy_tablet_pages
```

---

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

## Built-in Tablet Pages

A set of ready-made pages lives in `dashboard/static/tablet/`.

| Page | Path | Key URL parameters |
|------|------|--------------------|
| Welcome / greeting | `welcome.html` | `title`, `subtitle`, `message`, `image` |
| Listening indicator | `listening.html` | `prompt` |
| Image-card menu | `menu_demo.html` | `title`, `subtitle` |
| Question + timer | `question.html` | `question`, `timer`, `hint`, `image` |
| Answer / result | `answer.html` | `result` (`correct`/`wrong`/`info`), `title`, `answer` |
| Information display | `info.html` | `title`, `body`, `items` (pipe-separated), `image`, `icon` |

All pages accept a `?color=#rrggbb` parameter to override the accent colour.

A navigation drawer (☰ button, top-right) is injected by `nav.js` and links
between all pages.

---

## JavaScript Compatibility — Build Step

Pepper's tablet runs an early embedded Chromium browser (~v38, circa 2014)
that only supports **ES5 JavaScript**.  The built-in pages are written in
modern ES6+ for readability.  A Babel-based build step compiles them down to
ES5 before they are served to the robot.

**The build is run automatically by `install.sh`**, so students who followed
the standard install have nothing extra to do.

### What the build does

| Problem | Solution |
|---------|----------|
| `const`/`let`, arrow functions, template literals, destructuring, `for-of` | Babel `@babel/preset-env` targeting IE 11 |
| `fetch()` missing | `whatwg-fetch` polyfill bundled into `dist/polyfills.js` |
| `URLSearchParams` missing | `url-search-params-polyfill` bundled into `dist/polyfills.js` |
| CSS `var(--xxx)` custom properties | Hard-coded values inlined at build time |
| CSS `clamp()` | Replaced with the max value (safe for Pepper's 1280 px tablet) |

Compiled files are written to `dashboard/static/tablet/dist/`.  The dashboard
server automatically prefers `dist/` when the file exists, and falls back to
the source file otherwise (so the dashboard still works on your laptop
before a build is run).

### Re-running the build after editing a tablet page

```bash
cd HRI_lab_Pepper/dashboard/static/tablet
node build.js          # or: npm run build
```

Node.js must be installed.  The first time also requires:

```bash
npm install            # installs Babel + polyfill packages into node_modules/
```

### Adding a new tablet page

1. Create `dashboard/static/tablet/your_page.html` using ES6+ freely.
2. Run `node build.js` — the page appears in `dist/` ready for the robot.
3. Add it to the `PAGES` list in `nav.js` if you want it in the nav drawer.

---

## Notes

- After Pepper sleeps, the tablet screen turns off. `show_webview()` wakes it
  up automatically.
- Web pages loaded from an external laptop over WiFi can be slow or unreliable.
  Use `deploy_tablet_pages()` to copy pages to the robot once at startup — they
  are then served from the robot's own internal bridge IP (198.18.0.1) with no
  dependency on external WiFi.
- **Dashboard**: `robot_loop()` calls `deploy_tablet_pages()` automatically at
  startup.  Standalone scripts (e.g. `demos/menu_demo.py`) call it themselves.

---

## `deploy_tablet_pages(robot_ip, src_dir)` → `bool`

Copies compiled HTML pages from `src_dir` to the robot via SSH/SFTP so the
tablet loads them over the internal WiFi bridge instead of the laptop.
`dist/` is rebuilt automatically via `node build.js` before each deploy.

```python
from pathlib import Path
from HRI_lab_Pepper.tablet import deploy_tablet_pages

src = Path("HRI_lab_Pepper/dashboard/static/tablet")
ok  = deploy_tablet_pages(
    robot_ip = "172.18.48.50",
    src_dir  = src,
)
if ok:
    base = "http://198.18.0.1/apps/tablet"
else:
    base = "http://192.168.1.10:8080/tablet"

tablet.show_webview(f"{base}/welcome.html?title=Hello")
```

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `robot_ip` | `str` | Robot IP address |
| `src_dir` | `Path` | Directory containing the tablet pages (chooses `dist/` if present) |

Returns `True` on success, `False` on any failure (paramiko missing, SSH error).

SSH auth is attempted in order: keyboard-interactive → password (`robofun`) → public key.
