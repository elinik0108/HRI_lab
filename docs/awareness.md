# `interaction/awareness.py` — BasicAwareness

Enables/disables NAOqi's built-in human presence detection and gaze tracking
(ALBasicAwareness). When running, Pepper passively turns its head toward
people without you writing any code.

## Class: `BasicAwareness`

### Constructor

```python
BasicAwareness(session)
```

---

### `start() → None`

Start awareness. Pepper begins scanning and tracking people.

```python
awareness.start()
```

---

### `stop() → None`

Stop awareness. Pepper's head stays in its current position.

```python
awareness.stop()
```

---

### `is_running() → bool`

Return `True` if awareness is currently active.

---

### `set_engagement_mode(mode) → None`

Control how Pepper reacts when multiple people are present.

| `mode` | Behaviour |
|--------|-----------|
| `"Unengaged"` | Look around freely, ignore everyone |
| `"FullyEngaged"` | Lock onto one person and stay focused on them |
| `"SemiEngaged"` | Default: track the nearest person but glance at others |

```python
awareness.set_engagement_mode("FullyEngaged")
```

---

### `set_tracking_mode(mode) → None`

Control which sensors are used for tracking.

| `mode` | Description |
|--------|-------------|
| `"Head"` | Track with head/eyes only |
| `"BodyRotation"` | Also rotate body |
| `"WholeBody"` | Full-body tracking |

---

## Recommended Pattern

```python
# At the start of a session
awareness.start()

# While waiting for a user — awareness scans automatically
while not detector.is_someone_present(cam.get_frame()):
    time.sleep(0.3)

# User detected — engage fully
awareness.set_engagement_mode("FullyEngaged")
tts.speak("Hello!")

# At the end — restore default
awareness.set_engagement_mode("SemiEngaged")
```

---

## Notes

- `PepperSession.disable_autonomous_life()` disables a higher-level behaviour
  system that overrides awareness. Make sure to call it first.
- `BasicAwareness` only moves the head (and body in BodyRotation mode). It
  does **not** make the robot walk toward people.
