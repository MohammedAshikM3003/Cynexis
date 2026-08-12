"""
CYNEXIS — Rover Controller
Abstract rover interface + Mock + ESP32 stub.
"""

from abc import ABC, abstractmethod
from core.logger import get_logger
from core.state import robot_state
from core.constants import MAX_ROVER_SPEED, DEFAULT_ROVER_SPEED

log = get_logger("rover")


class RoverController(ABC):
    """Abstract rover interface."""

    @abstractmethod
    async def forward(self, speed: int = DEFAULT_ROVER_SPEED) -> None: ...

    @abstractmethod
    async def backward(self, speed: int = DEFAULT_ROVER_SPEED) -> None: ...

    @abstractmethod
    async def left(self, speed: int = DEFAULT_ROVER_SPEED) -> None: ...

    @abstractmethod
    async def right(self, speed: int = DEFAULT_ROVER_SPEED) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def set_speed(self, speed: int) -> None: ...

    @abstractmethod
    async def emergency_stop(self) -> None: ...


class MockRoverController(RoverController):
    """Simulated rover for development without hardware."""

    def __init__(self):
        log.info("MockRoverController initialized")

    async def forward(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        speed = min(speed, MAX_ROVER_SPEED)
        robot_state.rover.direction = "FORWARD"
        robot_state.rover.speed = speed
        robot_state.rover.is_moving = True
        log.info(f"MOCK: Rover FORWARD at speed {speed}")

    async def backward(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        speed = min(speed, MAX_ROVER_SPEED)
        robot_state.rover.direction = "BACKWARD"
        robot_state.rover.speed = speed
        robot_state.rover.is_moving = True
        log.info(f"MOCK: Rover BACKWARD at speed {speed}")

    async def left(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        speed = min(speed, MAX_ROVER_SPEED)
        robot_state.rover.direction = "LEFT"
        robot_state.rover.speed = speed
        robot_state.rover.is_moving = True
        log.info(f"MOCK: Rover LEFT at speed {speed}")

    async def right(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        speed = min(speed, MAX_ROVER_SPEED)
        robot_state.rover.direction = "RIGHT"
        robot_state.rover.speed = speed
        robot_state.rover.is_moving = True
        log.info(f"MOCK: Rover RIGHT at speed {speed}")

    async def stop(self) -> None:
        robot_state.rover.direction = "STOPPED"
        robot_state.rover.speed = 0
        robot_state.rover.is_moving = False
        log.info("MOCK: Rover STOPPED")

    async def set_speed(self, speed: int) -> None:
        robot_state.rover.target_speed = min(speed, MAX_ROVER_SPEED)
        log.info(f"MOCK: Rover speed set to {speed}")

    async def emergency_stop(self) -> None:
        robot_state.rover.direction = "STOPPED"
        robot_state.rover.speed = 0
        robot_state.rover.is_moving = False
        log.warning("MOCK: Rover EMERGENCY STOP")


class ESP32RoverController(RoverController):
    """
    ESP32-based rover controller.
    Communicates via SerialBridge → Transport → ESP32 Gateway.

    Updates robot_state only after receiving ACK from ESP32.
    """

    def __init__(self, bridge):
        """
        Args:
            bridge: SerialBridge instance for ESP32 communication.
        """
        from Backend.serial_bridge.bridge import SerialBridge
        self._bridge: SerialBridge = bridge
        log.info("ESP32RoverController created (bridge-based)")

    async def _send_and_update(self, command: str, speed: int, direction: str) -> None:
        """Send command via bridge, update state only on ACK."""
        speed = self._clamp_speed(speed)
        result = await self._bridge.send_command(command, {"speed": speed})
        if result["success"]:
            robot_state.rover.speed = speed
            robot_state.rover.direction = direction
            robot_state.rover.is_moving = speed > 0
            log.info(f"ESP32: {direction} at {speed} (ACK in {result['latency_ms']}ms)")
        else:
            log.warning(
                f"ESP32: {command} failed — {result.get('error', 'unknown')} "
                f"(status: {result['status']})"
            )

    async def forward(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        await self._send_and_update("FORWARD", speed, "FORWARD")

    async def backward(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        await self._send_and_update("BACKWARD", speed, "BACKWARD")

    async def left(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        await self._send_and_update("LEFT", speed, "LEFT")

    async def right(self, speed: int = DEFAULT_ROVER_SPEED) -> None:
        await self._send_and_update("RIGHT", speed, "RIGHT")

    async def stop(self) -> None:
        result = await self._bridge.send_command("STOP")
        robot_state.rover.speed = 0
        robot_state.rover.direction = "STOPPED"
        robot_state.rover.is_moving = False
        if result["success"]:
            log.info("ESP32: STOPPED")
        else:
            log.warning(f"ESP32: STOP may not have been received — {result['status']}")

    async def set_speed(self, speed: int) -> None:
        robot_state.rover.target_speed = self._clamp_speed(speed)

    async def emergency_stop(self) -> None:
        result = await self._bridge.emergency_stop()
        robot_state.rover.speed = 0
        robot_state.rover.direction = "STOPPED"
        robot_state.rover.is_moving = False
        log.warning(f"ESP32: EMERGENCY STOP — {result['status']}")

