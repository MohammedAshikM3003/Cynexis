"""
CYNEXIS — Sensor Abstraction
Base sensor interface. All sensors (real or mock) implement this.
"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    """A single sensor reading."""
    value: Any
    unit: str = ""
    timestamp: float = 0.0
    is_valid: bool = True


class SensorHealth(BaseModel):
    """Sensor health status."""
    is_connected: bool = False
    is_calibrated: bool = False
    error: str = ""
    last_read_ms: float = 0.0


class SensorInterface(ABC):
    """Abstract sensor interface. All sensors must implement this."""

    @abstractmethod
    async def read(self) -> SensorReading: ...

    @abstractmethod
    async def calibrate(self) -> bool: ...

    @abstractmethod
    def status(self) -> str: ...

    @abstractmethod
    def health(self) -> SensorHealth: ...
