#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Session Singleton
# =============================================================================
"""
Manages a single qi.Session for the whole process.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession

    sess = PepperSession.connect("tcp://172.18.48.50:9559")
    # … later in any module:
    sess = PepperSession.get()
"""
import sys
try:
    import qi
except ImportError:
    qi = None  # type: ignore[assignment]

from HRI_lab_Pepper.config import B, W, R


class PepperSession:
    """Singleton wrapper around a qi.Session."""

    _session = None  # type: qi.Session | None
    _cleanup_callbacks: list = []   # registered by modules, called on disconnect

    # ------------------------------------------------------------------
    @classmethod
    def connect(cls, url: str) -> "qi.Session":
        """
        Connect to the robot at *url* (e.g. ``"tcp://172.18.48.50:9559"``).

        Returns the underlying :class:`qi.Session` so callers that need the
        raw session object can use it directly.

        Raises :class:`RuntimeError` if the connection fails.
        """
        if cls._session is not None:
            return cls._session

        if qi is None:
            raise RuntimeError(
                "The 'qi' (Naoqi SDK) package is not installed. "
                "Run from a machine with the Pepper Python SDK."
            )
        session = qi.Session()
        try:
            # listen("tcp://0.0.0.0:0") opens a random port on every interface
            # so the robot can call back into client services (e.g. processRemote).
            # This must be called BEFORE connect(), otherwise registerService
            # has no reachable address and ALAudioDevice.subscribe fails.
            session.listen("tcp://0.0.0.0:0")
            session.connect(url)
        except RuntimeError as exc:
            print(f"{R}[PepperSession] Could not connect to {url}: {exc}{W}")
            raise

        cls._session = session
        print(f"{B}[PepperSession] Connected to {url}{W}")
        return session

    # ------------------------------------------------------------------
    @classmethod
    def get(cls) -> "qi.Session":
        """
        Return the active session.

        Raises :class:`RuntimeError` if :meth:`connect` has not been called.
        """
        if cls._session is None:
            raise RuntimeError(
                "No active Pepper session. Call PepperSession.connect(url) first."
            )
        return cls._session

    # ------------------------------------------------------------------
    @classmethod
    def disable_autonomous_life(cls) -> None:
        """
        Stop all autonomous background behaviours so Pepper stops moving its
        head and eyes randomly, WITHOUT calling setState("disabled") which
        would cause the robot to go to rest/crouch posture.

        Uses ALAutonomousLife.setAutonomousAbilityEnabled() (the correct
        service per Aldebaran docs) and ALMotion idle/breath controls.
        """
        session = cls.get()

        _ABILITIES = [
            "BackgroundMovement",
            "AutonomousBlinking",
            "BasicAwareness",
            "SpeakingMovement",
            "ListeningMovement",
        ]
        try:
            al = session.service("ALAutonomousLife")
            for ability in _ABILITIES:
                try:
                    al.setAutonomousAbilityEnabled(ability, False)
                except Exception:
                    pass
            print(f"{B}[PepperSession] Autonomous abilities disabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not disable autonomous abilities: {exc}{W}")

        try:
            motion = session.service("ALMotion")
            for chain in ["Body", "Head", "Arms", "LArm", "RArm", "Legs"]:
                try:
                    motion.setBreathEnabled(chain, False)
                except Exception:
                    pass
                try:
                    motion.setIdlePostureEnabled(chain, False)
                except Exception:
                    pass
            print(f"{B}[PepperSession] ALMotion breath/idle posture disabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not disable ALMotion idle: {exc}{W}")

    # ------------------------------------------------------------------
    @classmethod
    def enable_autonomous_life(cls) -> None:
        """
        Re-enable ``ALAutonomousLife`` (solitary state) and the standard
        autonomous abilities.
        """
        session = cls.get()
        try:
            al = session.service("ALAutonomousLife")
            al.setState("solitary")
            print(f"{B}[PepperSession] AutonomousLife enabled (solitary).{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not enable AutonomousLife: {exc}{W}")

        _ABILITIES = [
            "BackgroundMovement",
            "AutonomousBlinking",
            "BasicAwareness",
            "SpeakingMovement",
            "ListeningMovement",
        ]
        try:
            al = session.service("ALAutonomousLife")
            for ability in _ABILITIES:
                try:
                    al.setAutonomousAbilityEnabled(ability, True)
                except Exception:
                    pass
            print(f"{B}[PepperSession] Autonomous abilities re-enabled.{W}")
        except Exception as exc:
            print(f"{R}[PepperSession] Could not re-enable autonomous abilities: {exc}{W}")

    # ------------------------------------------------------------------
    @classmethod
    def register_cleanup(cls, callback) -> None:
        """
        Register a zero-argument callable to be called during
        :meth:`disconnect` (in LIFO order) before the session is closed.

        Modules should call this in their ``__init__`` so that their
        service subscriptions are always cleaned up, even if the user
        forgets to call ``stop()`` / ``unsubscribe()`` themselves.

        Example::

            class SomeModule:
                def __init__(self, session):
                    self._svc = session.service("ALSomeService")
                    self._svc.subscribe("MyModule")
                    PepperSession.register_cleanup(self._cleanup)

                def _cleanup(self):
                    try:
                        self._svc.unsubscribe("MyModule")
                    except Exception:
                        pass
        """
        cls._cleanup_callbacks.append(callback)

    # ------------------------------------------------------------------
    @classmethod
    def disconnect(cls) -> None:
        """
        Run all registered cleanup callbacks (LIFO), then close the session.
        """
        if cls._session is None:
            return

        # Call cleanups in reverse registration order (LIFO) so that
        # higher-level modules are torn down before lower-level ones.
        callbacks = list(reversed(cls._cleanup_callbacks))
        cls._cleanup_callbacks.clear()
        for cb in callbacks:
            try:
                cb()
            except Exception as exc:
                print(f"{R}[PepperSession] Cleanup error ({cb}): {exc}{W}")

        try:
            cls._session.close()
        except Exception:
            pass
        cls._session = None
        print(f"{B}[PepperSession] Disconnected.{W}")
