#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — LED Control Module
# =============================================================================
"""
Controls Pepper's eye and body LEDs via Naoqi ``ALLeds``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.motion.leds import RobotLEDs

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    leds = RobotLEDs(session)

    leds.happy()                    # Pulsing green
    leds.thinking()                 # Rotating blue
    leds.set_eyes(1.0, 0.0, 0.0)   # Solid red
    leds.off()
"""

import threading
import time
from typing import Tuple

from HRI_lab_Pepper.config import B, W


class RobotLEDs:
    """
    LED helper for Pepper's face / body LEDs.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    # Naoqi LED group names
    _FACE_LEDS    = "FaceLeds"
    _EYE_LEDS     = "FaceLeds"
    _EAR_LEDS     = "EarLeds"
    _BODY_LEDS    = "ChestLeds"  # Pepper has no foot LEDs (wheels, not legs)

    def __init__(self, session: "qi.Session") -> None:
        self._leds = session.service("ALLeds")
        self._anim_thread: threading.Thread = None
        self._anim_stop   = threading.Event()
        print(f"{B}[LEDs] Ready.{W}")

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------

    def set_eyes(self, r: float, g: float, b: float, duration: float = 0.2) -> None:
        """
        Set face/eye LEDs to an RGB colour.

        Parameters
        ----------
        r, g, b : float
            Colour channels in [0.0, 1.0].
        duration : float
            Fade-in time in seconds.
        """
        self._stop_animation()
        color = self._rgb_to_naoqi_int(r, g, b)
        self._leds.fadeRGB(self._EYE_LEDS, color, duration)

    def set_body(self, r: float, g: float, b: float, duration: float = 0.2) -> None:
        """Set chest LEDs."""
        self._stop_animation()
        color = self._rgb_to_naoqi_int(r, g, b)
        self._leds.fadeRGB(self._BODY_LEDS, color, duration)

    def off(self) -> None:
        """Turn off all LEDs."""
        self._stop_animation()
        self._leds.off(self._FACE_LEDS)
        self._leds.off(self._BODY_LEDS)

    # ------------------------------------------------------------------
    # Emotion presets
    # ------------------------------------------------------------------

    def happy(self) -> None:
        """Solid green — expresses joy or positive acknowledgement."""
        self.set_eyes(0.0, 1.0, 0.0)
        self.set_body(0.0, 0.3, 0.0)

    def thinking(self) -> None:
        """Rotating blue — indicates the robot is processing."""
        self.set_eyes(0.0, 0.3, 1.0)
        self._start_rotation_animation()

    def sad(self) -> None:
        """Dim white/blue — expresses empathy or neutral sadness."""
        self.set_eyes(0.1, 0.1, 0.4)
        self.set_body(0.05, 0.05, 0.2)

    def error(self) -> None:
        """Solid red — signals an error or failure."""
        self.set_eyes(1.0, 0.0, 0.0)
        self.set_body(0.3, 0.0, 0.0)

    def blink(
        self,
        r: float = 1.0,
        g: float = 1.0,
        b: float = 1.0,
        times: int = 3,
        period: float = 0.4,
    ) -> None:
        """
        Blink the eye LEDs *times* times.

        Parameters
        ----------
        r, g, b : float
            Colour in [0, 1].
        times : int
            Number of blink cycles.
        period : float
            On/off period in seconds.
        """
        self._stop_animation()
        color = self._rgb_to_naoqi_int(r, g, b)
        for _ in range(times):
            self._leds.fadeRGB(self._EYE_LEDS, color, 0.05)
            time.sleep(period / 2)
            self._leds.off(self._EYE_LEDS)
            time.sleep(period / 2)

    # ------------------------------------------------------------------
    # Internal animation helpers
    # ------------------------------------------------------------------

    def _start_rotation_animation(self) -> None:
        self._stop_animation()
        self._anim_stop.clear()
        self._anim_thread = threading.Thread(
            target=self._rotate_loop, daemon=True
        )
        self._anim_thread.start()

    def _stop_animation(self) -> None:
        self._anim_stop.set()
        if self._anim_thread is not None:
            self._anim_thread.join(timeout=1.0)
            self._anim_thread = None

    def _rotate_loop(self) -> None:
        """Cycle individual eye LEDs to create a rotating blue ring."""
        segments = [
            "Face/Led/Right/0Deg/Actuator/Value",
            "Face/Led/Right/45Deg/Actuator/Value",
            "Face/Led/Right/90Deg/Actuator/Value",
            "Face/Led/Right/135Deg/Actuator/Value",
            "Face/Led/Right/180Deg/Actuator/Value",
            "Face/Led/Right/225Deg/Actuator/Value",
            "Face/Led/Right/270Deg/Actuator/Value",
            "Face/Led/Right/315Deg/Actuator/Value",
        ]
        i = 0
        while not self._anim_stop.is_set():
            try:
                # fade-out all, light one
                self._leds.fadeRGB(self._EYE_LEDS, 0x00001A, 0.05)
                self._leds.setIntensity(segments[i % len(segments)], 1.0)
            except Exception:
                break
            i += 1
            time.sleep(0.08)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _rgb_to_naoqi_int(r: float, g: float, b: float) -> int:
        """Convert floating-point RGB [0,1] to a packed 0xRRGGBB integer."""
        ri = int(max(0.0, min(1.0, r)) * 255)
        gi = int(max(0.0, min(1.0, g)) * 255)
        bi = int(max(0.0, min(1.0, b)) * 255)
        return (ri << 16) | (gi << 8) | bi
