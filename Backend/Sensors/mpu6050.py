"""
CYNEXIS — Mock MPU6050 Sensor
Simulated IMU that returns plausible roll/pitch values.
"""

import time
import math
import random

from Backend.Sensors.base import SensorInterface, SensorReading, SensorHealth
from core.logger import get_logger

log = get_logger("sensor.mpu6050")


class MockMPU6050(SensorInterface):
    """Simulated MPU6050 IMU sensor."""

    def __init__(self):
        self._calibrated = False
        self._connected = True
        self._last_read = 0.0
        self._roll_offset = 0.0
        self._pitch_offset = 0.0
        log.info("MockMPU6050 initialized")

    async def read(self) -> SensorReading:
        """Return simulated roll/pitch/yaw values."""
        self._last_read = time.time()
        # Simulate slight drift
        roll = math.sin(time.time() * 0.5) * 5.0 + random.gauss(0, 0.3)
        pitch = math.cos(time.time() * 0.3) * 3.0 + random.gauss(0, 0.3)
        return SensorReading(
            value={"roll": round(roll, 2), "pitch": round(pitch, 2), "yaw": 0.0},
            unit="degrees",
            timestamp=self._last_read,
        )

    async def calibrate(self) -> bool:
        """Simulate calibration."""
        self._calibrated = True
        log.info("MockMPU6050 calibrated")
        return True

    def status(self) -> str:
        return "CONNECTED" if self._connected else "DISCONNECTED"

    def health(self) -> SensorHealth:
        return SensorHealth(
            is_connected=self._connected,
            is_calibrated=self._calibrated,
            last_read_ms=(time.time() - self._last_read) * 1000 if self._last_read else 0,
        )
