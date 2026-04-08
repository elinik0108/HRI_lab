#!/usr/bin/env python
# =============================================================================
#                        HRI_lab_Pepper — Speech-to-Text Module
# =============================================================================
"""
Vosk-based offline Speech-to-Text, streamed from Pepper's front microphone.

Usage (blocking)
----------------
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.speech.stt import SpeechToText

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    stt = SpeechToText(session)

    # Register + subscribe (once at startup)
    stt.register_and_subscribe()

    text = stt.listen()       # blocks until speech is detected or timeout
    print(text)               # e.g. "hello pepper"

    stt.unsubscribe()
"""
import json
import os
import threading
import time
import urllib.request
import zipfile

import numpy as np
try:
    import qi
    def _multithreaded(cls):
        return qi.multiThreaded()(cls)
except ImportError:
    qi = None  # type: ignore[assignment]
    def _multithreaded(cls):
        return cls

from HRI_lab_Pepper.config import (
    B, W,
    STT_SAMPLE_RATE, STT_MIC_CHANNEL, STT_TIMEOUT_SEC, STT_VAD_RMS_MIN,
    MODELS_ROOT, VOSK_MODEL_NAME, VOSK_MODEL_URL,
)

_MODULE_NAME = "PepperAPI_STT"


# ── Model helpers ─────────────────────────────────────────────────────────────

def _ensure_vosk_model() -> str:
    """Download and extract the Vosk model if not already present."""
    model_path = os.path.join(MODELS_ROOT, VOSK_MODEL_NAME)
    if os.path.isdir(model_path):
        return model_path

    zip_path = os.path.join(MODELS_ROOT, f"{VOSK_MODEL_NAME}.zip")
    if not os.path.exists(zip_path):
        print(f"{B}[STT] Downloading Vosk model …{W}")
        urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path)

    print(f"{B}[STT] Extracting Vosk model …{W}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(MODELS_ROOT)
    os.remove(zip_path)
    return model_path


# ── Main class ────────────────────────────────────────────────────────────────

@_multithreaded
class SpeechToText:
    """
    Naoqi-compatible STT service that captures audio from Pepper's microphone
    and transcribes it with Vosk.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session (from :class:`HRI_lab_Pepper.session.PepperSession`).
    timeout_sec : float
        Maximum listening time before the recogniser commits to the best
        partial result (or returns ``""``).
    mic_channel : int
        Naoqi audio channel index.  3 = front mic (default).
    """

    def __init__(
        self,
        session: "qi.Session",
        timeout_sec: float = STT_TIMEOUT_SEC,
        mic_channel: int = STT_MIC_CHANNEL,
    ) -> None:
        from vosk import Model, KaldiRecognizer

        self._session    = session
        self._timeout    = timeout_sec
        self._mic_ch     = mic_channel
        self._subscribed = False

        self.audio = session.service("ALAudioDevice")
        try:
            self.audio.setParameter("outputSampleRate", STT_SAMPLE_RATE)
        except Exception:
            pass

        model_path = _ensure_vosk_model()
        print(f"{B}[STT] Loading Vosk engine ({VOSK_MODEL_NAME}) …{W}")
        self._model = Model(model_path)
        self._rec   = KaldiRecognizer(self._model, STT_SAMPLE_RATE)

        self._lock        = threading.Lock()
        self._is_listening = False
        self._last_partial = ""
        self._deadline    = 0.0
        self._result_text = ""
        self._done_event  = threading.Event()

        from HRI_lab_Pepper.session import PepperSession
        PepperSession.register_cleanup(self.unsubscribe)

    # ------------------------------------------------------------------
    # Naoqi audio callback
    # ------------------------------------------------------------------

    def processRemote(self, nbChannels, nbrSamplesByChannel, timeStamp, inputBuffer):
        """Called by ALAudioDevice for every audio frame."""
        if not self._is_listening:
            return

        samples = np.frombuffer(bytes(bytearray(inputBuffer)), dtype=np.int16)

        # Basic Voice Activity Detection via RMS energy
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        timed_out = time.time() > self._deadline

        if rms < STT_VAD_RMS_MIN and not timed_out:
            return

        with self._lock:
            pcm = samples.tobytes()
            timed_out = time.time() > self._deadline  # re-check under lock

            if self._rec.AcceptWaveform(pcm):
                result = json.loads(self._rec.Result())
                text   = result.get("text", "").strip()
                if text:
                    print(f"\n{B}[STT] Result:{W} {text}")
                    self._finish(text)
                    return

            # partials
            partial = json.loads(self._rec.PartialResult()).get("partial", "").strip()
            if partial and partial != self._last_partial:
                print(f"\r{B}[STT] >> {W}{partial}    ", end="", flush=True)
                self._last_partial = partial

            if timed_out:
                final = json.loads(self._rec.FinalResult()).get("text", "").strip()
                if final:
                    print(f"\n{B}[STT] Result (timeout):{W} {final}")
                else:
                    print(f"\n{B}[STT] Timeout — no speech detected.{W}")
                self._finish(final)

    def _finish(self, text: str) -> None:
        self._result_text  = text
        self._is_listening = False
        self._rec.Reset()
        self._last_partial = ""
        self._done_event.set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_and_subscribe(self) -> None:
        """Register this service with Naoqi and subscribe to audio device."""
        if self._subscribed:
            return
        self._session.registerService(_MODULE_NAME, self)
        self.audio.setClientPreferences(
            _MODULE_NAME, STT_SAMPLE_RATE, self._mic_ch, 0
        )
        self.audio.subscribe(_MODULE_NAME)
        self._subscribed = True
        print(f"{B}[STT] Subscribed to ALAudioDevice (ch {self._mic_ch}){W}")

    def unsubscribe(self) -> None:
        """Unsubscribe from audio device."""
        if not self._subscribed:
            return
        try:
            self.audio.unsubscribe(_MODULE_NAME)
        except Exception:
            pass
        self._subscribed = False

    def listen(self) -> str:
        """
        Start listening and block until speech is detected or the timeout
        expires.

        Returns
        -------
        str
            Transcribed text, or ``""`` if nothing was recognised.
        """
        if not self._subscribed:
            self.register_and_subscribe()

        if self._is_listening:
            return ""

        print(f"{B}[STT] Listening …{W}")
        with self._lock:
            self._rec.Reset()
            self._last_partial = ""
            self._result_text  = ""

        self._done_event.clear()
        self._deadline    = time.time() + self._timeout
        self._is_listening = True

        self._done_event.wait(timeout=self._timeout + 2.0)
        return self._result_text
