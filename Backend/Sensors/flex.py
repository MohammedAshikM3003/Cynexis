"""
CYNEXIS — Mock Flex Sensor
Simulated flex sensor that returns plausible bend values.
"""

import time
import random

from Backend.Sensors.base import SensorInterface, SensorReading, SensorHealth
from core.logger import get_logger

log = get_logger("sensor.flex")


class MockFlexSensor(SensorInterface):
    """Simulated flex sensor for a single finger."""

    def __init__(self, finger_name: str = "unknown"):
        self.finger_name = finger_name
        self._calibrated = False
        self._connected = True
        self._last_read = 0.0
        self._straight_adc = 1500
        self._bent_adc = 3500
        log.info(f"MockFlexSensor [{finger_name}] initialized")

    async def read(self) -> SensorReading:
        """Return simulated ADC value (0-4095)."""
        self._last_read = time.time()
        # Simulate a finger at rest with slight noise
        adc_value = self._straight_adc + random.randint(-50, 50)
        return SensorReading(
            value=adc_value,
            unit="adc",
            timestamp=self._last_read,
        )

    async def calibrate(self) -> bool:
        """Simulate calibration."""
        self._calibrated = True
        log.info(f"MockFlexSensor [{self.finger_name}] calibrated: "
                 f"straight={self._straight_adc}, bent={self._bent_adc}")
        return True

    def status(self) -> str:
        return "CONNECTED" if self._connected else "DISCONNECTED"

    def health(self) -> SensorHealth:
        return SensorHealth(
            is_connected=self._connected,
            is_calibrated=self._calibrated,
            last_read_ms=(time.time() - self._last_read) * 1000 if self._last_read else 0,
        )
