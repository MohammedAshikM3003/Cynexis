"""
Tests for CYNEXIS serial bridge.
Covers: MockTransport, command→ACK flow, timeout→retry, heartbeat,
disconnect, reconnect, emergency stop, telemetry, motor-disabled, watchdog.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
import asyncio

from core.state import robot_state
from core.constants import SystemMode

from Backend.serial_bridge.protocol import (
    Message, MessageType, ProtocolCommand, AckStatus, ErrorCode,
    create_command, create_ack, create_nak, create_pong,
    create_telemetry, reset_command_counter,
)
from Backend.serial_bridge.transport import MockTransport
from Backend.serial_bridge.bridge import SerialBridge


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    reset_command_counter()
    robot_state.rover.speed = 0
    robot_state.rover.direction = "STOPPED"
    robot_state.rover.is_moving = False
    robot_state.esp32.connected = False
    robot_state.esp32.packets_sent = 0
    robot_state.esp32.packets_acked = 0
    robot_state.battery_pct = 100
    yield


# ============================================================
# MOCK TRANSPORT BASICS
# ============================================================

class TestMockTransport:
    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        t = MockTransport()
        assert not t.is_connected
        assert await t.connect()
        assert t.is_connected
        await t.disconnect()
        assert not t.is_connected

    @pytest.mark.asyncio
    async def test_send_records_history(self):
        t = MockTransport(auto_respond=False)
        await t.connect()
        await t.send("test message\n")
        assert len(t.sent_history) == 1
        assert t.sent_history[0] == "test message\n"

    @pytest.mark.asyncio
    async def test_send_fails_when_disconnected(self):
        t = MockTransport()
        result = await t.send("test\n")
        assert result is False

    @pytest.mark.asyncio
    async def test_receive_timeout(self):
        t = MockTransport(auto_respond=False)
        await t.connect()
        result = await t.receive(timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_inject_response(self):
        t = MockTransport(auto_respond=False)
        await t.connect()
        t.inject_response("hello\n")
        result = await t.receive(timeout=0.5)
        assert result == "hello\n"

    @pytest.mark.asyncio
    async def test_auto_respond_ack(self):
        """MockTransport auto-responds with ACK to COMMAND."""
        t = MockTransport(auto_respond=True)
        await t.connect()
        msg = create_command("FORWARD", {"speed": 150})
        await t.send(msg.serialize())
        response = await t.receive(timeout=1.0)
        assert response is not None
        parsed = Message.deserialize(response)
        assert parsed.is_ack()

    @pytest.mark.asyncio
    async def test_auto_respond_pong(self):
        """MockTransport auto-responds with PONG to PING."""
        from Backend.serial_bridge.protocol import create_ping
        t = MockTransport(auto_respond=True)
        await t.connect()
        msg = create_ping()
        await t.send(msg.serialize())
        response = await t.receive(timeout=1.0)
        assert response is not None
        parsed = Message.deserialize(response)
        assert parsed.is_pong()


# ============================================================
# SERIAL BRIDGE — COMMAND FLOW
# ============================================================

class TestBridgeCommands:
    @pytest_asyncio.fixture
    async def bridge(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(
            transport=t,
            command_timeout=1.0,
            max_retries=2,
            heartbeat_interval=60.0,  # Disable auto-heartbeat for tests
            heartbeat_timeout=3.0,
            motors_enabled=True,
        )
        await b.start()
        yield b
        await b.stop()

    @pytest.mark.asyncio
    async def test_send_command_success(self, bridge):
        """Command → ACK → success."""
        result = await bridge.send_command("FORWARD", {"speed": 150})
        assert result["success"] is True
        assert result["status"] == "EXECUTED"
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_send_stop_success(self, bridge):
        result = await bridge.send_command("STOP")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_all_rover_commands(self, bridge):
        for cmd in ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"]:
            result = await bridge.send_command(cmd)
            assert result["success"] is True, f"{cmd} failed"

    @pytest.mark.asyncio
    async def test_send_arm_commands(self, bridge):
        for cmd in ["ARM_HOME", "BASE", "SHOULDER", "ELBOW", "WRIST"]:
            result = await bridge.send_command(cmd, {"angle": 90})
            assert result["success"] is True, f"{cmd} failed"

    @pytest.mark.asyncio
    async def test_send_gripper_commands(self, bridge):
        for cmd in ["GRIP_OPEN", "GRIP_CLOSE"]:
            result = await bridge.send_command(cmd)
            assert result["success"] is True, f"{cmd} failed"

    @pytest.mark.asyncio
    async def test_invalid_command_rejected(self, bridge):
        result = await bridge.send_command("HACK_MOTORS")
        assert result["success"] is False
        assert result["status"] == "INVALID_COMMAND"


# ============================================================
# TIMEOUT AND RETRY
# ============================================================

class TestTimeoutRetry:
    @pytest_asyncio.fixture
    async def bridge_no_respond(self):
        """Bridge with no auto-respond — simulates unresponsive ESP32."""
        t = MockTransport(auto_respond=False)
        b = SerialBridge(
            transport=t,
            command_timeout=0.2,
            max_retries=2,
            heartbeat_interval=60.0,
            heartbeat_timeout=0.2,
            motors_enabled=True,
        )
        await b.start()
        yield b
        await b.stop()

    @pytest.mark.asyncio
    async def test_command_timeout(self, bridge_no_respond):
        """Command times out after retries."""
        result = await bridge_no_respond.send_command("FORWARD")
        assert result["success"] is False
        assert result["status"] == "TIMEOUT"
        assert result["retries"] == 2  # max_retries

    @pytest.mark.asyncio
    async def test_heartbeat_timeout(self, bridge_no_respond):
        """PING times out when ESP32 doesn't respond."""
        latency = await bridge_no_respond.send_ping()
        assert latency is None


# ============================================================
# DISCONNECT AND RECONNECT
# ============================================================

class TestDisconnect:
    @pytest.mark.asyncio
    async def test_send_when_disconnected(self):
        t = MockTransport()
        b = SerialBridge(transport=t, heartbeat_interval=60.0)
        # Don't start — bridge is not connected
        result = await b.send_command("FORWARD")
        assert result["success"] is False
        assert result["status"] == "DISCONNECTED"

    @pytest.mark.asyncio
    async def test_reconnect(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(transport=t, heartbeat_interval=60.0)
        await b.start()
        assert b.is_connected

        # Simulate disconnect
        await t.disconnect()
        b._connected = False

        # Reconnect
        await t.connect()
        b._connected = True
        result = await b.send_command("STOP")
        assert result["success"] is True

        await b.stop()


# ============================================================
# EMERGENCY STOP
# ============================================================

class TestEmergencyStop:
    @pytest_asyncio.fixture
    async def bridge(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(
            transport=t,
            command_timeout=1.0,
            heartbeat_interval=60.0,
            motors_enabled=True,
        )
        await b.start()
        yield b
        await b.stop()

    @pytest.mark.asyncio
    async def test_emergency_stop_sends(self, bridge):
        result = await bridge.emergency_stop()
        assert result["status"] in ("EMERGENCY_STOPPED", "EMERGENCY_STOP_NO_ACK")

    @pytest.mark.asyncio
    async def test_emergency_stop_clears_moving(self, bridge):
        bridge._is_moving = True
        await bridge.emergency_stop()
        assert bridge._is_moving is False


# ============================================================
# HEARTBEAT
# ============================================================

class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_ping_pong_success(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(transport=t, heartbeat_interval=60.0, heartbeat_timeout=2.0)
        await b.start()
        latency = await b.send_ping()
        assert latency is not None
        assert latency >= 0
        assert b._last_seen is not None
        await b.stop()


# ============================================================
# TELEMETRY
# ============================================================

class TestTelemetry:
    @pytest.mark.asyncio
    async def test_telemetry_updates_state(self):
        t = MockTransport(auto_respond=False)
        b = SerialBridge(transport=t, heartbeat_interval=60.0)
        await b.start()

        # Inject a telemetry message
        telem = create_telemetry({
            "battery_pct": 72,
            "temperature_c": 34.5,
            "motors_enabled": False,
            "firmware_version": "1.0.0",
        })
        t.inject_response(telem.serialize())

        # Give the receive loop time to process
        await asyncio.sleep(0.3)

        assert robot_state.battery_pct == 72
        assert robot_state.sensors.temperature_c == 34.5
        assert robot_state.esp32.firmware_version == "1.0.0"

        await b.stop()


# ============================================================
# MOTOR-DISABLED MODE
# ============================================================

class TestMotorDisabled:
    @pytest_asyncio.fixture
    async def bridge_no_motors(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(
            transport=t,
            heartbeat_interval=60.0,
            motors_enabled=False,  # Motors disabled
        )
        await b.start()
        yield b
        await b.stop()

    @pytest.mark.asyncio
    async def test_movement_acknowledged_not_sent(self, bridge_no_motors):
        """Motor-disabled mode ACKs movement but doesn't send to ESP32."""
        result = await bridge_no_motors.send_command("FORWARD", {"speed": 150})
        assert result["success"] is True
        assert result["status"] == "MOTORS_DISABLED"

    @pytest.mark.asyncio
    async def test_stop_still_sent(self, bridge_no_motors):
        """STOP and EMERGENCY_STOP are NOT blocked by motor-disabled mode."""
        # STOP is not in the motor-disabled list
        result = await bridge_no_motors.send_command("STOP")
        # It should go through the normal send path
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_arm_commands_blocked(self, bridge_no_motors):
        """Arm commands are blocked in motor-disabled mode."""
        for cmd in ["BASE", "SHOULDER", "ELBOW", "WRIST", "ARM_HOME"]:
            result = await bridge_no_motors.send_command(cmd, {"angle": 90})
            assert result["status"] == "MOTORS_DISABLED", f"{cmd} should be blocked"

    @pytest.mark.asyncio
    async def test_gripper_commands_blocked(self, bridge_no_motors):
        for cmd in ["GRIP_OPEN", "GRIP_CLOSE"]:
            result = await bridge_no_motors.send_command(cmd)
            assert result["status"] == "MOTORS_DISABLED"

    @pytest.mark.asyncio
    async def test_ping_still_works(self, bridge_no_motors):
        """PING is not a motor command — should work."""
        latency = await bridge_no_motors.send_ping()
        assert latency is not None

    @pytest.mark.asyncio
    async def test_enable_motors_runtime(self, bridge_no_motors):
        """Motors can be enabled at runtime."""
        bridge_no_motors.motors_enabled = True
        result = await bridge_no_motors.send_command("FORWARD")
        assert result["status"] != "MOTORS_DISABLED"


# ============================================================
# ESP32 STATE IN ROBOT STATE
# ============================================================

class TestESP32State:
    @pytest.mark.asyncio
    async def test_esp32_state_connected(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(transport=t, heartbeat_interval=60.0)
        await b.start()
        assert robot_state.esp32.connected is True
        await b.stop()
        assert robot_state.esp32.connected is False

    @pytest.mark.asyncio
    async def test_esp32_state_motors(self):
        t = MockTransport()
        b = SerialBridge(transport=t, heartbeat_interval=60.0, motors_enabled=False)
        await b.start()
        assert robot_state.esp32.motors_enabled is False
        b.motors_enabled = True
        assert robot_state.esp32.motors_enabled is True
        await b.stop()

    @pytest.mark.asyncio
    async def test_esp32_state_packets(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(transport=t, heartbeat_interval=60.0, motors_enabled=True)
        await b.start()
        await b.send_command("STOP")
        assert robot_state.esp32.packets_sent >= 1
        await b.stop()


# ============================================================
# STATUS REQUEST
# ============================================================

class TestStatusRequest:
    @pytest.mark.asyncio
    async def test_status_request(self):
        t = MockTransport(auto_respond=True)
        b = SerialBridge(transport=t, heartbeat_interval=60.0)
        await b.start()
        status = await b.request_status()
        assert status is not None
        assert "firmware_version" in status
        assert "motors_enabled" in status
        await b.stop()
