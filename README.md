# Getting Started with the Pepper Robot API

This guide walks you through installing the student API, connecting to the robot, and building your interactive application step by step.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Connecting to the Robot](#2-connecting-to-the-robot)
3. [Module Reference](#3-module-reference)
4. [Common Patterns](#4-common-patterns)
5. [Running the Dashboard](#5-running-the-dashboard)
6. [Logging Interaction Data](#6-logging-interaction-data)
7. [Tips & Troubleshooting](#7-tips--troubleshooting)

---

## 1. Installation

Run the install script once from the project root:

```bash
bash ./install.sh
```

This creates a virtual environment, installs all dependencies, and downloads the speech recognition model. Then activate it:

```bash
source .venv/bin/activate
```

Test the dashboard with:

```bash
python HRI_lab_Pepper/dashboard.py --url tcp://ROBOT_IP:9559
```

Then open **http://localhost:8080** in your browser and you should see something like:

<img width="3675" height="1910" alt="Screenshot from 2026-04-02 18-07-52" src="https://github.com/user-attachments/assets/9e7db66f-702d-44cf-aac8-eca02b9dd6de" />

For more information on the dashboard, see [./docs/dashboard.md](./docs/dashboard.md).

---

## 2. Connecting to the Robot

Every script starts the same way — create a session with the robot's IP address:

```python
from HRI_lab_Pepper.session import PepperSession

# Replace with your robot's actual IP
session = PepperSession.connect("tcp://172.18.48.50:9559")

# Stop random head/eye movements before your interaction starts
PepperSession.disable_autonomous_life()
```

At the end of your script, always disconnect cleanly:

```python
PepperSession.disconnect()
```

---

## 3. Module Reference

### `PepperSession` — Robot Connection

```python
from HRI_lab_Pepper.session import PepperSession

session = PepperSession.connect("tcp://ROBOT_IP:9559")
session = PepperSession.get()           # retrieve session wherever needed
PepperSession.disable_autonomous_life() # stop random movements
PepperSession.enable_autonomous_life()  # restore normal behaviour
PepperSession.disconnect()
```

---

### `TextToSpeech` — Make Pepper Speak

```python
from HRI_lab_Pepper.speech.tts import TextToSpeech

tts = TextToSpeech(session)

tts.speak("Hello! How can I help you?")
tts.speak("I am waving at you!", animated=True)   # with body gestures
tts.set_language("English")   # or "Swedish", "French", etc.
tts.set_volume(0.8)           # 0.0–1.0
tts.set_speed(90)             # 50–200, 100 = normal
tts.stop()                    # interrupt speech
```

---

### `SpeechToText` — Listen to the User

```python
from HRI_lab_Pepper.speech.stt import SpeechToText

stt = SpeechToText(session, timeout_sec=10)

# Call once at startup
stt.register_and_subscribe()

# Blocking call — returns the transcribed sentence or "" on timeout
text = stt.listen()
print("User said:", text)

# Call when done listening
stt.unsubscribe()
```

> **Note:** `listen()` blocks until the user stops speaking or the timeout expires. Call it in a loop to keep listening.

---

### `PepperCamera` — Get Camera Frames

```python
from HRI_lab_Pepper.vision.camera import PepperCamera
import cv2

cam = PepperCamera(session)
cam.start()

frame = cam.get_frame()     # returns a BGR numpy array (480×640×3) or None
if frame is not None:
    cv2.imwrite("snapshot.jpg", frame)

cam.stop()

# Or use as a context manager:
with PepperCamera(session) as cam:
    frame = cam.wait_for_frame(timeout=5.0)
```

---

### `HumanDetector` — Detect People

Detects whether someone is standing in front of the robot. Does **not** identify who it is.

```python
from HRI_lab_Pepper.vision.human_detection import HumanDetector

detector = HumanDetector()

frame = cam.get_frame()

# Simple: True/False
if detector.is_someone_present(frame):
    print("Someone is here!")

# Detailed: list of detections with bounding boxes
people = detector.detect(frame)
for person in people:
    x1, y1, x2, y2 = person["bbox"]
    confidence      = person["confidence"]
    print(f"Person at ({x1},{y1})–({x2},{y2}), confidence={confidence:.0%}")
```

---

### `ObjectDetector` — Detect Objects (80 COCO classes)

Detects everyday objects in front of the robot — cups, chairs, bottles, laptops, and 75 more categories from the COCO dataset.

```python
from HRI_lab_Pepper.vision.object_detection import ObjectDetector

det = ObjectDetector()

frame = cam.get_frame()

# Detect everything
objects = det.detect(frame)
for obj in objects:
    label = obj["label"]          # e.g. "cup", "chair", "person"
    conf  = obj["confidence"]     # float 0–1
    x1, y1, x2, y2 = obj["bbox"] # pixel coordinates
    print(f"{label}: {conf:.0%} at ({x1},{y1})–({x2},{y2})")

# Detect only a specific class
cups = det.detect_class(frame, "cup")

# Create a detector that only ever returns bottles and cups
limited_det = ObjectDetector(classes=["bottle", "cup"])
items = limited_det.detect(frame)

# See all 80 class names
print(det.get_labels())
```

> `ObjectDetector` uses the same YOLOv8n model as `HumanDetector`.  
> Running both at once doubles inference time — if you only need people, stick with `HumanDetector`.

---

### `TabletService` — Chest Tablet

```python
from HRI_lab_Pepper.interaction.tablet import TabletService

tablet = TabletService(session)

# Display an image (URL must be reachable from the robot's network)
tablet.show_image("http://192.168.1.10:8000/apple.jpg")

# Open a web page (great for showing interactive menus)
tablet.show_webview("http://192.168.1.10:8000/menu.html")

# React to tablet touches
def on_touch(x, y):
    print(f"Tablet touched at ({x:.2f}, {y:.2f})")  # x,y in [0,1]

tablet.set_on_touch_callback(on_touch)

tablet.set_brightness(0.9)
tablet.hide()   # blank the screen
```

---

### `TouchSensor` — Physical Touch Events

```python
from HRI_lab_Pepper.interaction.touch import TouchSensor, TouchZone

touch = TouchSensor(session)

# Event-driven (recommended)
def on_head_touched(value):
    if value == 1.0:
        print("Head touched!")

handle = touch.on_event(TouchZone.HEAD_MIDDLE, on_head_touched)
# Keep 'handle' alive — when garbage-collected the subscription is removed

# Available zones:
#   TouchZone.HEAD_FRONT, HEAD_MIDDLE, HEAD_REAR
#   TouchZone.HAND_LEFT,  HAND_RIGHT
#   TouchZone.BUMPER_LEFT, BUMPER_RIGHT, BUMPER_BACK
#   TouchZone.CHEST

# Synchronous poll (all sensors at once)
state = touch.get_all_state()
# {'head_front': False, 'head_middle': True, 'hand_left': False, …}

# Clean up
touch.remove_event(handle)
touch.remove_all_events()
```

---

### `RobotPosture` — Standing Positions

```python
from HRI_lab_Pepper.motion.posture import RobotPosture

posture = RobotPosture(session)

posture.stand_init()        # default interaction stance (recommended at start)
posture.stand()             # neutral upright
posture.crouch()            # lower posture
posture.go_to("Sit")        # any Naoqi posture name
print(posture.get())        # e.g. "StandInit"
```

---

### `RobotTracker` — Point and Look

```python
from HRI_lab_Pepper.motion.tracker import RobotTracker

tracker = RobotTracker(session)

# Point an arm at a 3D location (robot frame: x=forward, y=left, z=up, in metres)
tracker.point_at(1.5, 0.3, 1.0)            # point right arm at a shelf
tracker.point_at(0.8, -0.2, 0.9, effector="LArm")  # left arm

# Turn head toward a point
tracker.look_at(1.0, 0.0, 1.2)

# Track the nearest face with the head
tracker.track_face()
# … after a few seconds:
tracker.stop()
```

---

### `RobotLEDs` — Eye and Chest LEDs

```python
from HRI_lab_Pepper.motion.leds import RobotLEDs

leds = RobotLEDs(session)

# Emotion presets
leds.happy()      # green — positive response
leds.thinking()   # rotating blue — processing
leds.sad()        # dim blue — empathy
leds.error()      # red — failure or timeout

# Custom colour (values 0.0–1.0)
leds.set_eyes(1.0, 0.5, 0.0)   # orange eyes
leds.set_body(0.0, 0.0, 1.0)   # blue chest
leds.blink(r=1.0, g=1.0, b=0.0, times=3)  # yellow blink ×3
leds.off()
```

---

### `RobotMovement` — Navigate

```python
from HRI_lab_Pepper.motion.movement import RobotMovement
import math

mov = RobotMovement(session)

mov.walk_to(1.0, 0.0, 0.0)          # 1 m forward
mov.walk_to(0.0, 0.5, 0.0)          # 0.5 m to the left
mov.rotate(math.radians(90))         # turn 90° left
mov.stop()
print(mov.is_moving())               # True / False
```

---

### `BasicAwareness` — Detect Human Presence Passively

```python
from HRI_lab_Pepper.interaction.awareness import BasicAwareness

awareness = BasicAwareness(session)

awareness.start()
awareness.set_engagement_mode("FullyEngaged")  # lock onto one person
# "SemiEngaged" or "Unengaged" also available

awareness.stop()
```

---

## 4. Common Patterns

### Wait until a user appears

```python
import time

cam      = PepperCamera(session)
detector = HumanDetector()
cam.start()

print("Waiting for a user…")
while True:
    frame = cam.get_frame()
    if frame is not None and detector.is_someone_present(frame):
        break
    time.sleep(0.2)

print("User detected — starting interaction!")
tts.speak("Hello! Welcome.")
```

---

### Listen, then respond

```python
stt.register_and_subscribe()
tts.speak("What would you like?")
leds.thinking()

answer = stt.listen()   # blocks up to timeout_sec

leds.off()
if answer:
    tts.speak(f"You said: {answer}")
else:
    tts.speak("Sorry, I didn't catch that.")
```

---

### Fallback from voice to tablet

```python
tts.speak("Please tell me your choice, or tap the screen.")

# Listen for voice first
answer = stt.listen()

if not answer:
    # Voice failed — switch to tablet interaction
    tablet.show_webview("http://192.168.1.10:8000/choice.html")
    tts.speak("Please tap your choice on the screen.")
    # Your tablet touch callback will handle the response
```

---

### Dialogue loop with timeout reset

```python
stt.register_and_subscribe()

for turn in range(3):       # up to 3 conversation turns
    tts.speak("Go on, I am listening.")
    response = stt.listen()

    if not response:
        tts.speak("I did not hear anything. Let me try again.")
        continue

    # process response …
    if "yes" in response.lower():
        tts.speak("Great!")
        break
    elif "no" in response.lower():
        tts.speak("No problem.")
        break
```

---

### Point at a physical object

```python
# Pointing at a table in front of the robot, slightly to the right
tracker.point_at(1.2, -0.3, 0.8, effector="RArm")
tts.speak("Here is the object you need.")
time.sleep(3)
tracker.stop()
posture.stand_init()
```

---

### Reset for the next user (timeout guard)

```python
import time

INTERACTION_TIMEOUT = 120   # seconds

start = time.time()
in_session = True

while in_session:
    if time.time() - start > INTERACTION_TIMEOUT:
        tts.speak("I did not hear anything for a while. Goodbye!")
        leds.sad()
        time.sleep(2)
        in_session = False

    # … your interaction logic …

# Reset for next user
leds.off()
posture.stand_init()
tts.speak("Ready for the next person.")
```

---

## 5. Running the Dashboard

The dashboard gives you a live view of the camera, touch sensors, console output, and quick controls while you develop.

```bash
# Make sure your virtual environment is active
source .venv/bin/activate

python HRI_lab_Pepper/dashboard.py --url tcp://ROBOT_IP:9559
```

Then open **http://localhost:8080** in your browser.

**Dashboard features:**
- **Live camera** — real-time MJPEG stream with human detection boxes
- **Console** — all `print()` output from the robot loop appears here
- **Touch sensors** — live grid showing all 9 sensors (head, hands, bumpers, chest)
- **Toggles** — enable/disable Human Detection and Speech-to-Text at runtime
- **Posture** — Stand / StandInit / Crouch buttons
- **LEDs** — Happy / Thinking / Sad / Error / Off presets
- **Say** — type any text and press Enter to hear Pepper speak it
- **Stop All** — clean shutdown

---

## 6. Logging Interaction Data

All assignment groups are asked to store interaction data. Here is a simple pattern using CSV:

```python
import csv
import time

LOG_FILE = "interaction_log.csv"

def log_event(event_type, data):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), event_type, data])

# Usage during your interaction
log_event("user_detected",  "")
log_event("stt_result",     user_speech)
log_event("tablet_choice",  chosen_item)
log_event("session_end",    f"duration={elapsed:.1f}s")
```

For structured data (JSON per session):

```python
import json, time

session_data = {
    "start_time": time.time(),
    "turns": [],
}

# After each interaction turn:
session_data["turns"].append({
    "t": time.time() - session_data["start_time"],
    "robot": tts_text,
    "user":  stt_text,
})

# At session end:
with open(f"session_{int(time.time())}.json", "w") as f:
    json.dump(session_data, f, indent=2)
```

---

## 7. Tips & Troubleshooting

**Robot not reachable**
Make sure your laptop and the robot are on the same Wi-Fi network. Ping `ROBOT_IP` first:
```bash
ping 172.18.48.50
```

**STT returns empty strings often**
- Increase timeout: `SpeechToText(session, timeout_sec=20)`
- Make sure the room is quiet — Vosk is sensitive to background noise
- Speak clearly into the robot's front microphone (not the tablet)
- The `STT_VAD_RMS_MIN` constant in `config.py` controls the voice activity threshold — lower it if Pepper misses quiet speakers

**Pepper moves randomly during interaction**
Call `PepperSession.disable_autonomous_life()` right after connecting.

**Tablet `show_image()` shows nothing**
The URL must be reachable **from the robot's network**, not your laptop. Serve images with a local HTTP server:
```bash
python -m http.server 8000   # from the folder with your images
# Then use: tablet.show_image("http://YOUR_LAPTOP_IP:8000/image.jpg")
```

**Dashboard camera feed is blank**
The camera only works when the robot is connected. If you run the dashboard without a robot, the feed shows "Waiting for camera…".

**Pepper falls into rest posture**
Never call `ALAutonomousLife.setState("disabled")` — it triggers crouch. Use `PepperSession.disable_autonomous_life()` instead (which is what the API already does).
