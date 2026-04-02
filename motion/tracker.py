#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Robot Tracker Module
# =============================================================================
"""
Visual tracking and pointing via Naoqi ``ALTracker``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.motion.tracker import RobotTracker

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    tracker = RobotTracker(session)

    tracker.track_face()      # Pepper follows detected faces with its head
    tracker.stop()

    # Point at world coordinates (metres, robot frame)
    tracker.point_at(1.5, 0.2, 1.0)
"""

from HRI_lab_Pepper.config import B, W, R


class RobotTracker:
    """
    Wrapper around Naoqi ``ALTracker``.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    # Naoqi frame constants
    FRAME_TORSO = 0
    FRAME_WORLD = 1
    FRAME_ROBOT = 2

    def __init__(self, session: "qi.Session") -> None:
        self._tracker = session.service("ALTracker")
        self._motion  = session.service("ALMotion")
        print(f"{B}[Tracker] Ready.{W}")

    # ------------------------------------------------------------------
    # Tracking modes
    # ------------------------------------------------------------------

    def track_face(self, face_size: float = 0.15) -> None:
        """
        Start face tracking — Pepper rotates head to follow the closest face.

        Parameters
        ----------
        face_size : float
            Approximate face diameter in metres (used by the detector).
        """
        self._tracker.registerTarget("Face", face_size)
        self._tracker.setMode("Head")
        self._tracker.track("Face")
        print(f"{B}[Tracker] Tracking face.{W}")

    def track_object(self, target_name: str, target_size: float = 0.10) -> None:
        """
        Track a named landmark / object.

        Parameters
        ----------
        target_name : str
            LandMark name registered with ALTracker.
        target_size : float
            Physical size of the target in metres.
        """
        self._tracker.registerTarget(target_name, target_size)
        self._tracker.setMode("Head")
        self._tracker.track(target_name)
        print(f"{B}[Tracker] Tracking '{target_name}'.{W}")

    def track_person(self) -> None:
        """Track a person with whole-body movement (not just head)."""
        self._tracker.registerTarget("Face", 0.15)
        self._tracker.setMode("WholeBody")
        self._tracker.track("Face")
        print(f"{B}[Tracker] Tracking person (whole body).{W}")

    def stop(self) -> None:
        """Stop all tracking."""
        self._tracker.stopTracker()

    # ------------------------------------------------------------------
    # Pointing / Looking
    # ------------------------------------------------------------------

    def point_at(
        self,
        x: float,
        y: float,
        z: float,
        frame: int = FRAME_ROBOT,
        speed: float = 0.5,
        effector: str = "Arms",
    ) -> None:
        """
        Make Pepper raise and point one arm at a 3-D location.

        Parameters
        ----------
        x, y, z : float
            Target coordinates in metres.
        frame : int
            Naoqi space frame (0=Torso, 1=World, 2=Robot).
        speed : float
            Normalised arm-movement speed [0.0, 1.0].
        effector : str
            ``"Arms"``, ``"LArm"`` or ``"RArm"``.
        """
        self._tracker.pointAt(effector, [x, y, z], frame, speed)

    def look_at(
        self,
        x: float,
        y: float,
        z: float,
        frame: int = FRAME_ROBOT,
        speed: float = 0.4,
    ) -> None:
        """
        Rotate Pepper's head to look toward a 3-D point.

        Parameters
        ----------
        x, y, z : float
            Target coordinates in metres.
        frame : int
            Naoqi space frame.
        speed : float
            Normalised movement speed.
        """
        self._tracker.lookAt([x, y, z], frame, speed, False)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return ``True`` if the tracker is currently running."""
        return self._tracker.isActive()

    def get_target_position(self) -> list:
        """
        Return the last seen target position ``[x, y, z]`` in robot frame,
        or ``[0, 0, 0]`` if no target was found.
        """
        try:
            return list(self._tracker.getTargetPosition(self.FRAME_ROBOT))
        except Exception:
            return [0.0, 0.0, 0.0]
