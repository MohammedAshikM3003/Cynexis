"""
CYNEXIS — ESP32 Arm Controller
Communicates via SerialBridge → Transport → ESP32 Gateway.
Updates robot_state only after receiving ACK.
"""

from core.logger import get_logger
from core.state import robot_state
from core.constants import MIN_SERVO_ANGLE, MAX_SERVO_ANGLE
from Backend.Robot.arm import ArmController

log = get_logger("esp32_arm")


class ESP32ArmController(ArmController):
    """
    ESP32-based arm controller.
    Sends individual joint commands via SerialBridge.
    """

    def __init__(self, bridge):
        from Backend.serial_bridge.bridge import SerialBridge
        self._bridge: SerialBridge = bridge
        log.info("ESP32ArmController created (bridge-based)")

    async def _send_joint(self, command: str, angle: float, joint_name: str) -> None:
        """Send a joint command and update state on ACK."""
        angle = self._clamp(angle)
        result = await self._bridge.send_command(command, {"angle": angle})
        if result["success"]:
            joint = getattr(robot_state.arm, joint_name, None)
            if joint:
                joint.angle = angle
            log.info(f"ESP32: {joint_name} -> {angle}° (ACK in {result['latency_ms']}ms)")
        else:
            log.warning(f"ESP32: {command} failed — {result.get('error', 'unknown')}")

    async def base_position(self, angle: float) -> None:
        await self._send_joint("BASE", angle, "base")

    async def shoulder_position(self, angle: float) -> None:
        await self._send_joint("SHOULDER", angle, "shoulder")

    async def elbow_position(self, angle: float) -> None:
        await self._send_joint("ELBOW", angle, "elbow")

    async def wrist_position(self, angle: float) -> None:
        await self._send_joint("WRIST", angle, "wrist")

    async def home(self) -> None:
        """Move all joints to safe home position (90°)."""
        result = await self._bridge.send_command("ARM_HOME")
        if result["success"]:
            robot_state.arm.base.angle = 90.0
            robot_state.arm.shoulder.angle = 90.0
            robot_state.arm.elbow.angle = 90.0
            robot_state.arm.wrist.angle = 90.0
            robot_state.arm.is_moving = False
            log.info("ESP32: Arm -> HOME")
        else:
            log.warning(f"ESP32: ARM_HOME failed — {result.get('error', 'unknown')}")

    async def stop(self) -> None:
        robot_state.arm.is_moving = False
        log.info("ESP32: Arm STOPPED")
