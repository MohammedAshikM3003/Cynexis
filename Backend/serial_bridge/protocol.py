"""
CYNEXIS — Serial Communication Protocol
========================================
Defines the message format for Laptop ↔ ESP32 Gateway communication.

Transport: JSON-over-serial, newline-delimited.
Each message is a single JSON object terminated by '\\n'.

The ESP-NOW binary protocol (cynexis_protocol.h) is NOT used on the serial
link. The Gateway ESP32 translates between JSON (serial) and binary (ESP-NOW).

Protocol version: 1
"""

import time
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Any

from core.logger import get_logger

log = get_logger("protocol")

# ============================================================
# PROTOCOL VERSION
# ============================================================

PROTOCOL_VERSION = 1

# ============================================================
# MESSAGE TYPES
# ============================================================


class MessageType(str, Enum):
    """Types of messages exchanged between laptop and gateway."""
    COMMAND = "COMMAND"          # Laptop → Gateway: execute a robot command
    ACK = "ACK"                 # Gateway → Laptop: command accepted and executed
    NAK = "NAK"                 # Gateway → Laptop: command rejected
    PING = "PING"               # Laptop → Gateway: heartbeat request
    PONG = "PONG"               # Gateway → Laptop: heartbeat response
    TELEMETRY = "TELEMETRY"     # Gateway → Laptop: periodic sensor/state data
    ERROR = "ERROR"             # Gateway → Laptop: error report
    STATUS = "STATUS"           # Bidirectional: status request/response


# ============================================================
# COMMAND WHITELIST
# ============================================================


class ProtocolCommand(str, Enum):
    """
    Whitelisted commands that can be sent to the ESP32.
    No arbitrary GPIO/servo/shell commands allowed.
    """
    # Rover movement
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    STOP = "STOP"

    # System
    PING = "PING"
    STATUS = "STATUS"
    EMERGENCY_STOP = "EMERGENCY_STOP"

    # Camera
    PHOTO = "PHOTO"
    START_RECORDING = "START_RECORDING"
    STOP_RECORDING = "STOP_RECORDING"

    # Arm (individual joint control)
    ARM_HOME = "ARM_HOME"
    BASE = "BASE"
    SHOULDER = "SHOULDER"
    ELBOW = "ELBOW"
    WRIST = "WRIST"

    # Gripper
    GRIP_OPEN = "GRIP_OPEN"
    GRIP_CLOSE = "GRIP_CLOSE"


# Error codes returned in NAK/ERROR messages
class ErrorCode(str, Enum):
    """Error codes for NAK and ERROR messages."""
    NONE = "NONE"
    INVALID_COMMAND = "INVALID_COMMAND"
    INVALID_PARAMS = "INVALID_PARAMS"
    INVALID_CHECKSUM = "INVALID_CHECKSUM"
    INVALID_VERSION = "INVALID_VERSION"
    TIMEOUT = "TIMEOUT"
    HARDWARE_FAULT = "HARDWARE_FAULT"
    MOTORS_DISABLED = "MOTORS_DISABLED"
    BUSY = "BUSY"
    UNKNOWN = "UNKNOWN"


# ACK status values
class AckStatus(str, Enum):
    """Status values for ACK messages."""
    ACCEPTED = "ACCEPTED"
    EXECUTED = "EXECUTED"
    QUEUED = "QUEUED"


# ============================================================
# COMMAND ID GENERATION
# ============================================================

_command_counter = 0


def next_command_id() -> str:
    """Generate a monotonically increasing command ID."""
    global _command_counter
    _command_counter += 1
    return f"cmd-{_command_counter:06d}"


def reset_command_counter() -> None:
    """Reset command counter (for testing)."""
    global _command_counter
    _command_counter = 0


# ============================================================
# CHECKSUM
# ============================================================

def compute_checksum(payload: str) -> str:
    """
    Compute a checksum for a JSON payload string.
    Uses first 8 hex chars of SHA-256 for compactness.
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


# ============================================================
# MESSAGE
# ============================================================

@dataclass
class Message:
    """
    A single protocol message.

    Wire format (JSON, newline-delimited):
    {"v":1,"type":"COMMAND","id":"cmd-000001","ts":1234567890123,
     "cmd":"FORWARD","params":{"speed":150},"cs":"abcd1234"}
    """
    version: int = PROTOCOL_VERSION
    type: str = ""                          # MessageType value
    id: str = ""                            # Unique message ID
    timestamp: int = 0                      # Milliseconds since epoch
    command: Optional[str] = None           # ProtocolCommand value (for COMMAND type)
    params: Optional[dict[str, Any]] = None  # Command parameters
    status: Optional[str] = None            # AckStatus or ErrorCode
    code: Optional[str] = None              # ErrorCode for NAK/ERROR
    data: Optional[dict[str, Any]] = None   # Payload data (telemetry, status response)
    checksum: str = ""                      # Computed checksum

    def serialize(self) -> str:
        """
        Serialize to a newline-terminated JSON string.
        Computes checksum before serialization.
        """
        # Build compact dict (omit None fields)
        d = {"v": self.version, "type": self.type, "id": self.id, "ts": self.timestamp}

        if self.command is not None:
            d["cmd"] = self.command
        if self.params is not None:
            d["params"] = self.params
        if self.status is not None:
            d["status"] = self.status
        if self.code is not None:
            d["code"] = self.code
        if self.data is not None:
            d["data"] = self.data

        # Compute checksum over the payload WITHOUT the checksum field
        payload = json.dumps(d, separators=(",", ":"), sort_keys=True)
        d["cs"] = compute_checksum(payload)
        self.checksum = d["cs"]

        return json.dumps(d, separators=(",", ":"), sort_keys=True) + "\n"

    @classmethod
    def deserialize(cls, raw: str) -> "Message":
        """
        Deserialize a JSON string into a Message.
        Validates checksum. Raises ValueError on invalid input.
        """
        raw = raw.strip()
        if not raw:
            raise ValueError("Empty message")

        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON: {e}")

        # Extract checksum
        received_cs = d.pop("cs", "")

        # Validate checksum
        payload = json.dumps(d, separators=(",", ":"), sort_keys=True)
        expected_cs = compute_checksum(payload)
        if received_cs != expected_cs:
            raise ValueError(
                f"Checksum mismatch: expected={expected_cs}, received={received_cs}"
            )

        # Validate version
        version = d.get("v", 0)
        if version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {version}")

        # Validate message type
        msg_type = d.get("type", "")
        try:
            MessageType(msg_type)
        except ValueError:
            raise ValueError(f"Unknown message type: {msg_type}")

        # Validate command if present
        cmd = d.get("cmd")
        if cmd is not None:
            try:
                ProtocolCommand(cmd)
            except ValueError:
                raise ValueError(f"Unknown command: {cmd}")

        return cls(
            version=version,
            type=msg_type,
            id=d.get("id", ""),
            timestamp=d.get("ts", 0),
            command=cmd,
            params=d.get("params"),
            status=d.get("status"),
            code=d.get("code"),
            data=d.get("data"),
            checksum=received_cs,
        )

    def is_command(self) -> bool:
        return self.type == MessageType.COMMAND

    def is_ack(self) -> bool:
        return self.type == MessageType.ACK

    def is_nak(self) -> bool:
        return self.type == MessageType.NAK

    def is_ping(self) -> bool:
        return self.type == MessageType.PING

    def is_pong(self) -> bool:
        return self.type == MessageType.PONG

    def is_telemetry(self) -> bool:
        return self.type == MessageType.TELEMETRY

    def is_error(self) -> bool:
        return self.type == MessageType.ERROR


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def _now_ms() -> int:
    """Current time in milliseconds since epoch."""
    return int(time.time() * 1000)


def create_command(command: str, params: Optional[dict] = None) -> Message:
    """
    Create a COMMAND message.

    Args:
        command: ProtocolCommand value (validated against whitelist).
        params: Optional parameters (e.g., {"speed": 150}).
    """
    # Validate command against whitelist
    try:
        ProtocolCommand(command)
    except ValueError:
        raise ValueError(
            f"Command '{command}' is not in the protocol whitelist. "
            f"Allowed: {[c.value for c in ProtocolCommand]}"
        )

    return Message(
        type=MessageType.COMMAND,
        id=next_command_id(),
        timestamp=_now_ms(),
        command=command,
        params=params,
    )


def create_ping() -> Message:
    """Create a PING heartbeat message."""
    return Message(
        type=MessageType.PING,
        id=next_command_id(),
        timestamp=_now_ms(),
    )


def create_ack(command_id: str, status: str = AckStatus.EXECUTED) -> Message:
    """Create an ACK response for a given command ID."""
    return Message(
        type=MessageType.ACK,
        id=command_id,
        timestamp=_now_ms(),
        status=status,
    )


def create_nak(command_id: str, code: str = ErrorCode.UNKNOWN) -> Message:
    """Create a NAK response for a given command ID."""
    return Message(
        type=MessageType.NAK,
        id=command_id,
        timestamp=_now_ms(),
        code=code,
    )


def create_pong(ping_id: str) -> Message:
    """Create a PONG response for a given PING ID."""
    return Message(
        type=MessageType.PONG,
        id=ping_id,
        timestamp=_now_ms(),
    )


def create_telemetry(data: dict) -> Message:
    """Create a TELEMETRY message with sensor/state data."""
    return Message(
        type=MessageType.TELEMETRY,
        id=next_command_id(),
        timestamp=_now_ms(),
        data=data,
    )


def create_error(code: str, data: Optional[dict] = None) -> Message:
    """Create an ERROR message."""
    return Message(
        type=MessageType.ERROR,
        id=next_command_id(),
        timestamp=_now_ms(),
        code=code,
        data=data,
    )


def create_status_request() -> Message:
    """Create a STATUS request message."""
    return Message(
        type=MessageType.STATUS,
        id=next_command_id(),
        timestamp=_now_ms(),
    )


# ============================================================
# DUPLICATE DETECTION
# ============================================================

class DuplicateDetector:
    """
    Track recently seen message IDs to detect and reject duplicates.
    Uses a bounded set with FIFO eviction.
    """

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._seen: list[str] = []
        self._seen_set: set[str] = set()

    def is_duplicate(self, message_id: str) -> bool:
        """Check if a message ID has been seen before."""
        return message_id in self._seen_set

    def mark_seen(self, message_id: str) -> None:
        """Mark a message ID as seen."""
        if message_id in self._seen_set:
            return
        self._seen.append(message_id)
        self._seen_set.add(message_id)
        # Evict oldest if over capacity
        while len(self._seen) > self._max_size:
            old = self._seen.pop(0)
            self._seen_set.discard(old)

    def clear(self) -> None:
        """Clear all tracked IDs."""
        self._seen.clear()
        self._seen_set.clear()

    @property
    def count(self) -> int:
        return len(self._seen)
