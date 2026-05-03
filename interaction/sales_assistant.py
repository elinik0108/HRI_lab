import json, time, threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List
from urllib.parse import quote
from pathlib import Path

from .dialogue import Dialogue
from HRI_lab_Pepper.vision.marker_finder import find_marker_bearing
from .parsers import parse_product_type, parse_screen_size

## changes to lower case when called
class State(Enum):
    GREET = auto()
    ASK_PRODUCT = auto()
    LISTEN_PRODUCT = auto()
    ASK_SCREEN = auto()
    NARROW_DOWN = auto()
    INPUT_REGISTER_FAILURE = auto()
    SHOW_LOCATION = auto()
    POINT_AT_PRODUCT = auto()
    DONE = auto()

@dataclass
class SessionContext:
    product_type: Optional[str] = None
    screen: Optional[int] = None
    selected: Optional[object] = None
    events: List[tuple] = field(default_factory=list)
    screen_retries: int = 0

class SalesAssistant:
    '''
    The main class for the Sales Assistant Robot that executes.
    This class takes care of functionalities such as session handling,
    listening to customer, logging events, customer selections etc

    '''

    # TODO 1: a json file that has all lines the robot is saying
    # TODO 2: UX problem: the robot doesn't have any idea if a shoe type is out of stock
    #         How can we make sure the robot is not wasting a customers time by sending the customer
    #         to a location and shoes are not there?´
    # TODO 3:
    MAX_STT_RETRIES = 2

    def __init__(self, tts, stt, tablet, anim, leds, catalog, dashboard_url, on_robot=False, wait_for_tablet=None, url_builder=None, dialogue=None, pointer=None, camera=None, detector=None):
        self.tts, self.stt, self.tablet = tts, stt, tablet
        self.anim, self.leds = anim, leds
        self.catalog = catalog
        self.dashboard_url, self.on_robot = dashboard_url, on_robot
        self.ctx = SessionContext()
        self.state = State.GREET
        self.wait_for_tablet = wait_for_tablet
        self.url_builder = url_builder
        self.dialogue = dialogue or Dialogue()
        self.pointer = pointer
        self.camera = camera
        self.detector = detector

    def run(self):
        while self.state != State.DONE:
            handler = getattr(self, f"_on_{self.state.name.lower()}")
            self.state = handler()
        self.keep_the_current_session()

    def keep_the_current_session(self):
        sessions_dir = Path("database/sessions")
        sessions_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "product_type": self.ctx.product_type,
            "screen":       self.ctx.screen,
            "selected":     self.ctx.selected.id if self.ctx.selected else None,
            "events":       self.ctx.events,
        }
        path = sessions_dir / f"{int(record['timestamp'])}.json"
        path.write_text(json.dumps(record, indent=2, default=str))

    def _listen(self) -> str:
        self.stt.register_and_subscribe()
        try:
            return self.stt.listen() or ""
        finally:
            self.stt.unsubscribe()

    def _log_event(self, kind, payload):
        self.ctx.events.append((kind, payload))

    def _on_say(self, key, **kwargs):
        self.tts.speak(self.dialogue.get(key, **kwargs))

    def _on_greet(self):
        self.anim.run_async("animations/Stand/Gestures/Hey_1")
        self._on_say("greet")
        return State.ASK_PRODUCT

    def _on_ask_product(self):
        types = ", ".join(self.catalog.types())
        self._on_say("ask_product", types=types)
        return State.LISTEN_PRODUCT

    def _on_listen_product(self):
        for attempt in range(self.MAX_STT_RETRIES + 1):
            transcript = self._listen()
            self._log_event("stt_product", transcript)
            product_type = parse_product_type(transcript)
            if product_type:
                self.ctx.product_type = product_type
                self._on_say("product_confirmed", product_type=product_type)
                return State.ASK_SCREEN
            if attempt < self.MAX_STT_RETRIES:
                self._on_say("stt_retry")
        self._on_say("stt_failed_fallback")
        return State.INPUT_REGISTER_FAILURE

    def _on_ask_screen(self):
        self._on_say("ask_screen")
        transcript = self._listen()
        self._log_event("stt_screen", transcript)
        self.ctx.screen = parse_screen_size(transcript)
        return State.NARROW_DOWN


    def _on_narrow_down(self):
        candidates = self.catalog.filter(
            product_type=self.ctx.product_type,
            screen=self.ctx.screen,
        )
        if len(candidates) == 1:
            self.ctx.selected = candidates[0]
            return State.SHOW_LOCATION
        if len(candidates) == 0:
            without_screen = self.catalog.filter(product_type=self.ctx.product_type)
            if without_screen and self.ctx.screen is not None and self.ctx.screen_retries < 1:
                self.ctx.screen_retries += 1
                available = sorted({p.screen for p in without_screen})
                self._on_say("screen_unavailable",
                            asked=self.ctx.screen,
                            available=", ".join(str(s) for s in available))
                self._log_event("screen_unavailable",
                                {"asked": self.ctx.screen, "available": available})
                self.ctx.screen = None
                return State.ASK_SCREEN
            self._on_say("no_match")
        else:
            self._on_say("multiple_matches", count=len(candidates))
        return State.INPUT_REGISTER_FAILURE


    def _on_input_register_failure(self):
        candidates = self.catalog.filter(
            product_type=self.ctx.product_type,
            screen=self.ctx.screen,
        )
        if not candidates:
            candidates = self.catalog.filter(product_type=self.ctx.product_type)
        if not candidates:
            candidates = self.catalog.all()

        items = [
            {"id": p.id, "type": p.type, "screen": p.screen, "price": p.price}
            for p in candidates
        ]
        params = (
            f"title=Pick+your+laptop"
            f"&subtitle=Tap+a+card"
            f"&items={quote(json.dumps(items))}"
        )
        url = self.url_builder("product_picker.html", params)
        self.tablet.show_webview(url)

        choice = self.wait_for_tablet(timeout=60.0) if self.wait_for_tablet else {}
        self._log_event("tablet_pick", choice)

        product_id = choice.get("value") if choice else None
        self.ctx.selected = self.catalog.by_id(product_id) if product_id else None
        return State.SHOW_LOCATION if self.ctx.selected else State.DONE


    def _on_show_location(self):
        p = self.ctx.selected
        self._on_say("show_location_intro", product_type=p.type)
        self._log_event("shown_location", p.id)
        return State.POINT_AT_PRODUCT


    def _on_point_at_product(self):
        p = self.ctx.selected
        if not (self.pointer and self.camera and self.detector and p.marker_label):
            self._on_say("show_location_detail", location=p.location)
            self._log_event("point_skipped", "no_pointer_camera_detector_or_marker")
            return State.DONE

        self.pointer.turn_body(p.table_angle_deg)
        time.sleep(0.4)

        refined_bearing = None
        for _ in range(3):
            frame = self.camera.get_frame()
            result = find_marker_bearing(frame, self.detector, p.marker_label)
            if result is not None:
                refined_bearing, conf = result
                self._log_event("vision_hit", {
                    "bearing": refined_bearing, "conf": conf, "marker": p.marker_label,
                })
                break
            time.sleep(0.3)

        if refined_bearing is not None:
            self.pointer.turn_body(refined_bearing)
            time.sleep(0.3)
        else:
            self._log_event("vision_miss", {"id": p.id, "marker": p.marker_label})

        import threading
        arm_thread = threading.Thread(
            target=self.pointer.raise_right_arm,
            kwargs={"hold_seconds": 3.5},
            daemon=True,
        )
        arm_thread.start()
        time.sleep(0.3)
        self._on_say("show_location_pointing", product_type=p.type)
        self._on_say("show_location_detail", location=p.location)
        arm_thread.join(timeout=8.0)

        self._log_event("pointed", p.id)
        return State.DONE

