# `motion/tracker.py` — RobotTracker

Controls Pepper's active tracking and arm-pointing behaviour through
NAOqi ALTracker.

## Class: `RobotTracker`

### Constructor

```python
RobotTracker(session)
```

---

### `track_face(face_size=0.15) → None`

Start continuously tracking the nearest face with the head and eyes.  
The robot will turn its head to follow whoever it detects.

```python
tracker.track_face()
# ... interaction ...
tracker.stop()
```

---

### `track_object(target_name, target_size=0.10) → None`

Track an arbitrary object by its NAOqi target name.

---

### `track_person() → None`

Shorthand for `track_face()` using the "People" tracker mode.

---

### `stop() → None`

Stop all active tracking. The head stays in its last position.

---

### `point_at(x, y, z, *, effector="RArm", frame=2, speed=0.5) → None`

Raise one arm and point to a 3D location.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `float` | — | Distance forward (metres) |
| `y` | `float` | — | Distance left (metres, negative = right) |
| `z` | `float` | — | Height (metres) |
| `effector` | `str` | `"RArm"` | `"RArm"` or `"LArm"` |
| `frame` | `int` | `2` | Coordinate frame: 0=torso, 1=world, 2=robot |
| `speed` | `float` | `0.5` | Arm movement speed 0.0–1.0 |

```python
# Point at a table 1.2 m ahead and slightly right
tracker.point_at(1.2, -0.3, 0.8, effector="RArm")
time.sleep(3)
tracker.stop()
posture.stand_init()
```

---

### `look_at(x, y, z, *, frame=2, speed=0.3) → None`

Turn the **head** to face a 3D point.

```python
tracker.look_at(1.5, 0.0, 1.4)   # look forward and slightly up
```

---

### `is_active() → bool`

Return `True` if a tracker is currently running.

---

### `get_target_position() → list`

Return the `[x, y, z]` coordinates of the last tracked target.

---

## Coordinate System

Pepper uses a right-hand coordinate system with the origin at the robot's
feet:

- **x** — forward
- **y** — left (negative = right)
- **z** — up

Typical values for a standing person in front of the robot:

```
x ≈ 0.8–1.5 m   (how far they are)
y ≈ -0.3–0.3 m  (left/right offset)
z ≈ 1.0–1.6 m   (chest–head height)
```
