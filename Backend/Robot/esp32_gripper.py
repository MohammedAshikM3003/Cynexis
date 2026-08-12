"""
CYNEXIS — ESP32 Gripper Controller
Communicates via SerialBridge → Transport → ESP32 Gateway.
Updates robot_state only after receiving ACK.
"""

from core.logger import get_logger
from core.state import robot_state
from Backend.Robot.gripper import GripperController

log = get_logger("esp32_gripper")


class ESP32GripperController(GripperController):
    """
    ESP32-based gripper controller.
    Sends open/close commands via SerialBridge.
    """

    def __init__(self, bridge):
        from Backend.serial_bridge.bridge import SerialBridge
        self._bridge: SerialBridge = bridge
        log.info("ESP32GripperController created (bridge-based)")

    async def open(self) -> None:
        result = await self._bridge.send_command("GRIP_OPEN")
        if result["success"]:
            robot_state.gripper.position = 0.0
            robot_state.gripper.is_gripping = False
            log.info("ESP32: Gripper OPEN")
        else:
            log.warning(f"ESP32: GRIP_OPEN failed — {result.get('error', 'unknown')}")

    async def close(self) -> None:
        result = await self._bridge.send_command("GRIP_CLOSE")
        if result["success"]:
            robot_state.gripper.position = 100.0
            robot_state.gripper.is_gripping = True
            log.info("ESP32: Gripper CLOSE")
        else:
            log.warning(f"ESP32: GRIP_CLOSE failed — {result.get('error', 'unknown')}")

    async def set_position(self, position: float) -> None:
        position = max(0.0, min(position, 100.0))
        # Map 0-100% to OPEN/CLOSE for simplicity
        if position < 50:
            await self.open()
        else:
            await self.close()
