import json, time, threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List
from urllib.parse import quote
from pathlib import Path

from .parsers import parse_shoe_type, parse_color, parse_size
from .dialogue import Dialogue
from HRI_lab_Pepper.vision.marker_finder import find_marker_bearing

## changes to lower case when called
class State(Enum):
    GREET = auto()
    ASK_PRODUCT = auto()
    LISTEN_PRODUCT  = auto()
    ASK_COLOR = auto()
    ASK_SIZE = auto()
    NARROW_DOWN = auto()
    INPUT_REGISTER_FAILURE = auto()
    SHOW_LOCATION = auto()
    POINT_AT_SHOE = auto()
    DONE = auto()


@dataclass
class SessionContext:
    shoe_type: Optional[str] = None
    color: Optional[str] = None
    size: Optional[int] = None
    selected: Optional[object] = None
    events: List[tuple] = field(default_factory=list)
    size_retries: int = 0

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
        '''
        Takes care of session handling, creates a session in database/sessions
        '''

        sessions_dir = Path("database/sessions")
        sessions_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "shoe_type": self.ctx.shoe_type,
            "color": self.ctx.color,
            "size": self.ctx.size,
            "selected": self.ctx.selected.id if self.ctx.selected else None,
            "events": self.ctx.events,
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
        for atmpt in range(self.MAX_STT_RETRIES + 1):
            transcript = self._listen()
            self._log_event("stt_product", transcript)
            shoe_type = parse_shoe_type(transcript)
            if shoe_type:
                self.ctx.shoe_type = shoe_type
                self._on_say("product_confirmed", shoe_type=shoe_type)
                return State.ASK_COLOR
            if atmpt < self.MAX_STT_RETRIES:
                self._on_say("stt_retry")
        self._on_say("stt_failed_fallback")
        return State.INPUT_REGISTER_FAILURE

    ## color
    def _on_ask_color(self):
        self._on_say("ask_color")
        transcript = self._listen()
        self._log_event("stt_color", transcript)
        self.ctx.color = parse_color(transcript)
        return State.ASK_SIZE
    ## size
    def _on_ask_size(self):
        self._on_say("ask_size")
        transcript = self._listen()
        self._log_event("stt_size", transcript)
        self.ctx.size = parse_size(transcript)
        return State.NARROW_DOWN

    ## search for the cutstomer input
    def _on_narrow_down(self):
        candidates = self.catalog.filter(
            shoe_type=self.ctx.shoe_type,
            color=self.ctx.color,
            size=self.ctx.size,
        )
        if len(candidates) == 1:
            self.ctx.selected = candidates[0]
            return State.SHOW_LOCATION
        if len(candidates) == 0:
            without_size = self.catalog.filter(
                shoe_type=self.ctx.shoe_type,
                color=self.ctx.color,
            )
            if without_size and self.ctx.size is not None and self.ctx.size_retries < 1:
                self.ctx.size_retries += 1
                available = sorted({sz for s in without_size for sz in s.sizes})
                self._on_say("size_unavailable",
                        asked=self.ctx.size,
                        available=", ".join(str(sz) for sz in available))
                self._log_event("size_unavailable",
                                {"asked": self.ctx.size, "available": available})
                self.ctx.size = None
                return State.ASK_SIZE
            self._on_say("no_match")
        else:
            self._on_say("multiple_matches", count=len(candidates))
        return State.INPUT_REGISTER_FAILURE

        # if len(candidates) == 0:
        #     self.tts.speak("I couldn't find an exact match. Let me show you what's close.")
        # else:
        #     self.tts.speak(f"I found {len(candidates)} options. Please pick one on the tablet.")
        # return State.INPUT_REGISTER_FAILURE



    def _on_input_register_failure(self):

        candidates = self.catalog.filter(
            shoe_type=self.ctx.shoe_type,
            color=self.ctx.color,
            size=self.ctx.size,
        )
        if not candidates:
            candidates = self.catalog.filter(shoe_type=self.ctx.shoe_type, color=self.ctx.color,)

        if not candidates:
            candidates = self.catalog.filter(shoe_type=self.ctx.shoe_type)

        if not candidates:
            candidates = self.catalog.all()

        # Build the picker URL
        items = [
            {"id": s.id, "type": s.type, "color": s.color,
            "price": s.price, "sizes": s.sizes}
            for s in candidates
        ]
        params = (
            f"title=Pick+your+shoe"
            f"&subtitle=Tap+a+card"
            f"&items={quote(json.dumps(items))}"
        )
        url = self.url_builder("shoe_picker.html", params)
        self.tablet.show_webview(url)

        # Wait for the tap
        choice = self.wait_for_tablet(timeout=60.0) if self.wait_for_tablet else {}
        self._log_event("tablet_pick", choice)

        shoe_id = choice.get("value") if choice else None
        self.ctx.selected = self.catalog.by_id(shoe_id) if shoe_id else None
        print(f"[DEBUG _on_input_register_failure] shoe_id={shoe_id!r} selected={self.ctx.selected!r}")
        return State.SHOW_LOCATION if self.ctx.selected else State.DONE

    def _on_show_location(self):
        s = self.ctx.selected
        self._on_say("show_location_intro", color=s.color, type=s.type)
        self._log_event("shown_location", s.id)
        return State.POINT_AT_SHOE


    def _on_point_at_shoe(self):
        s = self.ctx.selected
        if not (self.pointer and self.camera and self.detector and s.marker_label):
            ##fallback if it goes wrong
            self._on_say("show_location_detail", location=s.location)
            self._log_event("point_skipped", "no_pointer_camera_detector_or_marker")
            return State.DONE

        self.pointer.turn_body(s.table_angle_deg)
        time.sleep(0.4)

        refined_bearing = None
        for _ in range(3):
            frame = self.camera.get_frame()
            result = find_marker_bearing(frame, self.detector, s.marker_label)
            if result is not None:
                refined_bearing, conf = result
                self._log_event("vision_hit", {
                    "bearing": refined_bearing, "conf": conf, "marker": s.marker_label,
                })
                break
            time.sleep(0.3)

        if refined_bearing is not None:
            print(f"[POINTING] marker={s.marker_label!r} bearing={refined_bearing:.1f} deg conf={conf:.2f}")
            self.pointer.turn_body(refined_bearing)
            time.sleep(0.3)
        else:
            print(f"[POINTING] marker={s.marker_label!r} not found. Using fixed angle only")
            self._log_event("vision_miss", {"id": s.id, "marker": s.marker_label})


        arm_thread = threading.Thread(
            target=self.pointer.raise_right_arm,
            kwargs={"hold_seconds": 3.5},
            daemon=True,
        )
        arm_thread.start()

        time.sleep(0.3)
        self._on_say("show_location_pointing", color=s.color, type=s.type)

        self._on_say("show_location_detail", location=s.location)

        # Wait for the arm to come down
        arm_thread.join(timeout=8.0)

        self._log_event("pointed", s.id)
        return State.DONE