#!/usr/bin/env python
# =============================================================================
#                        HRI_lab_Pepper — Text-to-Speech Module
# =============================================================================
"""
Wrapper around Naoqi ``ALTextToSpeech`` and ``ALAnimatedSpeech``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.speech.tts import TextToSpeech

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    tts = TextToSpeech(session)

    tts.speak("Hello, I am Pepper.")
    tts.animated_speak("I am ^start(animations/Stand/Gestures/Hey_1) happy to see you!")

    tts.set_language("English")
    tts.set_volume(0.8)
    tts.set_speed(90)      # % of normal speed (100 = normal)
"""

try:
    import qi
except ImportError:
    qi = None  # type: ignore[assignment]

from HRI_lab_Pepper.config import B, W, R


class TextToSpeech:
    """
    High-level TTS interface for Pepper.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    language : str
        Initial language for ALTextToSpeech (e.g. ``"English"``, ``"French"``).
    volume : float
        Initial volume 0.0–1.0.
    speed : int
        Initial speech speed as a percentage of normal (100 = normal).
    """

    def __init__(
        self,
        session: "qi.Session",
        language: str = "English",
        volume: float = 0.8,
        speed: int = 100,
    ) -> None:
        self._tts  = session.service("ALTextToSpeech")
        self._anim = session.service("ALAnimatedSpeech")

        self.set_language(language)
        self.set_volume(volume)
        self.set_speed(speed)

        print(f"{B}[TTS] Ready — lang={language}, vol={volume}, speed={speed}%{W}")

    # ------------------------------------------------------------------
    # Core speech
    # ------------------------------------------------------------------

    def speak(self, text: str, animated: bool = False) -> None:
        """
        Make Pepper say *text*.

        Parameters
        ----------
        text : str
            The sentence(s) to synthesise.
        animated : bool
            If ``True``, use ``ALAnimatedSpeech`` so Pepper also moves.
        """
        if not text:
            return
        if animated:
            self.animated_speak(text)
        else:
            self._tts.say(text)

    def animated_speak(self, text: str) -> None:
        """
        Speak with body animation.  Supports Naoqi ``^start()`` / ``^stop()``
        animation tags in *text*.
        """
        if not text:
            return
        self._anim.say(text)

    def say_localized(self, text: str) -> None:
        """
        Call ``ALTextToSpeech.sayLocalized`` when the robot should adapt
        phonemes to the current locale.
        """
        self._tts.sayLocalized(text)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_language(self, language: str) -> None:
        """Set the synthesis language (e.g. ``"English"``, ``"French"``)."""
        self._tts.setLanguage(language)

    def get_language(self) -> str:
        """Return the current synthesis language string."""
        return self._tts.getLanguage()

    def get_available_languages(self) -> list:
        """Return a list of installed language strings."""
        return self._tts.getAvailableLanguages()

    def set_volume(self, volume: float) -> None:
        """Set volume in the range [0.0, 1.0]."""
        volume = max(0.0, min(1.0, float(volume)))
        self._tts.setVolume(volume)

    def get_volume(self) -> float:
        """Return current volume."""
        return self._tts.getVolume()

    def set_speed(self, speed: int) -> None:
        """
        Set speech speed as a percentage of normal rate.

        Parameters
        ----------
        speed : int
            50–200; 100 = normal speed.
        """
        speed = max(50, min(200, int(speed)))
        self._tts.setParameter("speed", speed)

    def set_pitch(self, pitch: float) -> None:
        """Set pitch shifting in semitones (−9 to +9)."""
        self._tts.setParameter("pitchShift", float(pitch))

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Interrupt ongoing speech immediately."""
        self._tts.stopAll()
