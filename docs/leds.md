# `motion/leds.py` — RobotLEDs

Controls the RGB LEDs in Pepper's eyes and chest.  
LEDs are a simple and expressive way to show the robot's emotional state.

## Class: `RobotLEDs`

### Constructor

```python
RobotLEDs(session)
```

---

### Preset States

| Method | Colour | Meaning |
|--------|--------|---------|
| `happy()` | Green | Positive, success |
| `thinking()` | Rotating blue | Processing, waiting |
| `sad()` | Dim blue | Empathy, negative |
| `error()` | Red | Failure, timeout, error |
| `off()` | Off | Reset / idle |

```python
leds.thinking()
result = compute_something()
leds.happy() if result else leds.error()
time.sleep(1)
leds.off()
```

---

### `set_eyes(r, g, b, duration=0.2) → None`

Set both eye rings to a solid colour (values 0.0–1.0).

```python
leds.set_eyes(1.0, 0.5, 0.0)   # orange
leds.set_eyes(0.0, 0.0, 1.0)   # blue
leds.set_eyes(0.0, 0.0, 0.0)   # off
```

---

### `set_body(r, g, b, duration=0.2) → None`

Set the chest LED colour.

---

### `blink(r=1.0, g=1.0, b=1.0, times=3, on_duration=0.2, off_duration=0.2) → None`

Blink the eye LEDs *times* times.

```python
leds.blink(r=1.0, g=1.0, b=0.0, times=3)   # yellow blink ×3
```

---

### `off() → None`

Turn off all LED groups.

---

## Colour Reference

| Colour | r | g | b |
|--------|---|---|---|
| Red | 1.0 | 0.0 | 0.0 |
| Green | 0.0 | 1.0 | 0.0 |
| Blue | 0.0 | 0.0 | 1.0 |
| Yellow | 1.0 | 1.0 | 0.0 |
| Orange | 1.0 | 0.5 | 0.0 |
| Cyan | 0.0 | 1.0 | 1.0 |
| White | 1.0 | 1.0 | 1.0 |
| Off | 0.0 | 0.0 | 0.0 |

---

## Notes

- `thinking()` starts a rotating animation in a background thread. Call
  `off()` to stop it.
- Eye and body LEDs are controlled independently.
- `duration` in `set_eyes()` / `set_body()` is the fade transition time.
