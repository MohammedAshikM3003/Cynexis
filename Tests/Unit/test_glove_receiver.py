"""
CYNEXIS — Unit Tests for Glove Telemetry Receiver
===================================================
Tests for:
- JSON HAND_DATA packet parsing
- Legacy Plaintext parsing ("Thumb: 123   Index: 456")
- Malformed packet rejection
- Out-of-bounds numeric validation (0-4095)
- Robot state telemetry updates (flex_thumb, flex_index)
- Disconnection / connection failure resilience
- Auto-reconnect and retry loops
- Clean lifecycle shutdown
- Disabled receiver handling
- Read-only invariant (no write/send capabilities)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.state import robot_state
from core.config import settings
from Backend.serial_bridge.glove_receiver import (
    GloveReceiverBridge,
    MIN_ADC_VAL,
    MAX_ADC_VAL,
)


@pytest.fixture(autouse=True)
def reset_sensor_state():
    """Reset sensor readings before each test."""
    robot_state.sensors.flex_thumb = 0
    robot_state.sensors.flex_index = 0
    yield


# ============================================================
# 1. PARSING TESTS (JSON & PLAINTEXT)
# ============================================================

class TestGloveReceiverParsing:
    """Validates line parsing logic for both JSON and Plaintext formats."""

    def test_parse_json_valid_hand_data(self):
        line = '{"version":1,"type":"HAND_DATA","thumb":1200,"index":2400}'
        result = GloveReceiverBridge.parse_line(line)
        assert result == (1200, 2400)

    def test_parse_json_alternate_keys(self):
        line = '{"flex_thumb":850,"flex_index":3100}'
        result = GloveReceiverBridge.parse_line(line)
        assert result == (850, 3100)

    def test_parse_plaintext_standard(self):
        line = "Thumb: 123   Index: 456"
        result = GloveReceiverBridge.parse_line(line)
        assert result == (123, 456)

    def test_parse_plaintext_compact(self):
        line = "Thumb: 0 Index: 0"
        result = GloveReceiverBridge.parse_line(line)
        assert result == (0, 0)

    def test_parse_plaintext_mixed_whitespace(self):
        line = "  Thumb:   3950    Index:   120  \r\n"
        result = GloveReceiverBridge.parse_line(line)
        assert result == (3950, 120)

    def test_parse_malformed_json(self):
        bad_lines = [
            '{"version":1,"type":"HAND_DATA","thumb":123',  # Unterminated
            '{"type":"HAND_DATA","thumb":"abc","index":456}',  # Non-numeric
            '{"type":"OTHER_EVENT","value":100}',            # Missing keys
            '{not json}',
        ]
        for line in bad_lines:
            assert GloveReceiverBridge.parse_line(line) is None

    def test_parse_malformed_plaintext(self):
        bad_lines = [
            "Thumb: abc Index: 123",
            "Thumb: 123",
            "Index: 456",
            "Sender ready",
            "rst:ets Jul 29 2019",
            "",
            "   ",
        ]
        for line in bad_lines:
            assert GloveReceiverBridge.parse_line(line) is None

    def test_numeric_bounds_validation(self):
        # Valid bounds
        assert GloveReceiverBridge.parse_line('{"type":"HAND_DATA","thumb":0,"index":4095}') == (0, 4095)
        # Out of bounds (< 0)
        assert GloveReceiverBridge.parse_line('{"type":"HAND_DATA","thumb":-1,"index":2000}') is None
        # Out of bounds (> 4095)
        assert GloveReceiverBridge.parse_line('{"type":"HAND_DATA","thumb":5000,"index":2000}') is None
        assert GloveReceiverBridge.parse_line("Thumb: -5 Index: 200") is None
        assert GloveReceiverBridge.parse_line("Thumb: 100 Index: 9999") is None


# ============================================================
# 2. STATE APPLICATION & CALLBACKS
# ============================================================

class TestGloveReceiverState:
    """Verifies that received data cleanly updates robot_state."""

    def test_apply_telemetry_updates_robot_state(self):
        bridge = GloveReceiverBridge(port="COM8", enabled=True)
        bridge._apply_telemetry(1500, 2800)

        assert robot_state.sensors.flex_thumb == 1500
        assert robot_state.sensors.flex_index == 2800
        assert bridge.packets_received == 1
        assert bridge.last_packet_time is not None

    @pytest.mark.asyncio
    async def test_callback_invocation(self):
        bridge = GloveReceiverBridge(port="COM8", enabled=True)
        callback_called = False
        received_values = ()

        async def on_packet(thumb, index):
            nonlocal callback_called, received_values
            callback_called = True
            received_values = (thumb, index)

        bridge.set_callback(on_packet)
        bridge._apply_telemetry(500, 1000)

        # Allow callback task to run
        await asyncio.sleep(0.05)
        assert callback_called
        assert received_values == (500, 1000)


# ============================================================
# 3. LIFECYCLE, RESILIENCE & RECONNECT
# ============================================================

class TestGloveReceiverLifecycle:
    """Verifies start, stop, disconnection, retry loops, and read-only invariant."""

    @pytest.mark.asyncio
    async def test_disabled_receiver_does_not_start(self):
        bridge = GloveReceiverBridge(port="COM8", enabled=False)
        started = await bridge.start()
        assert not started
        assert not bridge.is_running

    @pytest.mark.asyncio
    async def test_empty_port_does_not_start(self):
        bridge = GloveReceiverBridge(port="", enabled=True)
        started = await bridge.start()
        assert not started
        assert not bridge.is_running

    @pytest.mark.asyncio
    async def test_start_stop_cleanly(self):
        bridge = GloveReceiverBridge(port="COM8", reconnect_interval=0.05, enabled=True)
        with patch("serial.Serial", side_effect=Exception("Simulated port error")):
            started = await bridge.start()
            assert started
            assert bridge.is_running

            await asyncio.sleep(0.08)
            await bridge.stop()
            assert not bridge.is_running

    @pytest.mark.asyncio
    async def test_stream_reading_and_reconnection(self):
        """Simulates receiving lines via mock pyserial instance."""
        bridge = GloveReceiverBridge(port="COM8", reconnect_interval=0.05, enabled=True)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial.readline.side_effect = [
            b'{"type":"HAND_DATA","thumb":111,"index":222}\n',
            b'Thumb: 333   Index: 444\n',
            b'',
            b'',
        ]

        with patch("serial.Serial", return_value=mock_serial):
            await bridge.start()
            await asyncio.sleep(0.1)

            assert robot_state.sensors.flex_thumb == 333
            assert robot_state.sensors.flex_index == 444
            assert bridge.packets_received >= 2

            await bridge.stop()
            assert not bridge.is_running

    def test_read_only_invariant(self):
        """Ensures that GloveReceiverBridge possesses NO write or send methods."""
        bridge = GloveReceiverBridge(port="COM8")
        assert not hasattr(bridge, "send")
        assert not hasattr(bridge, "send_command")
        assert not hasattr(bridge, "write")
        assert not hasattr(bridge, "transmit")
