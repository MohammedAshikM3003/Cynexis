"""
CYNEXIS — Robot Status Tool
Deterministic telemetry reporter reading directly from robot_state without LLM guesswork or internet access.
"""

from typing import Optional
from core.state import robot_state
from core.constants import ConnectionState, SystemMode
from core.logger import get_logger

log = get_logger("robot_status_tool")


class RobotStatusTool:
    """Reads real-time state from robot_state and generates concise voice status responses."""

    @classmethod
    def get_connection_status(cls) -> str:
        """Report connection state of the robot and ESP32 gateway."""
        esp32_conn = robot_state.esp32.connected
        system_conn = robot_state.connection
        if esp32_conn or system_conn == ConnectionState.CONNECTED:
            lat = round(robot_state.esp32.latency_ms, 1)
            return f"The robot is connected and online. ESP32 gateway latency is {lat} milliseconds."
        return "The robot is currently running in local offline mode, disconnected from the ESP32 gateway."

    @classmethod
    def get_battery_status(cls) -> str:
        """Report battery percentage and voltage."""
        pct = robot_state.battery_pct
        mv = robot_state.battery_mv
        volts = round(mv / 1000.0, 2)
        if pct <= 20:
            return f"Battery level is low at {pct} percent, measuring {volts} volts."
        return f"Battery level is nominal at {pct} percent, measuring {volts} volts."

    @classmethod
    def get_motor_status(cls) -> str:
        """Report motor enable state."""
        motors_enabled = robot_state.esp32.motors_enabled
        if motors_enabled:
            return "Hardware motor output is currently enabled."
        return "Hardware motor output is currently disabled for safety."

    @classmethod
    def get_full_system_status(cls) -> str:
        """Report comprehensive robot system status."""
        mode_str = robot_state.mode.value
        bat = robot_state.battery_pct
        esp_online = "online" if robot_state.esp32.connected else "offline"
        motors = "enabled" if robot_state.esp32.motors_enabled else "disabled"
        return (
            f"CYNEXIS system is in {mode_str} mode. "
            f"Battery is at {bat} percent. ESP32 gateway is {esp_online}, and motors are {motors}."
        )

    @classmethod
    def process(cls, query: str) -> str:
        """Process status query deterministically."""
        q = query.lower()
        if any(w in q for w in ["battery", "charge", "power"]):
            return cls.get_battery_status()
        if any(w in q for w in ["motor", "motors"]):
            return cls.get_motor_status()
        if any(w in q for w in ["connected", "online", "connection", "esp32"]):
            return cls.get_connection_status()
        return cls.get_full_system_status()
