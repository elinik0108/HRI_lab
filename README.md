# HRI Pepper Sales Assistant

A Pepper-based sales assistant for a shoe shop. Built for the Human Robot Interaction course, 2026.

## What it does
Pepper waits for a customer to approach, asks what shoes they're looking for via
speech, falls back to a tablet picker if speech fails, then turns toward the
shelf and points at the selected item using YOLO-based marker detection.

## State machine
GREET → ASK_PRODUCT → LISTEN_PRODUCT → ASK_COLOR → ASK_SIZE → NARROW_DOWN →
{ SHOW_LOCATION → POINT_AT_SHOE → DONE }
                or
              { INPUT_REGISTER_FAILURE → SHOW_LOCATION → POINT_AT_SHOE → DONE }

(see interaction/sales_assistant.py for the full state graph)

## How to run

### Real robot
```bash
python dashboard/__main__.py --url tcp://ROBOT_IP:9559
```

### Dry-run (no robot needed)
```bash
python dashboard/__main__.py --dry-run
```

## How it's structured
- `interaction/sales_assistant.py` — the state machine
- `interaction/dialogue.json` — all robot speech (edit this to change phrasing)
- `interaction/parsers.py` — turns STT output into structured slots
- `models/shoe.py` + `database/shoes.json` — the shoe catalog
- `vision/marker_finder.py` — YOLO-based shelf marker detection
- `motion/pointing.py` — body turn + arm raise
- `dashboard/static/tablet/shoe_picker.html` — fallback picker UI
- `demos/sales_assistant_robot.py` — entry point that wires everything

## Adding a new shoe
1. Add an entry to `database/shoes.json` with id, type, color, sizes, price,
   location, marker_label (a COCO class name), and table_angle_deg.
2. Place a physical object matching `marker_label` in front of Pepper at
   roughly `table_angle_deg` from straight-ahead.
3. Restart the demo.

## Known limitations
- Vosk STT is noisy; the system retries once and falls back to tablet input.
- YOLO recognises only COCO classes, so shoe markers must be everyday objects
  (cup, bottle, book, etc.).
- Pepper's per-finger control isn't available, so "pointing" uses a near-closed
  hand on an extended arm.

## Team
- 