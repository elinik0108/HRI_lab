from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List
import json
from urllib.parse import quote
import json, time
from pathlib import Path

from .parsers import parse_shoe_type, parse_color, parse_size

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

    def __init__(self, tts, stt, tablet, anim, leds, catalog, dashboard_url, on_robot=False, wait_for_tablet=None, url_builder=None):
        self.tts, self.stt, self.tablet = tts, stt, tablet
        self.anim, self.leds = anim, leds
        self.catalog = catalog
        self.dashboard_url, self.on_robot = dashboard_url, on_robot
        self.ctx = SessionContext()
        self.state = State.GREET
        self.wait_for_tablet = wait_for_tablet
        self.url_builder = url_builder

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

    def _on_greet(self):
        self.anim.run_async("animations/Stand/Gestures/Hey_1")
        self.tts.speak("Hi! I'm Kiwi. I can help you find the right shoes today.")
        return State.ASK_PRODUCT

    def _on_ask_product(self):
        types = ", ".join(self.catalog.types())
        self.tts.speak(f"What kind of shoe are you looking for? " f"For example: {types}.")
        return State.LISTEN_PRODUCT

    def _on_listen_product(self):
        for atmpt in range(self.MAX_STT_RETRIES + 1):
            transcript = self._listen()
            self._log_event("stt_product", transcript)
            shoe_type = parse_shoe_type(transcript)
            if shoe_type:
                self.ctx.shoe_type = shoe_type
                self.tts.speak(f"Got it — {shoe_type}.")
                return State.ASK_COLOR
            if atmpt < self.MAX_STT_RETRIES:
                self.tts.speak("Sorry, I didn't catch that. Could you say it again?")
        self.tts.speak("No worries. Let me show you what we have on the tablet.")
        return State.INPUT_REGISTER_FAILURE

    ## color
    def _on_ask_color(self):
        self.tts.speak("What color would you like?")
        transcript = self._listen()
        self._log_event("stt_color", transcript)
        self.ctx.color = parse_color(transcript)
        return State.ASK_SIZE
    ## size
    def _on_ask_size(self):
        self.tts.speak("And what size?")
        transcript = self._listen()
        self._log_event("stt_size", transcript)
        self.ctx.size = parse_size(transcript)
        return State.NARROW_DOWN

    ## search for the cutstomer input
    def _on_narrow_down(self):
        candidates = self.catalog.filter(shoe_type=self.ctx.shoe_type, color=self.ctx.color, size=self.ctx.size,)
        if len(candidates) == 1:
            self.ctx.selected = candidates[0]
            return State.SHOW_LOCATION

        if len(candidates) == 0:
            without_size = self.catalog.filter(shoe_type=self.ctx.shoe_type, color=self.ctx.color,)

            if without_size and self.ctx.size is not None and self.ctx.size_retries < 1:
                self.ctx.size_retries +=1
                ##sort available sizes
                available = sorted({sz for s in without_size for sz in s.sizes})
                sizes_str = ", ".join(str(sz) for sz in available)
                self.tts.speak(f"Sorry, we don't have size {self.ctx.size} in that style."
                f"We have it in sizes {sizes_str}. What size would you like instead?")
                self._log_event("size_unavailable, asked if the customer wants different size and showed those")
                self.ctx.size = None

                return State.ASK_SIZE

            self.tts.speak("I couldn't find an exact match. Let me show you what's close.")
            return State.INPUT_REGISTER_FAILURE

        self.tts.speak(f"I found {len(candidates)} options. Please pick one on the tablet.")
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
        return State.SHOW_LOCATION if self.ctx.selected else State.DONE

    def _on_show_location(self):
        # TODO right now the robot is just saying the location.
        ##     It should point towards the position the selected shoes are
        s = self.ctx.selected
        self.tts.speak(f"You can find the {s.color} {s.type} in {s.location}.")
        self._log_event("shown_location", s.id)

        return State.DONE