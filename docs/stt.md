# `speech/stt.py` — SpeechToText

Captures audio from Pepper's microphones and converts it to text using
**Vosk** (offline, no internet required).

## Class: `SpeechToText`

### Constructor

```python
SpeechToText(session, timeout_sec=15, vad_rms_min=400)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session` | `qi.Session` | — | Active session |
| `timeout_sec` | `float` | `15` | Max wait in `listen()` before returning `""` |
| `vad_rms_min` | `int` | `400` | Voice activity threshold — lower = more sensitive |

---

### `register_and_subscribe() → None`

Start listening. Call once before the first `listen()`.

```python
stt = SpeechToText(session)
stt.register_and_subscribe()
```

---

### `listen() → str`

Block until the user finishes speaking (VAD silence detection) or
*timeout_sec* expires. Returns the transcribed text, or `""` on timeout.

```python
text = stt.listen()
if text:
    print("User said:", text)
else:
    print("No speech detected.")
```

The function **resets internally** between calls, so you can call it in a loop
without calling `register_and_subscribe()` again:

```python
for _ in range(3):
    tts.speak("Say something.")
    text = stt.listen()
    if text:
        break
```

---

### `unsubscribe() → None`

Stop listening and release the audio service. Call when you are done with STT.

```python
stt.unsubscribe()
```

---

## Notes

- **Language:** Vosk defaults to English. A Swedish model can be dropped into
  `/models/vosk_model/` and selected by changing `config.VOSK_MODEL_PATH`.
- **Noise:** The robot's front microphone picks up its own motors. Keep
  interactions short and wait for movement to stop before listening.
- **Latency:** Vosk transcription runs on CPU and typically takes 0.5–2 s after
  the speaker stops.
- **`vad_rms_min`:** If the robot keeps missing quiet speakers, lower to `200`.
  If it triggers on background noise, raise to `600`.
