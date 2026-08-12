"""
CYNEXIS — Arm Controller
Abstract arm interface + Mock. 4-DOF: base + shoulder + elbow + wrist.
No hardcoded sensor model.
"""

from abc import ABC, abstractmethod
from core.logger import get_logger
from core.state import robot_state
from core.constants import MIN_SERVO_ANGLE, MAX_SERVO_ANGLE

log = get_logger("arm")


class ArmController(ABC):
    """Abstract robotic arm interface (4-DOF: base + shoulder + elbow + wrist)."""

    @abstractmethod
    async def base_position(self, angle: float) -> None: ...

    @abstractmethod
    async def shoulder_position(self, angle: float) -> None: ...

    @abstractmethod
    async def elbow_position(self, angle: float) -> None: ...

    @abstractmethod
    async def wrist_position(self, angle: float) -> None: ...

    @abstractmethod
    async def home(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    def _clamp(self, angle: float) -> float:
        """Clamp angle to safe servo range."""
        return max(MIN_SERVO_ANGLE, min(angle, MAX_SERVO_ANGLE))


class MockArmController(ArmController):
    """Simulated arm for development without hardware."""

    def __init__(self):
        log.info("MockArmController initialized")

    async def base_position(self, angle: float) -> None:
        angle = self._clamp(angle)
        robot_state.arm.base.angle = angle
        robot_state.arm.is_moving = True
        log.info(f"MOCK: Base -> {angle}°")
        robot_state.arm.is_moving = False

    async def shoulder_position(self, angle: float) -> None:
        angle = self._clamp(angle)
        robot_state.arm.shoulder.angle = angle
        robot_state.arm.is_moving = True
        log.info(f"MOCK: Shoulder -> {angle}°")
        robot_state.arm.is_moving = False

    async def elbow_position(self, angle: float) -> None:
        angle = self._clamp(angle)
        robot_state.arm.elbow.angle = angle
        robot_state.arm.is_moving = True
        log.info(f"MOCK: Elbow -> {angle}°")
        robot_state.arm.is_moving = False

    async def wrist_position(self, angle: float) -> None:
        angle = self._clamp(angle)
        robot_state.arm.wrist.angle = angle
        robot_state.arm.is_moving = True
        log.info(f"MOCK: Wrist -> {angle}°")
        robot_state.arm.is_moving = False

    async def home(self) -> None:
        """Move all joints to safe home position (90°)."""
        robot_state.arm.base.angle = 90.0
        robot_state.arm.shoulder.angle = 90.0
        robot_state.arm.elbow.angle = 90.0
        robot_state.arm.wrist.angle = 90.0
        robot_state.arm.is_moving = False
        log.info("MOCK: Arm -> HOME (90°/90°/90°/90°)")

    async def stop(self) -> None:
        robot_state.arm.is_moving = False
        log.info("MOCK: Arm STOPPED")
