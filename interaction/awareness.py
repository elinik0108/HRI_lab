#!/usr/bin/env python
# =============================================================================
#                    HRI_lab_Pepper — Basic Awareness Module
# =============================================================================
"""
Controls Pepper's human-attention tracking via Naoqi ``ALBasicAwareness``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.interaction.awareness import BasicAwareness

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    awareness = BasicAwareness(session)

    awareness.start()                               # Start tracking people
    awareness.set_engagement_mode("FullyEngaged")   # Focus on one person
    awareness.stop()                                # Disable awareness
"""

from HRI_lab_Pepper.config import B, W, R


# Valid engagement mode strings
_ENGAGEMENT_MODES = {"FullyEngaged", "SemiEngaged", "Unengaged"}


class BasicAwareness:
    """
    Wrapper around Naoqi ``ALBasicAwareness``.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    def __init__(self, session: "qi.Session") -> None:
        self._awareness  = session.service("ALBasicAwareness")
        self._memory     = session.service("ALMemory")
        print(f"{B}[Awareness] Ready.{W}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Enable ALBasicAwareness so Pepper tracks nearby humans."""
        self._awareness.startAwareness()
        print(f"{B}[Awareness] Started.{W}")

    def stop(self) -> None:
        """Disable ALBasicAwareness."""
        self._awareness.stopAwareness()
        print(f"{B}[Awareness] Stopped.{W}")

    def is_running(self) -> bool:
        """Return ``True`` if awareness is currently active."""
        return self._awareness.isRunning()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_engagement_mode(self, mode: str) -> None:
        """
        Set the engagement mode for ALBasicAwareness.

        Parameters
        ----------
        mode : str
            One of:
            * ``"FullyEngaged"``  — Lock onto one person.
            * ``"SemiEngaged"``   — Prefer one person but switch on prolonged
              absence.
            * ``"Unengaged"``     — Scan for humans continuously.

        Raises
        ------
        ValueError
            If *mode* is not a valid engagement mode string.
        """
        if mode not in _ENGAGEMENT_MODES:
            raise ValueError(
                f"Invalid engagement mode '{mode}'. "
                f"Choose from {sorted(_ENGAGEMENT_MODES)}."
            )
        self._awareness.setEngagementMode(mode)

    def set_tracking_mode(self, mode: str) -> None:
        """
        Set the tracking target for BasicAwareness.

        Parameters
        ----------
        mode : str
            ``"Head"`` or ``"WholeBody"``.
        """
        self._awareness.setTrackingMode(mode)
