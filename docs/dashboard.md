# `dashboard.py` / `dashboard/` — Live Dashboard

The dashboard is a browser-based control panel for developing and demonstrating
your Pepper application. It streams the camera, shows console output, displays
touch sensor states, and lets you toggle pipeline modules at runtime.

## Starting the Dashboard

```bash
source .venv_students/bin/activate
python HRI_lab_Pepper/dashboard.py --url tcp://ROBOT_IP:9559
```

Then open **http://localhost:8080** in your browser.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | `tcp://172.18.48.50:9559` | Robot NAOqi URL |
| `--port` | `8080` | Dashboard HTTP port |
| `--fps` | `10` | Camera capture rate |

---

## Dashboard Panels

### Camera Feed (top left)

Live MJPEG stream from Pepper's front camera. When **Human Detection** is on,
green bounding boxes and confidence percentages are overlaid. When **Object
Detection** is on, each detected object gets a colour-coded box with its label.

---

### Console (top right)

All output sent to `stdout` from the robot loop (your `print()` calls, module
status messages) appears here in real time.

---

### Controls Bar (bottom)

#### PIPELINE group

| Button | Default | Effect |
|--------|---------|--------|
| Human Detection | ON | Toggle person detection overlay |
| Speech-to-Text | OFF | Toggle STT (listen for voice) |
| Object Detection | OFF | Toggle COCO 80-class detection overlay |

#### AWARENESS group

| Button | Description |
|--------|-------------|
| Start | Enable BasicAwareness (Pepper tracks people) |
| Stop  | Disable BasicAwareness |

#### POSTURE group

| Button | Action |
|--------|--------|
| Stand | `posture.stand()` |
| StandInit | `posture.stand_init()` |
| Crouch | `posture.crouch()` |

#### LEDS group

| Button | LED state |
|--------|-----------|
| Happy | Green |
| Thinking | Rotating blue |
| Sad | Dim blue |
| Error | Red |
| Off | All off |

#### Tablet page selector

Shows predefined tablet pages (welcome, menu, answer, listening, info).

#### SAY

Type any text and press **Enter** (or click **Say**) to make Pepper speak it
immediately.

#### STOP ALL

Graceful shutdown: stops camera, STT, awareness, LEDs off, stand-init posture.

---

### Touch Sensor Grid (bottom right)

Real-time display of all 9 physical sensors. A sensor turns green when
pressed.

---

## Architecture Overview

```
browser (WebSocket + MJPEG)
       │
       │  WS events (JSON)
       ▼
  aiohttp server (port 8080)
       │
       │  flags, commands
       ▼
  robot_loop() thread
       │
       ├── PepperCamera (background thread)
       ├── HumanDetector / ObjectDetector (per frame)
       ├── SpeechToText (optional)
       └── all other modules
```

The server communicates with the browser over WebSocket for bidirectional
control. Camera frames are pushed as MJPEG over a separate HTTP endpoint.

---

## Notes

- The dashboard must be running for `robot_loop()` to execute. If you close
  the browser, the loop keeps running.
- All modules are initialised inside `robot_loop()`, so they start
  automatically when you launch the dashboard.
- You can write custom commands that get picked up from the
  `command_queue` in `server.py` if you want to add your own dashboard buttons.
