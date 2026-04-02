#!/usr/bin/env python
# =============================================================================
#                     HRI_lab_Pepper — Robot Movement Module
# =============================================================================
"""
High-level locomotion control via Naoqi ``ALMotion``.

Usage
-----
    from HRI_lab_Pepper.session import PepperSession
    from HRI_lab_Pepper.motion.movement import RobotMovement

    session = PepperSession.connect("tcp://ROBOT_IP:9559")
    mov = RobotMovement(session)

    mov.walk_to(1.0, 0.0, 0.0)     # Walk 1 m forward
    mov.rotate(math.radians(90))    # Turn 90° left
    mov.stop()
"""

import math
from typing import Optional

from HRI_lab_Pepper.config import B, W, R


class RobotMovement:
    """
    Locomotion interface backed by ``ALMotion``.

    Parameters
    ----------
    session : qi.Session
        Active Naoqi session.
    """

    def __init__(self, session: "qi.Session") -> None:
        self._motion = session.service("ALMotion")
        self._motion.wakeUp()
        print(f"{B}[Movement] Ready.{W}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def walk_to(
        self,
        x: float,
        y: float,
        theta: float = 0.0,
        *,
        speed: float = 1.0,
    ) -> None:
        """
        Move to a relative position then stop.

        Parameters
        ----------
        x : float
            Forward distance in metres (negative = backward).
        y : float
            Lateral distance in metres (positive = left).
        theta : float
            Rotation in radians (positive = left / counter-clockwise).
        speed : float
            Speed normalised to [0.1, 1.0].
        """
        speed = max(0.1, min(1.0, speed))
        self._motion.moveToward(
            x,
            0.0,   # no lateral drift while navigating forward
            theta / max(abs(theta), 0.01) if theta != 0 else 0.0,
        )
        # Use moveTo for a precise final goal
        self._motion.moveTo(x, y, theta, [["MaxVelXY", speed]])

    def move_toward(
        self,
        vx: float,
        vy: float,
        vtheta: float,
    ) -> None:
        """
        Apply continuous velocity command (non-blocking).

        Parameters
        ----------
        vx, vy, vtheta : float
            Normalised velocities in [−1, 1].  Call :meth:`stop` to halt.
        """
        self._motion.moveToward(
            max(-1.0, min(1.0, vx)),
            max(-1.0, min(1.0, vy)),
            max(-1.0, min(1.0, vtheta)),
        )

    def rotate(self, angle_rad: float, *, speed: float = 0.5) -> None:
        """
        Rotate in place by *angle_rad* radians.

        Parameters
        ----------
        angle_rad : float
            Positive = left (counter-clockwise).
        speed : float
            Normalised angular speed.
        """
        self._motion.moveTo(0.0, 0.0, angle_rad, [["MaxVelTheta", speed]])

    def stop(self) -> None:
        """Immediately halt all ongoing movement."""
        self._motion.stopMove()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_moving(self) -> bool:
        """Return ``True`` if Pepper is currently moving."""
        return self._motion.moveIsActive()

    def get_position(self, frame: int = 2) -> list:
        """
        Return ``[x, y, z, roll, pitch, yaw]`` of the robot's torso.

        Parameters
        ----------
        frame : int
            Naoqi space frame.  ``1`` = World, ``2`` = Robot (default).
        """
        return self._motion.getPosition("Torso", frame, True)

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------

    def rest(self) -> None:
        """Put the robot in rest posture (stiff = False)."""
        self._motion.rest()

    def wake_up(self) -> None:
        """Wake up robot (stiff = True, stand up)."""
        self._motion.wakeUp()
