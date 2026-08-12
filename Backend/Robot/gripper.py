"""
CYNEXIS — Gripper Controller
Abstract gripper interface + Mock.
"""

from abc import ABC, abstractmethod
from core.logger import get_logger
from core.state import robot_state

log = get_logger("gripper")


class GripperController(ABC):
    """Abstract gripper interface."""

    @abstractmethod
    async def open(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def set_position(self, position: float) -> None: ...


class MockGripperController(GripperController):
    """Simulated gripper for development without hardware."""

    def __init__(self):
        log.info("MockGripperController initialized")

    async def open(self) -> None:
        robot_state.gripper.position = 0.0
        robot_state.gripper.is_gripping = False
        log.info("MOCK: Gripper OPEN")

    async def close(self) -> None:
        robot_state.gripper.position = 100.0
        robot_state.gripper.is_gripping = True
        log.info("MOCK: Gripper CLOSE")

    async def set_position(self, position: float) -> None:
        position = max(0.0, min(position, 100.0))
        robot_state.gripper.position = position
        robot_state.gripper.is_gripping = position > 50.0
        log.info(f"MOCK: Gripper -> {position}%")
