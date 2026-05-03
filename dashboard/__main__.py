#!/usr/bin/env python
# =============================================================================
#  HRI_lab_Pepper — Menu Demo Scenario
# =============================================================================
"""
Multi-modal demo that chains:
  1. Person detection — Pepper waits until someone stands in front of it.
  2. Greeting        — Pepper greets the person with speech + animation.
  3. STT query       — Pepper asks for confirmation ("ready?") and checks STT.
  4. Tablet menu     — Pepper shows a 4-option image-card menu on the tablet.
  5. Reaction        — Pepper reacts differently to each card selection:
       • Weather → speaks a weather forecast and shows info page
       • Joke    → tells a joke with an enthusiastic animation
       • News    → reads a mock headline
       • Dance   → runs a dance animation

Usage
-----
    # Start the dashboard first in another terminal:
    python -m HRI_lab_Pepper.dashboard --url tcp://ROBOT_IP:9559

    # Then run this script:
    python demos/menu_demo.py --url tcp://ROBOT_IP:9559 [--port 8080]

    # Or run without a live robot (dry-run mode):
    python demos/menu_demo.py --dry-run
"""

import argparse
import queue
import time
import sys
import threading
import json as _json
from pathlib import Path
from HRI_lab_Pepper.interaction.sales_assistant import SalesAssistant
from HRI_lab_Pepper.models.catalog import ShoeCatalog


# ── Robot drivers ──────────────────────────────────────────────────────────────
try:
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.speech.tts import TextToSpeech
    from HRI_lab_Pepper.speech.stt import SpeechToText
    from HRI_lab_Pepper.vision.camera import PepperCamera
    from HRI_lab_Pepper.vision.human_detection import HumanDetector
    from HRI_lab_Pepper.vision.object_detection import ObjectDetector
    from HRI_lab_Pepper.tablet import TabletService, deploy_tablet_pages, TABLET_ROBOT_BASE as _TABLET_ROBOT_BASE
    from HRI_lab_Pepper.interaction.awareness import BasicAwareness
    from HRI_lab_Pepper.motion.posture import RobotPosture
    from HRI_lab_Pepper.motion.leds import RobotLEDs
    from HRI_lab_Pepper.motion.animation_player import AnimationPlayer
    from HRI_lab_Pepper.motion.pointing import Pointer
except ImportError as e:
    print(f"[DEMO] Import error: {e}")
    print("[DEMO] Is the package installed? Run: pip install -e .")
    sys.exit(1)

_TABLET_SRC_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "tablet"


# ──────────────────────────────────────────────────────────────────────────────
#  Scenario content
# ──────────────────────────────────────────────────────────────────────────────

CONFIRM_KEYWORDS = ("yes", "yeah", "yep", "sure", "ready", "ok", "okay", "go")


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[DEMO] {msg}", flush=True)


# ──────────────────────────────────────────────────────────────────────────────
#  Tablet input queue
# ──────────────────────────────────────────────────────────────────────────────

# Single-item queue: ALMemory subscriber puts here; _wait_for_menu_choice reads.
_choice_queue: queue.Queue = queue.Queue()


def _wait_for_person(
    camera: "PepperCamera",
    detector: "HumanDetector",
    timeout: float = 120.0,
    check_interval: float = 0.5,
) -> bool:
    """
    Block until at least one person is detected in the camera frame,
    or *timeout* seconds elapse.

    Returns True if a person was found, False on timeout.
    """
    _log("Waiting for a person to appear…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        frame = camera.get_frame()
        if frame is not None:
            detections = detector.detect(frame)
            if detections:
                _log(f"Person detected! ({len(detections)} detection(s))")
                return True
        time.sleep(check_interval)
    _log("Timeout: no person detected.")
    return False

def _wait_for_no_person(camera, detector, timeout=30.0, check_interval=0.5):
    """Block until the camera sees no one, or timeout."""
    _log("Waiting for the customer to leave…")
    deadline = time.time() + timeout
    consecutive_empty = 0
    while time.time() < deadline:
        frame = camera.get_frame()
        if frame is not None and not detector.detect(frame):
            consecutive_empty += 1
            if consecutive_empty >= 4:
                _log("Customer has left.")
                return True
        else:
            consecutive_empty = 0
        time.sleep(check_interval)
    _log("Timeout waiting for customer to leave, continuing anyway.")
    return False

def _wait_for_confirmation(
    stt: "SpeechToText",
    keywords: tuple = CONFIRM_KEYWORDS,
) -> bool:
    """
    Listen for a yes-like utterance.
    Returns True if a matching keyword was heard.
    """
    _log(f"Listening for confirmation (keywords: {keywords}) …")
    transcript = stt.listen()
    if not transcript:
        _log("No speech heard.")
        return False
    _log(f"Heard: '{transcript}'")
    return any(kw in transcript.lower() for kw in keywords)


def _wait_for_menu_choice(timeout: float = 30.0) -> dict:
    """
    Block until the broker receives a card_choice POST from the tablet,
    or *timeout* seconds elapse.  Returns the payload dict, or {} on timeout.
    """
    _log("Waiting for menu selection on tablet…")
    try:
        data = _choice_queue.get(timeout=timeout)
        _log(f"Menu choice received: {data.get('value', '?')}")
        return data
    except queue.Empty:
        _log("Menu selection timeout.")
        return {}


def _led(leds: object, preset: str) -> None:
    """Dispatch a preset name string to the matching RobotLEDs method."""
    fn = getattr(leds, preset, None) or getattr(leds, "off")
    fn()


def _build_tablet_url(base_url: str, page: str, params: str, on_robot: bool = False) -> str:
    """Build a tablet URL — uses the robot-internal bridge when on_robot=True."""
    if on_robot:
        url = f"{_TABLET_ROBOT_BASE}/{page}"
    else:
        url = f"{base_url}/tablet/{page}"
    if params:
        url += f"?{params}"
    return url


# ──────────────────────────────────────────────────────────────────────────────
#  Dry-run mode  (no real robot)
# ──────────────────────────────────────────────────────────────────────────────

class _FakeTTS:
    def speak(self, text, animated=True): _log(f"[TTS] {text}")
    def set_volume(self, v): pass
    def set_speed(self, s): pass

class _FakeSTT:
    def __init__(self):
        #self._replies = iter(["sneakers", "red", "42"])
        #self._replies = iter(["sneakers", "test", "42"])
        #self._replies = iter(["hmm", "red", "42"])

        self._replies = iter(["sneakers", "red", "50", "49"])
    def register_and_subscribe(self): pass
    def listen(self):
        import time; time.sleep(0.3)
        return next(self._replies, "")
    def unsubscribe(self): pass

class _FakeCamera:
    def get_frame(self):
        import numpy as np
        return np.zeros((240, 320, 3), dtype="uint8")
    def start(self): _log("[CAMERA] Started")
    def stop(self): _log("[CAMERA] Stopped")

class _FakeDetector:
    def detect(self, frame): return [{"bbox": [0, 0, 1, 1], "confidence": 0.9}]

class _FakeObjectDetector:
    def detect(self, frame): return []
    def detect_class(self, frame, label): return []

class _FakePointer:
    def turn_body(self, yaw_deg, speed=0.3):
        _log(f"[POINTER] turn body {yaw_deg:.1f}°")
    def raise_right_arm(self, hold_seconds=4.0):
        _log(f"[POINTER] raise right arm ({hold_seconds}s)")
    def point_toward(self, yaw_deg, hold_seconds=4.0):
        self.turn_body(yaw_deg)
        self.raise_right_arm(hold_seconds)

class _FakeTablet:
    def __init__(self, dashboard_url: str):
        self._dashboard_url = dashboard_url

    def show_webview(self, url):
        _log(f"[TABLET] show: {url}")
        if "shoe_picker" in url:
            def _inject():
                time.sleep(1.0)
                _choice_queue.put({"action": "shoe_choice", "value": "s003", "index": 0})
                _log("[FAKE] Injected shoe_choice: s003")
            threading.Thread(target=_inject, daemon=True).start()

    def hide(self):
        _log("[TABLET] hide")

class _FakeAnim:
    def run_async(self, path): _log(f"[ANIM] {path}")

class _FakePosture:
    def stand(self, speed=None): pass
    def stand_init(self): pass

class _FakeLEDs:
    def happy(self):    _log("[LED] happy")
    def thinking(self): _log("[LED] thinking")
    def sad(self):      _log("[LED] sad")
    def error(self):    _log("[LED] error")
    def off(self):      _log("[LED] off")

class _FakeAwareness:
    def start(self): pass
    def stop(self): pass


# ──────────────────────────────────────────────────────────────────────────────
#  Main scenario
# ──────────────────────────────────────────────────────────────────────────────

def run_scenario(tts, stt, camera, detector, tablet, anim, posture, leds, awareness,
                 pointer, object_detector,
                 dashboard_url, on_robot=False):
    posture.stand()
    camera.start()
    time.sleep(1.0)
    tts.set_volume(40)
    tts.set_speed(90)

    while True:
        if not _wait_for_person(camera, detector, timeout=120.0):
            _log("Nobody showed up. Ending demo.")
            return

        _led(leds, "happy")

        catalog = ShoeCatalog.load("database/shoes.json")
        assistant = SalesAssistant(
            tts=tts, stt=stt, tablet=tablet, anim=anim, leds=leds,
            catalog=catalog,
            pointer=pointer,
            camera=camera,
            detector=object_detector,
            dashboard_url=dashboard_url, on_robot=on_robot,
            wait_for_tablet=_wait_for_menu_choice,
            url_builder=lambda page, params: _build_tablet_url(
                dashboard_url, page, params, on_robot
            ),
        )
        assistant.run()

        tablet.hide()
        _led(leds, "off")
        _wait_for_no_person(camera, detector, timeout=30.0)
        _log("Ready for the next customer.")
# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pepper menu demo scenario")
    parser.add_argument("--url",      default="tcp://172.18.48.50:9559",
                        help="Naoqi URL, e.g. tcp://ROBOT_IP:9559")
    parser.add_argument("--port",     type=int, default=8080,
                        help="Dashboard server port (default: 8080)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Run without a real robot (fake drivers)")
    args = parser.parse_args()

    if args.dry_run:
        _log("=== DRY-RUN MODE (no robot) ===")
        dashboard_url = f"http://localhost:{args.port}"
        on_robot  = False
        tts             = _FakeTTS()
        stt             = _FakeSTT()
        camera          = _FakeCamera()
        detector        = _FakeDetector()
        tablet          = _FakeTablet(dashboard_url)
        anim            = _FakeAnim()
        posture         = _FakePosture()
        leds            = _FakeLEDs()
        awareness       = _FakeAwareness()
        pointer         = _FakePointer()
        object_detector = _FakeObjectDetector()
    else:
        _log(f"Connecting to {args.url} …")
        session   = PepperSession.connect(args.url)
        PepperSession.disable_autonomous_life()
        tts             = TextToSpeech(session)
        stt             = SpeechToText(session)
        camera          = PepperCamera(session)
        detector        = HumanDetector()
        tablet          = TabletService(session)
        anim            = AnimationPlayer(session)
        posture         = RobotPosture(session)
        leds            = RobotLEDs(session)
        awareness       = BasicAwareness(session)
        pointer         = Pointer(session)
        object_detector = ObjectDetector()

        # Derive dashboard URL reachable by the robot's tablet browser.
        _robot_host = args.url.split("://")[-1].split(":")[0]
        import socket as _socket
        try:
            _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            _s.connect((_robot_host, 9559))
            _local_ip = _s.getsockname()[0]
            _s.close()
        except Exception:
            _local_ip = "localhost"
        dashboard_url = f"http://{_local_ip}:{args.port}"
        _log(f"Dashboard URL: {dashboard_url}")

        # Register a qi service 'TabletInput' with a notify() method.
        # The tablet JS calls QiSession → service('TabletInput') → notify(json),
        # routed back through the existing SSH reverse tunnel.
        class _TabletInputSvc:
            def notify(self, json_str):
                try:
                    _choice_queue.put(_json.loads(str(json_str)))
                except Exception:
                    pass

        _tab_svc = _TabletInputSvc()
        session.registerService("TabletInput", _tab_svc)
        _log("Tablet input service ready.")

        # Deploy tablet pages directly to the robot via SSH
        on_robot = deploy_tablet_pages(
            robot_ip=_robot_host,
            src_dir=_TABLET_SRC_DIR,
        )
        if not on_robot:
            _log("Tablet pages not deployed — falling back to laptop URLs.")

    try:
        run_scenario(
            tts=tts,
            stt=stt, 
            camera=camera, 
            detector=detector,
            tablet=tablet, 
            anim=anim, 
            posture=posture, 
            leds=leds,
            awareness=awareness,
            pointer=pointer,
            object_detector=object_detector,
            dashboard_url=dashboard_url, on_robot=on_robot,
        )
    except KeyboardInterrupt:
        _log("Interrupted by user.")
    finally:
        if not args.dry_run:
            _log("Cleaning up …")
            for fn, label in [
                (stt.unsubscribe,          "STT unsubscribe"),
                (camera.stop,              "camera stop"),
                (awareness.stop,           "awareness stop"),
                (leds.off,                 "LEDs off"),
                (tablet.hide,              "tablet hide"),
                (lambda: posture.stand(speed=0.5), "posture stand"),
                # (PepperSession.enable_autonomous_life, "autonomous life restore"),
                (PepperSession.disconnect, "session disconnect"),
            ]:
                try:
                    fn()
                except Exception as exc:
                    _log(f"  [{label}] {exc}")
            _log("Cleanup done.")


if __name__ == "__main__":
    main()
