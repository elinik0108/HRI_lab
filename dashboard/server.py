#!/usr/bin/env python
# =============================================================================
#   HRI_lab_Pepper — Dashboard server
# =============================================================================
"""
FastAPI web server that drives the developer dashboard and serves tablet pages.

Run directly:
    python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559
    → open http://localhost:8080

Tablet pages are served at:
    http://localhost:8080/tablet/welcome.html?title=Hello&message=How+can+I+help?
    http://localhost:8080/tablet/menu.html?title=Choose&items=Option+1,Option+2
    etc.
"""

import argparse
import asyncio
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import socket

import cv2
import numpy as np
import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Add repo root to sys.path so this module works when run directly
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from HRI_lab_Pepper.session import PepperSession
from HRI_lab_Pepper.vision.camera import PepperCamera
from HRI_lab_Pepper.vision.human_detection import HumanDetector
from HRI_lab_Pepper.vision.object_detection import ObjectDetector
from HRI_lab_Pepper.speech.stt import SpeechToText
from HRI_lab_Pepper.speech.tts import TextToSpeech
from HRI_lab_Pepper.motion.posture import RobotPosture
from HRI_lab_Pepper.motion.tracker import RobotTracker
from HRI_lab_Pepper.motion.leds import RobotLEDs
from HRI_lab_Pepper.interaction.awareness import BasicAwareness
from HRI_lab_Pepper.interaction.touch import TouchSensor

_STATIC_DIR = Path(__file__).parent / "static"

# Robot fixed internal IP seen by the tablet over the dedicated WiFi bridge.
# Pages served from here load without crossing external WiFi → far more reliable.
_TABLET_ROBOT_BASE = "http://198.18.0.1/apps/tablet"

app = FastAPI(title="Pepper Student Dashboard")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Allow cross-origin requests from the tablet (served at 198.18.0.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Shared state ──────────────────────────────────────────────────────────────
_latest_frame = None
_frame_lock   = threading.Lock()

connected_ws: set = set()
_server_loop      = None

pipeline_flags = {"human_detection": True, "stt": False, "object_detection": False}
_flags_lock = threading.Lock()

command_queue: list = []
_cmd_lock = threading.Lock()

stop_event = threading.Event()

_touch_state: dict = {}

_robot_status: dict = {
    "battery_pct": -1,
    "temp_status":  0,    # 0 = OK, 1 = warm, 2 = hot
    "overheating":  False,
}
_robot_status_lock = threading.Lock()
_dashboard_base_url = "http://localhost:8080"
_tablet_deployed: bool = False   # True once pages are SFTPed to the robot

_system_metrics: dict = {
    "cpu_pct": 0.0, "ram_used_gb": 0.0, "ram_total_gb": 0.0,
    "cam_fps": 0.0, "cam_req_fps": 0.0, "resolution": "-",
}
_metrics_lock = threading.Lock()

# Tablet inputs (button presses from tablet pages)
_tablet_inputs: list = []
_tablet_lock = threading.Lock()

# Last STT transcript (shown as overlay on the camera feed)
_stt_result:    str   = ""
_stt_result_ts: float = 0.0
_stt_lock = threading.Lock()
_STT_OVERLAY_SEC = 8.0   # seconds to keep the transcript visible


# ── WebSocket broadcaster ─────────────────────────────────────────────────────

async def _broadcast(event: str, payload: dict):
    msg = json.dumps({"type": event, "payload": payload})
    dead = set()
    for ws in connected_ws:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    connected_ws.difference_update(dead)


def broadcast(event: str, payload: dict):
    if _server_loop and not _server_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(event, payload), _server_loop)


# ── Stdout → WebSocket proxy ─────────────────────────────────────────────────

_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class _StdoutProxy:
    def __init__(self, orig):
        self._orig = orig

    def write(self, msg):
        self._orig.write(msg)
        clean = _ANSI_RE.sub('', msg).strip()
        if clean:
            try:
                broadcast("log", {"text": clean})
            except Exception:
                pass

    def flush(self):
        self._orig.flush()


# ═════════════════════════════════════════════════════════════════════════════
#  FastAPI routes
# ═════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def _startup():
    global _server_loop
    _server_loop = asyncio.get_running_loop()
    sys.stdout = _StdoutProxy(sys.stdout)


@app.get("/")
async def _index():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/tablet/{page:path}")
async def _tablet_page(page: str):
    """Serve tablet HTML pages directly (e.g. /tablet/welcome.html)."""
    target = (_STATIC_DIR / "tablet" / page).resolve()
    # Safety: prevent path traversal
    if not str(target).startswith(str((_STATIC_DIR / "tablet").resolve())):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": f"page '{page}' not found"}, status_code=404)
    return FileResponse(target)


@app.websocket("/ws")
async def _ws_main(ws: WebSocket):
    await ws.accept()
    connected_ws.add(ws)
    try:
        while True:
            await asyncio.sleep(0.1)
    except (WebSocketDisconnect, Exception):
        connected_ws.discard(ws)


@app.get("/video_feed")
async def _video_feed():
    def _gen():
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Waiting for camera...", (120, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        while True:
            with _frame_lock:
                f = _latest_frame
            img = f if f is not None else blank
            ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ok:
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n'
            time.sleep(1 / 30.0)
    return StreamingResponse(_gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/toggle")
async def _toggle(body: dict):
    name    = body.get("pipeline", "")
    enabled = bool(body.get("enabled", False))
    with _flags_lock:
        if name in pipeline_flags:
            pipeline_flags[name] = enabled
            print(f"[CORE] '{name}' → {'ON' if enabled else 'OFF'}")
    return JSONResponse({"ok": True})


@app.post("/api/command")
async def _command(body: dict):
    with _cmd_lock:
        command_queue.append(body)
    return JSONResponse({"ok": True})


@app.post("/api/tablet_input")
async def _tablet_input(body: dict):
    """
    Called by tablet HTML pages when the user taps a button.

    The robot loop can poll this with :func:`get_tablet_input`.
    """
    entry = {**body, "ts": time.time()}
    with _tablet_lock:
        _tablet_inputs.append(entry)
    broadcast("tablet_input", entry)
    return JSONResponse({"ok": True})


@app.get("/api/tablet_input")
async def _get_tablet_input():
    """
    Return the most recent tablet input (or empty dict if none).

    Students can poll this, or listen for ``tablet_input`` WebSocket events.
    """
    with _tablet_lock:
        inp = dict(_tablet_inputs[-1]) if _tablet_inputs else {}
    return JSONResponse(inp)


@app.post("/api/shutdown")
async def _shutdown():
    print("[CORE] Shutdown requested from dashboard.")
    stop_event.set()

    def _exit():
        time.sleep(2.5)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()
    return JSONResponse({"ok": True})


@app.get("/api/status")
async def _status():
    with _flags_lock:
        flags = dict(pipeline_flags)
    with _metrics_lock:
        metrics = dict(_system_metrics)
    with _robot_status_lock:
        robot = dict(_robot_status)
    return JSONResponse({"flags": flags, "metrics": metrics, "robot": robot})


@app.get("/api/robot_status")
async def _robot_status_ep():
    with _robot_status_lock:
        return JSONResponse(dict(_robot_status))


@app.get("/api/db/recent")
async def _db_recent(n: int = 50):
    try:
        from HRI_lab_Pepper.database import DialogDB
        db   = DialogDB()
        rows = db.get_history(n=n)
        db.close()
        return JSONResponse({"rows": rows, "count": len(rows)})
    except Exception as exc:
        return JSONResponse({"rows": [], "error": str(exc)})


# ── Public helper for robot code ──────────────────────────────────────────────

def get_tablet_input(consume: bool = True) -> dict:
    """
    Return the latest input received from a tablet page button press.

    Parameters
    ----------
    consume : bool
        If True (default), remove the entry after reading it so the next call
        returns the *next new* input. Set to False to just peek.

    Returns
    -------
    dict
        The last button press, e.g. ``{"action": "choice", "value": "Option 1"}``,
        or an empty dict if no input is waiting.

    Example
    -------
    >>> inp = get_tablet_input()
    >>> if inp:
    ...     print("User tapped:", inp.get("value"))
    """
    with _tablet_lock:
        if not _tablet_inputs:
            return {}
        if consume:
            return _tablet_inputs.pop()
        return dict(_tablet_inputs[-1])


# ═════════════════════════════════════════════════════════════════════════════
#  Background metric/touch loops
# ═════════════════════════════════════════════════════════════════════════════

def _metrics_loop():
    psutil.cpu_percent()          # prime the counter
    while not stop_event.is_set():
        time.sleep(1.0)
        vm  = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        with _metrics_lock:
            m = dict(_system_metrics)
        m["cpu_pct"]      = cpu
        m["ram_used_gb"]  = vm.used  / 1e9
        m["ram_total_gb"] = vm.total / 1e9
        broadcast("metrics", m)


def _touch_loop():
    while not stop_event.is_set():
        time.sleep(0.08)
        broadcast("touch", _touch_state)


# ═════════════════════════════════════════════════════════════════════════════
#  Tablet page deployment (SFTP to robot's built-in web server)
# ═════════════════════════════════════════════════════════════════════════════

def _deploy_tablet_pages(robot_ip: str, dash_url: str) -> bool:
    """
    Copy tablet HTML pages to the robot at:
        ~/.local/share/PackageManager/apps/tablet/html/

    The robot's built-in web server then serves them at:
        http://198.18.0.1/apps/tablet/<page>

    The tablet loads those pages over the **internal** robot↔tablet WiFi bridge
    (fixed IP 198.18.0.1), so the request never crosses external WiFi.
    This is the primary fix for intermittent tablet display failures.

    ``menu.html``'s callback URL is patched from the relative
    ``/api/tablet_input`` to the absolute ``<dash_url>/api/tablet_input``
    so it still reaches the laptop dashboard server across the LAN.

    Returns True if deployment succeeded, False on any error.
    """
    try:
        import paramiko  # noqa: PLC0415
    except ImportError:
        print("[TABLET] paramiko not installed — pages will be served from the laptop.")
        print("[TABLET]   Install with:  pip install paramiko")
        print("[TABLET]   Then re-run the dashboard to enable robot-side serving.")
        return False

    tablet_dir  = _STATIC_DIR / "tablet"
    remote_base = ".local/share/PackageManager/apps/tablet/html"

    # Pepper's SSH server only allows keyboard-interactive auth (not plain
    # password auth), so we use paramiko.Transport directly instead of
    # SSHClient.connect(password=...) which tries the wrong auth method.
    transport = None
    sftp      = None
    try:
        transport = paramiko.Transport((robot_ip, 22))
        transport.connect()

        def _ki_handler(title, instructions, prompt_list):
            # For each prompt (usually just "Password:"), return "nao"
            return ["nao" for _ in prompt_list]

        transport.auth_interactive("nao", _ki_handler)
        sftp = paramiko.SFTPClient.from_transport(transport)
    except Exception as exc:
        print(f"[TABLET] SSH connect failed ({exc}) — using laptop URLs (less reliable).")
        if transport:
            try:
                transport.close()
            except Exception:
                pass
        return False

    try:
        # Ensure remote directory exists
        _sftp_makedirs(sftp, remote_base)

        for f in sorted(tablet_dir.iterdir()):
            if not f.is_file():
                continue
            data = f.read_bytes()
            if f.name == "menu.html":
                # Patch relative callback URL so it reaches the laptop server
                data = data.replace(
                    b"fetch('/api/tablet_input'",
                    f"fetch('{dash_url}/api/tablet_input'".encode(),
                )
            sftp.putfo(io.BytesIO(data), f"{remote_base}/{f.name}")
            print(f"[TABLET]   deployed {f.name}")

        sftp.close()
        transport.close()
        print(f"[TABLET] All pages deployed → http://198.18.0.1/apps/tablet/")
        return True

    except Exception as exc:
        print(f"[TABLET] SFTP deploy failed ({exc}) — using laptop URLs.")
        try:
            sftp.close()
        except Exception:
            pass
        try:
            transport.close()
        except Exception:
            pass
        return False


def _sftp_makedirs(sftp, remote_path: str) -> None:
    """Recursively create directories on the SFTP server (like `mkdir -p`)."""
    parts = remote_path.replace("\\", "/").split("/")
    path  = ""
    for part in parts:
        if not part:
            continue
        path = f"{path}/{part}" if path else part
        try:
            sftp.stat(path)
        except FileNotFoundError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass  # concurrent creation or already exists


# ═════════════════════════════════════════════════════════════════════════════
#  Robot main loop
# ═════════════════════════════════════════════════════════════════════════════

def robot_loop(args):
    global _latest_frame, _touch_state, _dashboard_base_url
    global _stt_result, _stt_result_ts

    print("[INIT] Connecting to Pepper ...")
    session = PepperSession.connect(args.url)

    # Detect our LAN IP as seen from the robot, for tablet webview URLs
    _robot_host = args.url.split("://")[-1].split(":")[0]
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect((_robot_host, 9559))
        _local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _local_ip = "localhost"
    _dashboard_base_url = f"http://{_local_ip}:{args.port}"
    print(f"[INIT] Dashboard URL (for tablet): {_dashboard_base_url}")

    print("[INIT] Loading modules ...")
    cam         = PepperCamera(session)
    humans      = HumanDetector()
    objects     = ObjectDetector()
    stt         = SpeechToText(session)
    tts         = TextToSpeech(session)
    posture     = RobotPosture(session)
    tracker     = RobotTracker(session)
    leds        = RobotLEDs(session)
    awareness   = BasicAwareness(session)
    touch       = TouchSensor(session)
    from HRI_lab_Pepper.interaction.tablet import TabletService
    tablet_svc  = TabletService(session)
    _al_life    = session.service("ALAutonomousLife")

    _al_motion  = session.service("ALMotion")
    _al_battery = session.service("ALBattery")
    _al_btemp   = session.service("ALBodyTemperature")
    print("[INIT] All modules ready.")

    # Deploy tablet pages to the robot so the tablet loads them from
    # 198.18.0.1 (internal bridge) instead of the laptop (external WiFi).
    global _tablet_deployed
    _tablet_deployed = _deploy_tablet_pages(_robot_host, _dashboard_base_url)

    PepperSession.disable_autonomous_life()
    posture.stand_init()
    awareness.start()
    cam.start()

    stt_active   = False
    _status_tick = 0

    # Continuous STT loop — runs in a background thread while STT is active.
    # Keeps calling stt.listen() so every utterance is captured and surfaced
    # as an overlay on the camera feed.
    def _stt_listen_loop() -> None:
        global _stt_result, _stt_result_ts
        while True:
            with _flags_lock:
                still_on = pipeline_flags["stt"]
            if not still_on:
                break
            text = stt.listen()   # blocks up to stt._timeout seconds
            if text:
                with _stt_lock:
                    _stt_result    = text
                    _stt_result_ts = time.time()

    print("[CORE] Entering main loop ...")
    try:
        while not stop_event.is_set():

            # ── Commands from dashboard ──
            with _cmd_lock:
                cmds = list(command_queue)
                command_queue.clear()

            for c in cmds:
                ctype = c.get("cmd", "")
                cargs = c.get("args", {})

                if ctype == "say":
                    text = cargs.get("text", "")
                    if text:
                        print(f"[TTS] Saying: {text}")
                        threading.Thread(
                            target=tts.speak, args=(text,), daemon=True
                        ).start()

                elif ctype == "posture":
                    name = cargs.get("name", "StandInit")
                    print(f"[CORE] Posture → {name}")
                    threading.Thread(
                        target=posture.go_to, args=(name,), daemon=True
                    ).start()

                elif ctype == "led":
                    preset = cargs.get("preset", "off")
                    print(f"[CORE] LED preset → {preset}")
                    fn = getattr(leds, preset, None)
                    if callable(fn):
                        threading.Thread(target=fn, daemon=True).start()

                elif ctype == "awareness":
                    if cargs.get("on", True):
                        awareness.start()
                    else:
                        awareness.stop()

                elif ctype == "autonomous_ability":
                    ability = cargs.get("ability", "")
                    on      = bool(cargs.get("on", False))
                    if ability:
                        try:
                            _al_life.setAutonomousAbilityEnabled(ability, on)
                            print(f"[CORE] Ability '{ability}' → {'ON' if on else 'OFF'}")
                        except Exception as exc:
                            print(f"[CORE] Could not set ability '{ability}': {exc}")

                elif ctype == "breathing":
                    on = bool(cargs.get("on", False))
                    for _chain in ["Body", "Head", "LArm", "RArm"]:
                        try:
                            _al_motion.setBreathEnabled(_chain, on)
                        except Exception:
                            pass
                    print(f"[CORE] Breathing → {'ON' if on else 'OFF'}")

                elif ctype == "show_tablet":
                    page   = cargs.get("page", "")
                    params = cargs.get("params", "")
                    if page:
                        # Use robot-side URL when deployed (internal bridge, reliable)
                        # Fall back to laptop URL otherwise (external WiFi, flaky)
                        if _tablet_deployed:
                            _url = f"{_TABLET_ROBOT_BASE}/{page}"
                        else:
                            _url = f"{_dashboard_base_url}/tablet/{page}"
                        if params:
                            _url += f"?{params}"
                        # Run in a daemon thread: show_webview retries up to 3×
                        # which would stall the robot loop if called inline.
                        threading.Thread(
                            target=tablet_svc.show_webview,
                            args=(_url,),
                            daemon=True,
                        ).start()
                        print(f"[TABLET] → {page}")

                elif ctype == "tablet_hide":
                    try:
                        tablet_svc.hide()
                        print("[TABLET] Hidden")
                    except Exception as exc:
                        print(f"[TABLET] Hide error: {exc}")

            # ── Camera frame ──
            frame = cam.get_frame()
            stats = cam.get_stats()
            with _metrics_lock:
                _system_metrics["cam_fps"]     = stats["actual_fps"]
                _system_metrics["cam_req_fps"] = stats["requested_fps"]
                _system_metrics["resolution"]  = stats["resolution"]

            # ── Human detection ──
            with _flags_lock:
                do_human = pipeline_flags["human_detection"]
                do_stt   = pipeline_flags["stt"]
                do_obj   = pipeline_flags["object_detection"]

            if frame is not None:
                display = frame.copy()
                if do_human:
                    people = humans.detect(frame)
                    for p in people:
                        x1, y1, x2, y2 = p["bbox"]
                        conf = p["confidence"]
                        label = f"person {conf:.0%}"
                        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 128), 2)
                        (tw, th), _ = cv2.getTextSize(
                            label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        cv2.rectangle(
                            display, (x1, y1 - th - 10), (x1 + tw + 8, y1),
                            (0, 255, 128), -1)
                        cv2.putText(
                            display, label, (x1 + 4, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                if do_obj:
                    detected_objects = objects.detect(frame)
                    for obj in detected_objects:
                        x1, y1, x2, y2 = obj["bbox"]
                        conf  = obj["confidence"]
                        cid   = obj["class_id"]
                        lbl   = f'{obj["label"]} {conf:.0%}'
                        # Deterministic colour per class
                        np.random.seed(cid + 42)
                        clr = tuple(int(c) for c in np.random.randint(80, 230, 3).tolist())
                        cv2.rectangle(display, (x1, y1), (x2, y2), clr, 2)
                        (tw, th), _ = cv2.getTextSize(
                            lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                        cv2.rectangle(
                            display, (x1, y1 - th - 10), (x1 + tw + 8, y1),
                            clr, -1)
                        cv2.putText(
                            display, lbl, (x1 + 4, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                # ── STT transcript overlay ──
                with _stt_lock:
                    _last_text = _stt_result
                    _last_ts   = _stt_result_ts
                if do_stt and _last_text and (time.time() - _last_ts) < _STT_OVERLAY_SEC:
                    h_img, w_img = display.shape[:2]
                    font       = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.60
                    thickness  = 2
                    text_str   = f"  Human: {_last_text}"
                    (tw, th), _ = cv2.getTextSize(text_str, font, font_scale, thickness)
                    band_h = th + 14
                    # Semi-transparent dark band at the top
                    roi     = display[0:band_h, 0:w_img]
                    overlay = roi.copy()
                    cv2.rectangle(overlay, (0, 0), (w_img, band_h), (20, 20, 20), -1)
                    cv2.addWeighted(overlay, 0.7, roi, 0.3, 0, roi)
                    display[0:band_h, 0:w_img] = roi
                    cv2.putText(display, text_str, (4, th + 6),
                                font, font_scale, (50, 255, 180), thickness)
                with _frame_lock:
                    _latest_frame = display

            # ── STT management ──
            if do_stt and not stt_active:
                stt.register_and_subscribe()
                stt_active = True
                threading.Thread(target=_stt_listen_loop, daemon=True).start()
                print("[CORE] STT started — listening ...")
            elif not do_stt and stt_active:
                stt.unsubscribe()
                stt_active = False
                with _stt_lock:
                    _stt_result    = ""
                    _stt_result_ts = 0.0
                print("[CORE] STT stopped.")

            # ── Touch sensors ──
            try:
                _touch_state = touch.get_all_state()
            except Exception:
                pass

            # ── Robot status poll (battery + temp, every ~5 s) ──
            _status_tick += 1
            if _status_tick % 160 == 0:
                bat, ts = -1, 0
                try:
                    bat = int(_al_battery.getBatteryCharge())
                except Exception:
                    pass
                try:
                    # getTemperatureDiagnosis returns [level, [devices]]
                    # level: 0=NEGLIGIBLE, 1=SERIOUS, 2=CRITICAL
                    diag = _al_btemp.getTemperatureDiagnosis()
                    ts   = int(diag[0])
                except Exception:
                    pass
                with _robot_status_lock:
                    _robot_status["battery_pct"] = bat
                    _robot_status["temp_status"]  = ts
                    _robot_status["overheating"]  = ts >= 2
                broadcast("robot_status", dict(_robot_status))
                if bat >= 0 and ts >= 1:
                    _lbl = ["OK", "warm", "hot"][min(ts, 2)]
                    print(f"[CORE] ⚠ Battery {bat}%  Temp: {_lbl}")

            time.sleep(0.03)

    finally:
        print("[CORE] Cleaning up ...")
        for fn in (cam.stop, awareness.stop, tracker.stop, leds.off):
            try:
                fn()
            except Exception:
                pass
        if stt_active:
            try:
                stt.unsubscribe()
            except Exception:
                pass
        try:
            posture.stand(speed=0.5)
        except Exception:
            pass
        PepperSession.disconnect()
        print("[CORE] Done.")


# ═════════════════════════════════════════════════════════════════════════════
#  Public entry points
# ═════════════════════════════════════════════════════════════════════════════

def run(url: str = "tcp://172.18.48.50:9559", port: int = 8080) -> None:
    """
    Start the dashboard server programmatically.

    Parameters
    ----------
    url : str
        Robot connection URL.
    port : int
        Local HTTP port (default 8080).
    """

    class _Args:
        pass

    a = _Args()
    a.url  = url
    a.port = port

    threading.Thread(target=robot_loop,    args=(a,), daemon=True).start()
    threading.Thread(target=_metrics_loop,             daemon=True).start()
    threading.Thread(target=_touch_loop,               daemon=True).start()

    print("=" * 54)
    print(f"  PEPPER DASHBOARD  →  http://localhost:{port}")
    print(f"  Tablet pages      →  http://localhost:{port}/tablet/")
    print("=" * 54)

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def _cli() -> None:
    """Argument-parser entry point used by ``__main__.py``."""
    parser = argparse.ArgumentParser(description="Pepper Student Dashboard")
    parser.add_argument(
        "--url",  default="tcp://172.18.48.50:9559",
        help="Robot connection URL (default: tcp://172.18.48.50:9559)",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Web server port (default: 8080)",
    )
    a = parser.parse_args()
    run(url=a.url, port=a.port)
