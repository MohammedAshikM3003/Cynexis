"""
CYNEXIS — Central Robot State
Pydantic models representing the full system state.
All decoupled from hardware — usable in mock mode.
"""

import time
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from core.constants import (
    SystemMode,
    ConnectionState,
    ActionName,
    DEFAULT_ROVER_SPEED,
)


class RoverState(BaseModel):
    """Rover chassis state."""
    speed: int = Field(default=0, ge=0, le=255)
    target_speed: int = Field(default=DEFAULT_ROVER_SPEED)
    direction: str = Field(default="STOPPED")  # FORWARD/BACKWARD/LEFT/RIGHT/STOPPED
    is_moving: bool = Field(default=False)


class ArmJointState(BaseModel):
    """Single arm joint state."""
    angle: float = Field(default=0.0)
    min_angle: float = Field(default=0.0)
    max_angle: float = Field(default=270.0)


class ArmState(BaseModel):
    """Robotic arm state (4-DOF: base + shoulder + elbow + wrist)."""
    base: ArmJointState = Field(default_factory=ArmJointState)  # Turntable rotation
    shoulder: ArmJointState = Field(default_factory=ArmJointState)
    elbow: ArmJointState = Field(default_factory=ArmJointState)
    wrist: ArmJointState = Field(default_factory=ArmJointState)
    is_moving: bool = Field(default=False)


class GripperState(BaseModel):
    """Gripper state."""
    position: float = Field(default=0.0, ge=0.0, le=100.0)  # 0=open, 100=closed
    is_gripping: bool = Field(default=False)


class CameraState(BaseModel):
    """Camera subsystem state."""
    is_active: bool = Field(default=False)
    is_recording: bool = Field(default=False)
    is_streaming: bool = Field(default=False)
    resolution: str = Field(default="1080p")
    photos_taken: int = Field(default=0)


class HandState(BaseModel):
    """Hand gesture and position state."""
    gesture: str = Field(default="UNKNOWN")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    thumb_bend_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    index_bend_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    is_stable: bool = Field(default=False)
    stable_count: int = Field(default=0)
    last_updated: Optional[datetime] = Field(default=None)


class SensorState(BaseModel):
    """Sensor readings snapshot."""
    distance_cm: float = Field(default=0.0)  # HC-SR04
    roll: float = Field(default=0.0)         # MPU6050
    pitch: float = Field(default=0.0)        # MPU6050
    flex_thumb: int = Field(default=0)
    flex_index: int = Field(default=0)
    flex_thumb_bend_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    flex_index_bend_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    flex_middle: int = Field(default=0)
    flex_ring: int = Field(default=0)
    flex_pinky: int = Field(default=0)
    temperature_c: float = Field(default=25.0)


class VoiceState(BaseModel):
    """Voice subsystem state."""
    is_listening: bool = Field(default=False)
    is_processing: bool = Field(default=False)
    is_speaking: bool = Field(default=False)
    state: str = Field(default="IDLE")  # IDLE, LISTENING, THINKING, SPEAKING, EXECUTING, ERROR
    last_utterance: str = Field(default="")
    last_response: str = Field(default="")
    current_voice: str = Field(default="am_michael")


class AIState(BaseModel):
    """AI subsystem state."""
    llm_loaded: bool = Field(default=False)
    stt_loaded: bool = Field(default=False)
    tts_loaded: bool = Field(default=False)
    intent_ready: bool = Field(default=False)


class NetworkState(BaseModel):
    """Network connectivity state."""
    wifi_connected: bool = Field(default=False)
    internet_available: bool = Field(default=False)
    sync_enabled: bool = Field(default=False)
    pending_sync_count: int = Field(default=0)


class ESP32State(BaseModel):
    """ESP32 gateway communication state."""
    connected: bool = Field(default=False)
    last_seen: Optional[datetime] = Field(default=None)
    latency_ms: float = Field(default=0.0)
    packet_loss_pct: float = Field(default=0.0)
    packets_sent: int = Field(default=0)
    packets_acked: int = Field(default=0)
    firmware_version: str = Field(default="")
    motors_enabled: bool = Field(default=False)


class RobotState(BaseModel):
    """
    Central robot state — single source of truth.
    Updated by controllers, read by API/WebSocket/UI.
    """
    # System
    mode: SystemMode = Field(default=SystemMode.IDLE)
    connection: ConnectionState = Field(default=ConnectionState.DISCONNECTED)
    battery_pct: int = Field(default=100, ge=0, le=100)
    battery_mv: int = Field(default=12600)
    current_ma: int = Field(default=0)
    uptime_s: float = Field(default=0.0)
    boot_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Commands
    current_action: Optional[ActionName] = Field(default=None)
    last_action: Optional[ActionName] = Field(default=None)
    last_action_time: Optional[datetime] = Field(default=None)

    # Subsystems
    rover: RoverState = Field(default_factory=RoverState)
    arm: ArmState = Field(default_factory=ArmState)
    gripper: GripperState = Field(default_factory=GripperState)
    camera: CameraState = Field(default_factory=CameraState)
    sensors: SensorState = Field(default_factory=SensorState)
    hand: HandState = Field(default_factory=HandState)
    voice: VoiceState = Field(default_factory=VoiceState)
    ai: AIState = Field(default_factory=AIState)
    network: NetworkState = Field(default_factory=NetworkState)
    esp32: ESP32State = Field(default_factory=ESP32State)

    # Errors
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # ESP-NOW link
    esp_now_rssi: int = Field(default=0)
    glove_battery_pct: int = Field(default=100)

    def update_uptime(self) -> None:
        """Recalculate uptime from boot time."""
        self.uptime_s = (datetime.now(timezone.utc) - self.boot_time).total_seconds()


# Singleton state instance
robot_state = RobotState()
