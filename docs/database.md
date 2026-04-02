# `database/db.py` — DialogDB

A lightweight SQLite-backed store for logging interaction data (conversation
turns, events, arbitrary key–value pairs) without needing a full database
server.

## Class: `DialogDB`

### Constructor

```python
DialogDB(path="pepper_dialog.db")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `"pepper_dialog.db"` | Path to the SQLite file |

The database file is created automatically if it does not exist.

---

### Context Manager

```python
with DialogDB("my_study.db") as db:
    db.log(speaker="robot", text="Hello!")
# db.close() is called automatically
```

---

### Logging Conversation Turns

#### `log(speaker, text, *, session_id=None, intent=None, slot=None, extra=None) → int`

Store one conversation turn and return its row ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `speaker` | `str` | `"robot"` or `"user"` |
| `text` | `str` | What was said |
| `session_id` | `int \| None` | Link to a session (see `new_session()`) |
| `intent` | `str \| None` | Detected NLU intent |
| `slot` | `dict \| None` | Extracted slots as a dict |
| `extra` | `dict \| None` | Any extra data (stored as JSON) |

```python
db.log("robot", "Hello! How can I help you?")
db.log("user",  text=stt_result, intent="order_food",
       slot={"item": "coffee"}, session_id=sid)
```

---

#### `get_history(limit=50, session_id=None) → list[dict]`

Retrieve the most recent conversation turns.

```python
history = db.get_history(limit=20)
for row in history:
    print(f"[{row['speaker']}] {row['text']}")
```

Each dict contains: `id`, `ts`, `speaker`, `text`, `session_id`, `intent`,
`slot`, `extra`.

---

#### `clear_history(*, session_id=None) → int`

Delete conversation turns. If `session_id` is given, only that session's
turns are deleted. Returns the number of rows deleted.

---

### Sessions

#### `new_session(label=None) → int`

Start a new interaction session and return its ID.

```python
sid = db.new_session(label="Group A — Trial 1")
```

---

#### `end_session(session_id) → None`

Mark a session as finished (stores the end timestamp).

```python
db.end_session(sid)
```

---

#### `get_session(session_id) → list[dict]`

Return all turns belonging to one session.

---

#### `list_sessions() → list[dict]`

Return summary info about all sessions (id, label, start time, end time,
turn count).

---

### Key–Value Store

Useful for saving small configuration or state between runs.

```python
db.save("participant_id", 42)
db.save("last_group", "B")

pid = db.load("participant_id")   # → 42
grp = db.load("last_group")       # → "B"
grp = db.load("missing", default="A")  # → "A" if key not found

db.delete("last_group")
print(db.all_keys())              # → ["participant_id"]
```

---

### Event Log

For discrete events (button presses, user detections, errors):

#### `log_event(event_type, data=None) → int`

```python
db.log_event("user_detected")
db.log_event("tablet_touch", {"x": 0.5, "y": 0.3})
db.log_event("stt_timeout")
```

#### `get_events(event_type=None, limit=100) → list[dict]`

```python
touches = db.get_events("tablet_touch")
```

---

## Full Session Example

```python
from HRI_lab_Pepper.database.db import DialogDB

db = DialogDB("study_data.db")

sid = db.new_session(label="P03 — Trial 2")

db.log("robot", "What would you like to order?", session_id=sid)
db.log("user", user_text, session_id=sid,
       intent=intent, slot=slots)
db.log_event("session_start", {"participant": "P03"})

# ... interaction ...

db.end_session(sid)
db.close()
```
