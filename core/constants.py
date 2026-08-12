"""
CYNEXIS — Constants
System-wide constants, enums, and limits.
"""

from enum import Enum, auto

# ============================================================
# VERSION
# ============================================================
CYNEXIS_VERSION = "1.0.0"
SPEC_VERSION = "2.1"

# ============================================================
# SYSTEM STATES (matches CYNEXIS_MASTER_SPECIFICATION.md §12)
# ============================================================


class SystemMode(str, Enum):
    """Exclusive robot operating states."""
    NORMAL = "NORMAL"
    IDLE = "IDLE"
    MANUAL = "MANUAL"
    AI = "AI"
    SAFE = "SAFE"
    EMERGENCY = "EMERGENCY"
    SHUTDOWN = "SHUTDOWN"


class ConnectionState(str, Enum):
    """Hardware connection states."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    ERROR = "ERROR"


class SyncState(str, Enum):
    """Cloud sync states for queue items."""
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class SafetyLevel(str, Enum):
    """Action safety classification."""
    LOW = "LOW"          # No physical movement (e.g., GET_STATUS)
    MEDIUM = "MEDIUM"    # Controlled movement (e.g., FORWARD)
    HIGH = "HIGH"        # Potentially dangerous (e.g., ARM_UP at speed)
    CRITICAL = "CRITICAL"  # Emergency actions (e.g., EMERGENCY_STOP)


class GestureType(str, Enum):
    """Recognized hand gestures."""
    OPEN = "OPEN"
    FIST = "FIST"
    POINT = "POINT"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


# ============================================================
# ACTION NAMES (whitelist — only these are valid commands)
# ============================================================

class ActionName(str, Enum):
    """Predefined robot actions. LLM cannot invent new ones."""
    # Greetings & demonstrations
    HELLO = "HELLO"
    INTRODUCE_SELF = "INTRODUCE_SELF"
    WAVE = "WAVE"
    NOD = "NOD"
    # Movement
    STOP = "STOP"
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    # Arm
    ARM_UP = "ARM_UP"
    ARM_DOWN = "ARM_DOWN"
    # Gripper
    GRIP_OPEN = "GRIP_OPEN"
    GRIP_CLOSE = "GRIP_CLOSE"
    # Camera & Vision
    PHOTO = "PHOTO"
    START_RECORDING = "START_RECORDING"
    STOP_RECORDING = "STOP_RECORDING"
    DESCRIBE_SCENE = "DESCRIBE_SCENE"
    # System
    GET_STATUS = "GET_STATUS"
    EMERGENCY_STOP = "EMERGENCY_STOP"


# ============================================================
# SAFETY LIMITS
# ============================================================

MAX_ROVER_SPEED = 255         # PWM max
DEFAULT_ROVER_SPEED = 150     # PWM default
MAX_SERVO_ANGLE = 270         # DS3218 max degrees
MIN_SERVO_ANGLE = 0
MOVEMENT_TIMEOUT_MS = 5000    # Auto-stop after 5s without new command
COMMAND_TIMEOUT_MS = 10000    # Max time for any single action
OBSTACLE_STOP_CM = 20         # HC-SR04 threshold
BATTERY_CRITICAL_PCT = 15     # Enter SHUTDOWN below this
COMMS_WATCHDOG_MS = 500       # ESP-NOW timeout
MAX_MISSED_PACKETS = 5

# ============================================================
# COMMUNICATION
# ============================================================

TELEMETRY_RATE_HZ = 2         # WebSocket broadcast rate
GLOVE_SEND_RATE_HZ = 50       # Control glove → robot
STATUS_SEND_RATE_HZ = 10      # Robot → status glove

# ============================================================
# ESP32 SERIAL PROTOCOL
# ============================================================

PROTOCOL_VERSION = 1              # Laptop ↔ Gateway JSON protocol version
HEARTBEAT_INTERVAL_S = 1.0       # PING interval
HEARTBEAT_TIMEOUT_S = 3.0        # PONG deadline
COMMAND_TIMEOUT_S = 2.0          # ACK deadline per attempt
MAX_COMMAND_RETRIES = 3          # Retry count before giving up
MOVEMENT_WATCHDOG_S = 5.0        # Auto-stop if no new movement cmd
