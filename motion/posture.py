#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Robot Posture Module
# =============================================================================
"""
Controls Pepper's whole-body posture via Naoqi ``ALRobotPosture``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.motion.posture import RobotPosture

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    posture = RobotPosture(session)

    posture.stand()          # Neutral standing pose
    posture.stand_init()     # PEPPER stand-init (slightly bent arms)
    posture.crouch()
    posture.go_to("Sit")     # Any named posture
    print(posture.get())     # e.g. "Stand"
"""

from HRI_lab_Pepper.config import B, W, R


class RobotPosture:
    """
    Wrapper around ``ALRobotPosture``.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    default_speed : float
        Default speed of posture transitions, normalised to [0.0, 1.0].
    """

    def __init__(
        self,
        session: "qi.Session",
        default_speed: float = 0.8,
    ) -> None:
        self._posture      = session.service("ALRobotPosture")
        self._default_speed = default_speed
        print(f"{B}[Posture] Ready.{W}")

    # ------------------------------------------------------------------
    # Named shortcuts
    # ------------------------------------------------------------------

    def stand(self, speed: float = None) -> None:
        """Go to the ``"Stand"`` posture."""
        self.go_to("Stand", speed)

    def stand_init(self, speed: float = None) -> None:
        """Go to the ``"StandInit"`` posture (default interaction stance)."""
        self.go_to("StandInit", speed)

    def stand_zero(self, speed: float = None) -> None:
        """Go to ``"StandZero"`` (all joints at zero angles)."""
        self.go_to("StandZero", speed)

    def crouch(self, speed: float = None) -> None:
        """Go to the ``"Crouch"`` posture."""
        self.go_to("Crouch", speed)

    def sit(self, speed: float = None) -> None:
        """Go to the ``"Sit"`` posture (Pepper only)."""
        self.go_to("Sit", speed)

    def sit_relax(self, speed: float = None) -> None:
        """Go to ``"SitRelax"`` posture."""
        self.go_to("SitRelax", speed)

    # ------------------------------------------------------------------
    # Generic API
    # ------------------------------------------------------------------

    def go_to(self, posture_name: str, speed: float = None) -> bool:
        """
        Move to any named posture.

        Parameters
        ----------
        posture_name : str
            Naoqi posture name, e.g. ``"Stand"``, ``"StandInit"``,
            ``"Crouch"``, ``"Sit"``.
        speed : float or None
            Transition speed [0.0, 1.0].  Uses default if ``None``.

        Returns
        -------
        bool
            ``True`` if the posture was successfully reached.
        """
        spd = speed if speed is not None else self._default_speed
        spd = max(0.0, min(1.0, float(spd)))
        result = self._posture.goToPosture(posture_name, spd)
        return bool(result)

    def get(self) -> str:
        """Return the name of the current posture."""
        return self._posture.getPosture()

    def available(self) -> list:
        """Return a list of all available posture names."""
        return self._posture.getPostureList()
