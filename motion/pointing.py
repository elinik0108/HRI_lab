import math
import time


class Pointer:
    def __init__(self, session):
        self.motion = session.service("ALMotion")

    def turn_body(self, yaw_deg: float, speed: float = 0.3):
        """Rotate base by yaw_deg degrees."""
        if abs(yaw_deg) < 1.0:
            return
        yaw_rad = math.radians(yaw_deg)
        self.motion.moveTo(0.0, 0.0, yaw_rad)

    def raise_right_arm(self, hold_seconds: float = 4.0):
        """Raise right arm out in front, hand near-closed, hold, then return to rest."""
        
        arm_names  = ["RShoulderPitch", "RShoulderRoll", "RElbowRoll", "RElbowYaw", "RWristYaw"]
        arm_target = [0.0, -0.3, 0.05, 1.0, 1.5]
        arm_rest = [1.5, -0.1, 0.5, 1.0, 0.0]
        speed = 0.2

        self.motion.setStiffnesses("RArm", 1.0)
        self.motion.setAngles("RHand", 0.2, speed)
        self.motion.setAngles(arm_names, arm_target, speed)
        time.sleep(hold_seconds)

        # Return to rest
        self.motion.setAngles(arm_names, arm_rest, speed)
        self.motion.setAngles("RHand", 0.5, speed)
        time.sleep(0.5)

    def point_toward(self, yaw_deg: float, hold_seconds: float = 4.0):
        self.turn_body(yaw_deg)
        time.sleep(0.3)
        self.raise_right_arm(hold_seconds)