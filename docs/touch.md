# `interaction/touch.py` — TouchSensor

Reads Pepper's physical touch sensors: head (3 zones), hands (2), forearm
bumpers (3), and chest button.

## Enum: `TouchZone`

| Constant | Sensor |
|----------|--------|
| `TouchZone.HEAD_FRONT` | Front head button |
| `TouchZone.HEAD_MIDDLE` | Middle head button |
| `TouchZone.HEAD_REAR` | Rear head button |
| `TouchZone.HAND_LEFT` | Left hand sensor |
| `TouchZone.HAND_RIGHT` | Right hand sensor |
| `TouchZone.BUMPER_LEFT` | Left forearm bumper |
| `TouchZone.BUMPER_RIGHT` | Right forearm bumper |
| `TouchZone.BUMPER_BACK` | Back bumper |
| `TouchZone.CHEST` | Chest button |

---

## Class: `TouchSensor`

### Constructor

```python
TouchSensor(session)
```

---

### `on_event(zone, callback) → handle`

Subscribe to touch events on a sensor zone. *callback* is called with
`value = 1.0` when pressed and `value = 0.0` when released.

**Returns** a handle object. Keep it alive in a variable — when the
handle is garbage-collected the subscription is removed.

```python
def on_chest(value):
    if value == 1.0:
        print("Chest button pressed!")

handle = touch.on_event(TouchZone.CHEST, on_chest)
```

---

### `remove_event(handle) → None`

Manually unsubscribe the event associated with *handle*.

---

### `remove_all_events() → None`

Remove all active event subscriptions managed by this `TouchSensor` instance.

---

### `get_value(zone) → float`

Poll the current state of a sensor (1.0 = pressed, 0.0 = not pressed).

```python
if touch.get_value(TouchZone.HEAD_MIDDLE) == 1.0:
    tts.speak("You touched my head!")
```

---

### `get_all_state() → dict`

Return the state of all sensors as a dict with `bool` values.

```python
state = touch.get_all_state()
# {
#   "head_front":   False,
#   "head_middle":  True,
#   "head_rear":    False,
#   "hand_left":    False,
#   "hand_right":   False,
#   "bumper_left":  False,
#   "bumper_right": False,
#   "bumper_back":  False,
#   "chest":        False,
# }
```

---

## Example — Head Menu

```python
handle_front  = touch.on_event(TouchZone.HEAD_FRONT,  lambda v: v and tts.speak("Option A"))
handle_middle = touch.on_event(TouchZone.HEAD_MIDDLE, lambda v: v and tts.speak("Option B"))
handle_rear   = touch.on_event(TouchZone.HEAD_REAR,   lambda v: v and tts.speak("Option C"))

tts.speak("Touch my head to choose option A, B, or C.")
time.sleep(15)

touch.remove_all_events()
```
