# `speech/tts.py` — TextToSpeech

Makes Pepper speak using the NAOqi text-to-speech engine (ALTextToSpeech).

## Class: `TextToSpeech`

### Constructor

```python
TextToSpeech(session)
```

---

### `speak(text, animated=False) → None`

Speak *text*. Blocks until speech is finished.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Text to say |
| `animated` | `bool` | `False` | If `True`, adds body gestures |

```python
tts.speak("Hello! I am Pepper.")
tts.speak("Nice to meet you!", animated=True)
```

---

### `animated_speak(text) → None`

Identical to `speak(text, animated=True)`.

---

### `say_localized(text) → None`

Say *text* using the robot's current language setting (useful when the
language may have been changed at runtime).

---

### `set_language(language) → None`

Change the speech language.

```python
tts.set_language("English")   # default
tts.set_language("Swedish")
tts.set_language("French")
```

---

### `get_language() → str`

Return the current language name.

---

### `get_available_languages() → list[str]`

Return all languages installed on this robot.

---

### `set_volume(volume) → None`

Set the speech volume.

| Parameter | Range | Default |
|-----------|-------|---------|
| `volume` | `0.0–1.0` | `0.75` |

---

### `get_volume() → float`

Return the current volume.

---

### `set_speed(speed) → None`

Set the speech rate.

| Parameter | Range | Default | Notes |
|-----------|-------|---------|-------|
| `speed` | `50–200` | `100` | 100 = normal, 80 = slow, 130 = fast |

---

### `set_pitch(pitch) → None`

Set the voice pitch.

| Parameter | Range | Default |
|-----------|-------|---------|
| `pitch` | `0.5–4.0` | `1.0` (normal) |

---

### `stop() → None`

Interrupt the current speech immediately.

---

## NAOqi Speech Tags

You can embed formatting tags in the text string for pauses and emphasis:

```
"Hello \\pau=500\\ how are you?"    # 500 ms pause
"I REALLY \\emph=2\\ want to help."  # emphasis
"Welcome to \\vct=130\\ Umeå! \\vct=100\\"  # speed change mid-sentence
```

> Double-escape the backslash in Python strings: `\\pau=500\\`
