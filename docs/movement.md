# `motion/movement.py` — RobotMovement

Controls Pepper's locomotion (walking and turning) through NAOqi ALMotion.

> **Safety note:** Always have someone nearby when running movement code on
> the physical robot for the first time.

## Class: `RobotMovement`

### Constructor

```python
RobotMovement(session)
```

---

### `walk_to(x, y, theta, *, speed=0.5) → None`

Walk to a position relative to the robot's current location.  
Blocks until the motion is complete.

| Parameter | Unit | Description |
|-----------|------|-------------|
| `x` | metres | Forward distance (negative = backwards) |
| `y` | metres | Lateral distance (positive = left, negative = right) |
| `theta` | radians | Final heading rotation |
| `speed` | 0.0–1.0 | Walking speed (default 0.5) |

```python
import math

mov.walk_to(1.0, 0.0, 0.0)           # 1 m forward
mov.walk_to(0.0, 0.5, 0.0)           # 0.5 m to the left
mov.walk_to(0.0, 0.0, math.pi / 2)   # turn 90° left in place
```

---

### `move_toward(vx, vy, vtheta) → None`

Start continuous movement (non-blocking). The robot keeps moving until
`stop()` is called.

| Parameter | Range | Description |
|-----------|-------|-------------|
| `vx` | -1.0–1.0 | Forward/backward velocity |
| `vy` | -1.0–1.0 | Lateral velocity |
| `vtheta` | -1.0–1.0 | Rotation velocity |

---

### `rotate(angle_rad, *, speed=0.5) → None`

Turn in place by *angle_rad* radians.

```python
import math

mov.rotate(math.radians(90))     # turn left 90°
mov.rotate(math.radians(-45))    # turn right 45°
mov.rotate(math.pi)              # turn 180°
```

---

### `stop() → None`

Stop any ongoing movement immediately.

---

### `is_moving() → bool`

Return `True` if the robot is currently executing a move.

---

### `get_position(frame=2) → list`

Return the robot's current `[x, y, theta]` in the given coordinate frame.

| `frame` | Description |
|---------|-------------|
| `0` | Torso |
| `1` | World |
| `2` | Robot (default) |

---

### `rest() → None`

Put Pepper into rest mode (crouched, stiffness removed). Use at the end of a
session if the robot will be left unattended.

---

### `wake_up() → None`

Wake up from rest mode (stands up, stiffness restored).

---

## Notes

- `walk_to()` uses the robot's odometry which can drift; do not rely on
  centimetre accuracy.
- Always call `stop()` before calling `posture.stand_init()` to avoid
  conflicting joint commands.
- On a real floor, lateral movement (`y`) may be imprecise — Pepper's omni
  wheels have limited lateral traction.
