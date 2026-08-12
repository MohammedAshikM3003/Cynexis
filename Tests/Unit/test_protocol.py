"""
Tests for CYNEXIS serial communication protocol.
Covers: serialization, deserialization, checksum, whitelist, IDs, duplicates.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import json

from Backend.serial_bridge.protocol import (
    Message, MessageType, ProtocolCommand, ErrorCode, AckStatus,
    PROTOCOL_VERSION, compute_checksum,
    create_command, create_ping, create_ack, create_nak,
    create_pong, create_telemetry, create_error, create_status_request,
    next_command_id, reset_command_counter, DuplicateDetector,
)


@pytest.fixture(autouse=True)
def reset_counter():
    """Reset command counter before each test."""
    reset_command_counter()
    yield


# ============================================================
# SERIALIZATION / DESERIALIZATION
# ============================================================

class TestSerialization:
    def test_command_round_trip(self):
        """Command serializes and deserializes correctly."""
        msg = create_command("FORWARD", {"speed": 200})
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.COMMAND
        assert parsed.command == "FORWARD"
        assert parsed.params == {"speed": 200}
        assert parsed.version == PROTOCOL_VERSION

    def test_ping_round_trip(self):
        msg = create_ping()
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.PING
        assert parsed.id == msg.id

    def test_ack_round_trip(self):
        msg = create_ack("cmd-000001", AckStatus.EXECUTED)
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.ACK
        assert parsed.status == AckStatus.EXECUTED
        assert parsed.id == "cmd-000001"

    def test_nak_round_trip(self):
        msg = create_nak("cmd-000001", ErrorCode.INVALID_COMMAND)
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.NAK
        assert parsed.code == ErrorCode.INVALID_COMMAND

    def test_pong_round_trip(self):
        msg = create_pong("ping-001")
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.PONG
        assert parsed.id == "ping-001"

    def test_telemetry_round_trip(self):
        data = {"battery_pct": 85, "temperature_c": 32.5}
        msg = create_telemetry(data)
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.TELEMETRY
        assert parsed.data["battery_pct"] == 85

    def test_error_round_trip(self):
        msg = create_error(ErrorCode.HARDWARE_FAULT, {"detail": "motor stall"})
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.ERROR
        assert parsed.code == ErrorCode.HARDWARE_FAULT

    def test_status_request_round_trip(self):
        msg = create_status_request()
        raw = msg.serialize()
        parsed = Message.deserialize(raw)
        assert parsed.type == MessageType.STATUS

    def test_newline_terminated(self):
        """Serialized output ends with newline."""
        msg = create_ping()
        raw = msg.serialize()
        assert raw.endswith("\n")

    def test_single_line(self):
        """Serialized output is a single line."""
        msg = create_command("STOP")
        raw = msg.serialize()
        lines = raw.strip().split("\n")
        assert len(lines) == 1


# ============================================================
# CHECKSUM
# ============================================================

class TestChecksum:
    def test_checksum_consistency(self):
        """Same payload produces same checksum."""
        payload = '{"test": "data"}'
        assert compute_checksum(payload) == compute_checksum(payload)

    def test_checksum_different(self):
        """Different payloads produce different checksums."""
        assert compute_checksum("hello") != compute_checksum("world")

    def test_checksum_length(self):
        """Checksum is 8 hex characters."""
        cs = compute_checksum("test")
        assert len(cs) == 8
        assert all(c in "0123456789abcdef" for c in cs)

    def test_corrupt_checksum_rejected(self):
        """Modified checksum is rejected on deserialize."""
        msg = create_command("FORWARD", {"speed": 100})
        raw = msg.serialize()
        # Corrupt the checksum
        d = json.loads(raw)
        d["cs"] = "deadbeef"
        corrupted = json.dumps(d) + "\n"
        with pytest.raises(ValueError, match="Checksum mismatch"):
            Message.deserialize(corrupted)

    def test_tampered_data_rejected(self):
        """Modified payload data is rejected."""
        msg = create_command("FORWARD", {"speed": 100})
        raw = msg.serialize()
        # Change speed but keep checksum
        modified = raw.replace('"speed":100', '"speed":999')
        with pytest.raises(ValueError, match="Checksum mismatch"):
            Message.deserialize(modified)


# ============================================================
# INVALID MESSAGES
# ============================================================

class TestInvalidMessages:
    def test_empty_string(self):
        with pytest.raises(ValueError, match="Empty message"):
            Message.deserialize("")

    def test_malformed_json(self):
        with pytest.raises(ValueError, match="Malformed JSON"):
            Message.deserialize("{broken json")

    def test_wrong_version(self):
        d = {"v": 99, "type": "PING", "id": "x", "ts": 0}
        # Must compute checksum with same serialization as deserialize expects
        payload = json.dumps(d, separators=(",", ":"), sort_keys=True)
        cs = compute_checksum(payload)
        d["cs"] = cs
        raw = json.dumps(d, separators=(",", ":"), sort_keys=True)
        with pytest.raises(ValueError, match="Unsupported protocol version"):
            Message.deserialize(raw)

    def test_unknown_message_type(self):
        d = {"v": 1, "type": "HACK", "id": "x", "ts": 0}
        raw = json.dumps(d, separators=(",", ":"), sort_keys=True)
        cs = compute_checksum(raw)
        d["cs"] = cs
        with pytest.raises(ValueError, match="Unknown message type"):
            Message.deserialize(json.dumps(d, separators=(",", ":"), sort_keys=True))

    def test_unknown_command(self):
        d = {"v": 1, "type": "COMMAND", "id": "x", "ts": 0, "cmd": "HACK_MOTORS"}
        raw = json.dumps(d, separators=(",", ":"), sort_keys=True)
        cs = compute_checksum(raw)
        d["cs"] = cs
        with pytest.raises(ValueError, match="Unknown command"):
            Message.deserialize(json.dumps(d, separators=(",", ":"), sort_keys=True))


# ============================================================
# COMMAND WHITELIST
# ============================================================

class TestCommandWhitelist:
    def test_all_rover_commands_valid(self):
        for cmd in ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"]:
            msg = create_command(cmd)
            assert msg.command == cmd

    def test_all_system_commands_valid(self):
        for cmd in ["PING", "STATUS", "EMERGENCY_STOP"]:
            msg = create_command(cmd)
            assert msg.command == cmd

    def test_all_arm_commands_valid(self):
        for cmd in ["ARM_HOME", "BASE", "SHOULDER", "ELBOW", "WRIST"]:
            msg = create_command(cmd)
            assert msg.command == cmd

    def test_gripper_commands_valid(self):
        for cmd in ["GRIP_OPEN", "GRIP_CLOSE"]:
            msg = create_command(cmd)
            assert msg.command == cmd

    def test_camera_commands_valid(self):
        for cmd in ["PHOTO", "START_RECORDING", "STOP_RECORDING"]:
            msg = create_command(cmd)
            assert msg.command == cmd

    def test_arbitrary_command_rejected(self):
        with pytest.raises(ValueError, match="not in the protocol whitelist"):
            create_command("HACK_MOTORS")

    def test_gpio_command_rejected(self):
        with pytest.raises(ValueError, match="not in the protocol whitelist"):
            create_command("GPIO_SET")

    def test_shell_command_rejected(self):
        with pytest.raises(ValueError, match="not in the protocol whitelist"):
            create_command("EXEC_SHELL")


# ============================================================
# COMMAND IDS
# ============================================================

class TestCommandIds:
    def test_ids_monotonic(self):
        id1 = next_command_id()
        id2 = next_command_id()
        id3 = next_command_id()
        assert id1 < id2 < id3

    def test_id_format(self):
        id1 = next_command_id()
        assert id1.startswith("cmd-")
        assert len(id1) == 10  # "cmd-" + 6 digits

    def test_reset_counter(self):
        next_command_id()
        next_command_id()
        reset_command_counter()
        id1 = next_command_id()
        assert id1 == "cmd-000001"


# ============================================================
# DUPLICATE DETECTION
# ============================================================

class TestDuplicateDetection:
    def test_first_seen_not_duplicate(self):
        dd = DuplicateDetector()
        assert not dd.is_duplicate("cmd-001")

    def test_second_seen_is_duplicate(self):
        dd = DuplicateDetector()
        dd.mark_seen("cmd-001")
        assert dd.is_duplicate("cmd-001")

    def test_different_ids_not_duplicate(self):
        dd = DuplicateDetector()
        dd.mark_seen("cmd-001")
        assert not dd.is_duplicate("cmd-002")

    def test_eviction_at_capacity(self):
        dd = DuplicateDetector(max_size=3)
        dd.mark_seen("a")
        dd.mark_seen("b")
        dd.mark_seen("c")
        dd.mark_seen("d")  # Evicts "a"
        assert not dd.is_duplicate("a")
        assert dd.is_duplicate("b")

    def test_clear(self):
        dd = DuplicateDetector()
        dd.mark_seen("cmd-001")
        dd.clear()
        assert not dd.is_duplicate("cmd-001")
        assert dd.count == 0

    def test_count(self):
        dd = DuplicateDetector()
        dd.mark_seen("a")
        dd.mark_seen("b")
        assert dd.count == 2


# ============================================================
# MESSAGE TYPE HELPERS
# ============================================================

class TestMessageHelpers:
    def test_is_command(self):
        assert create_command("STOP").is_command()

    def test_is_ack(self):
        assert create_ack("x").is_ack()

    def test_is_nak(self):
        assert create_nak("x").is_nak()

    def test_is_ping(self):
        assert create_ping().is_ping()

    def test_is_pong(self):
        assert create_pong("x").is_pong()

    def test_is_telemetry(self):
        assert create_telemetry({}).is_telemetry()

    def test_is_error(self):
        assert create_error("X").is_error()
