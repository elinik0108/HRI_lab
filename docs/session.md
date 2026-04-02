# `session.py` — PepperSession

Manages the connection to the Pepper robot's NAOqi middleware.  
This is the **first thing** every script must do before using any other module.

## Class: `PepperSession`

Singleton — only one connection is maintained at a time. All modules receive
the same `qi.Session` object through `PepperSession.get()`.

---

### `PepperSession.connect(url) → qi.Session`

Open a connection to the robot.

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `str` | NAOqi URL, e.g. `"tcp://172.18.48.50:9559"` |

```python
from HRI_lab_Pepper.session import PepperSession

session = PepperSession.connect("tcp://172.18.48.50:9559")
```

Raises `RuntimeError` if already connected. Raises `ConnectionError` if the
robot is unreachable.

---

### `PepperSession.get() → qi.Session`

Retrieve the active session from anywhere in your code.

```python
session = PepperSession.get()
```

Raises `RuntimeError` if `connect()` has not been called yet.

---

### `PepperSession.disable_autonomous_life() → None`

Stop Pepper's random background movements (head scanning, blinking into gaze
mode, attention tracking). **Call this right after connecting** to keep the
robot still during your interaction.

```python
PepperSession.disable_autonomous_life()
```

---

### `PepperSession.enable_autonomous_life() → None`

Re-enable the robot's background behaviours. Useful if you want to restore the
robot to its waiting state.

```python
PepperSession.enable_autonomous_life()
```

---

### `PepperSession.disconnect() → None`

Close the session. Always call this at the end of your script.

```python
PepperSession.disconnect()
```

---

## Typical Script Structure

```python
from HRI_lab_Pepper.session import PepperSession

# 1. Connect
session = PepperSession.connect("tcp://172.18.48.50:9559")
PepperSession.disable_autonomous_life()

try:
    # 2. Your interaction logic here
    pass

finally:
    # 3. Always clean up
    PepperSession.disconnect()
```
