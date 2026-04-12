# `motion/posture.py` — RobotPosture

Controls Pepper's whole-body standing positions using NAOqi ALRobotPosture.  
Always call `stand_init()` at the start of an interaction to put the robot
in a safe, natural stance.

## Class: `RobotPosture`

### Constructor

```python
RobotPosture(session)
```

---

### `stand_init(speed=None) → None`

Recommended default stance: arms slightly forward, head up. Use this at the
start and end of every interaction.

```python
posture.stand_init()
```

---

### `stand(speed=None) → None`

Neutral upright position with arms at the sides.

---

### `stand_zero(speed=None) → None`

Upright with all joints at zero angle.

---

### `crouch(speed=None) → None`

Lower crouch position (reduces height, less intimidating).

### `go_to(posture_name, speed=None) → bool`

Move to any NAOqi posture by name. Returns `True` on success.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `posture_name` | `str` | — | NAOqi posture name |
| `speed` | `float \| None` | `None` | Movement speed 0.0–1.0; `None` = default |

```python
posture.go_to("StandInit")
posture.go_to("Crouch", speed=0.5)
```

---

### `get() → str`

Return the name of the current posture, e.g. `"StandInit"`, `"Stand"`.

```python
print(posture.get())
```

---

### `available() → list[str]`

Return all posture names available on this robot.

---

## `speed` Parameter

All posture methods accept an optional `speed` argument (float, 0.0–1.0).  
Higher speed means faster movement but potentially less stable transitions.

```python
posture.stand_init(speed=0.8)   # fast
posture.stand_init(speed=0.3)   # slow and gentle
```
