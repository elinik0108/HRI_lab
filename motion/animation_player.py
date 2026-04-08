#!/usr/bin/env python
# =============================================================================
#                 HRI_lab_Pepper — Animation Player Module
# =============================================================================
"""
Wrapper around Naoqi ``ALAnimationPlayer``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.motion.animation_player import AnimationPlayer

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    anim = AnimationPlayer(session)

    # Blocking (waits until animation finishes)
    anim.run("animations/Stand/Gestures/Hey_1")

    # Non-blocking (fire-and-forget in a background thread)
    anim.run_async("animations/Stand/Emotions/Positive/Happy_4")
"""

import threading

try:
    import qi
except ImportError:
    qi = None  # type: ignore[assignment]

from HRI_lab_Pepper.config import B, W, R


class AnimationPlayer:
    """
    High-level interface to ``ALAnimationPlayer`` on Pepper.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    def __init__(self, session: "qi.Session") -> None:
        self._player = session.service("ALAnimationPlayer")
        print(f"{B}[ANIM] AnimationPlayer ready{W}")

    # ------------------------------------------------------------------
    # Core playback
    # ------------------------------------------------------------------

    def run(self, animation_path: str) -> None:
        """
        Play an animation by its full path (blocking).

        Parameters
        ----------
        animation_path : str
            Full animation path, e.g.
            ``"animations/Stand/Gestures/Hey_1"``
        """
        if not animation_path:
            return
        print(f"[ANIM] Running: {animation_path}")
        try:
            self._player.run(animation_path)
        except Exception as exc:
            print(f"{R}[ANIM] Error running '{animation_path}': {exc}{W}")

    def run_async(self, animation_path: str) -> None:
        """
        Play an animation in a background thread (non-blocking).

        Parameters
        ----------
        animation_path : str
            Full animation path, e.g.
            ``"animations/Stand/Gestures/Hey_1"``
        """
        if not animation_path:
            return
        threading.Thread(target=self.run, args=(animation_path,), daemon=True).start()
