"""
CYNEXIS — Serial Bridge
========================
Orchestrates communication between the laptop and ESP32 gateway.

Responsibilities:
- Send commands and wait for ACK/NAK
- Retry on timeout
- Heartbeat loop (PING/PONG)
- Emergency stop bypass (skips queue, sends immediately)
- Telemetry parsing and state updates
- Movement watchdog (auto-stop if stale)
- Connection state tracking

Architecture:
    Action Handler → Controller → SerialBridge → Transport → ESP32
"""

import asyncio
import time
from typing import Optional, Callable, Awaitable
from datetime import datetime, timezone

from core.logger import get_logger
from core.state import robot_state
from core.config import settings

from Backend.serial_bridge.protocol import (
    Message, MessageType, ProtocolCommand, ErrorCode, AckStatus,
    create_command, create_ping, create_ack, create_nak, create_pong,
    create_status_request, DuplicateDetector, PROTOCOL_VERSION,
)
from Backend.serial_bridge.transport import Transport

log = get_logger("bridge")


class SerialBridge:
    """
    Orchestrates serial communication with the ESP32 gateway.

    Usage:
        bridge = SerialBridge(transport)
        await bridge.start()
        result = await bridge.send_command("FORWARD", {"speed": 150})
        await bridge.stop()
    """

    def __init__(
        self,
        transport: Transport,
        command_timeout: float = 2.0,
        max_retries: int = 3,
        heartbeat_interval: float = 1.0,
        heartbeat_timeout: float = 3.0,
        movement_timeout: float = 5.0,
        motors_enabled: bool = False,
    ):
        self._transport = transport
        self._command_timeout = command_timeout
        self._max_retries = max_retries
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._movement_timeout = movement_timeout
        self._motors_enabled = motors_enabled

        # State tracking
        self._running = False
        self._connected = False
        self._last_seen: Optional[datetime] = None
        self._last_pong_ms: float = 0
        self._latency_ms: float = 0.0
        self._packets_sent: int = 0
        self._packets_acked: int = 0
        self._packets_failed: int = 0

        # Pending ACKs: command_id → asyncio.Future
        self._pending: dict[str, asyncio.Future] = {}

        # Duplicate detection
        self._dedup = DuplicateDetector(max_size=500)

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None

        # Movement watchdog
        self._last_movement_cmd_time: float = 0
        self._is_moving: bool = False

        # Telemetry callback
        self._telemetry_callback: Optional[Callable[[dict], Awaitable[None]]] = None

        log.info(
            f"SerialBridge created (timeout={command_timeout}s, "
            f"retries={max_retries}, motors={'ON' if motors_enabled else 'OFF'})"
        )

    # ============================================================
    # LIFECYCLE
    # ============================================================

    async def start(self) -> bool:
        """Start the bridge: connect transport, start background tasks."""
        if self._running:
            log.warning("Bridge already running")
            return True

        success = await self._transport.connect()
        if not success:
            log.error("Bridge failed to connect transport")
            self._update_esp32_state(connected=False)
            return False

        self._connected = True
        self._running = True
        self._last_seen = datetime.now(timezone.utc)

        # Start background loops
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._watchdog_task = asyncio.create_task(self._movement_watchdog_loop())

        self._update_esp32_state(connected=True)
        log.info("SerialBridge started")
        return True

    async def stop(self) -> None:
        """Stop the bridge: cancel tasks, disconnect transport."""
        self._running = False

        # Cancel background tasks
        for task in [self._heartbeat_task, self._receive_task, self._watchdog_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Fail all pending commands
        for cmd_id, future in self._pending.items():
            if not future.done():
                future.set_result(None)
        self._pending.clear()

        await self._transport.disconnect()
        self._connected = False
        self._update_esp32_state(connected=False)
        log.info("SerialBridge stopped")

    # ============================================================
    # SEND COMMAND (with ACK waiting + retry)
    # ============================================================

    async def send_command(
        self,
        command: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Send a command and wait for ACK/NAK.

        Returns:
            {
                "success": bool,
                "command_id": str,
                "status": "EXECUTED" | "TIMEOUT" | "NAK" | "DISCONNECTED",
                "error": Optional[str],
                "latency_ms": float,
                "retries": int,
            }
        """
        if not self._connected:
            return self._failure_result("", "DISCONNECTED", "Transport not connected")

        # Check motor-disabled mode for movement commands
        if not self._motors_enabled and command in (
            "FORWARD", "BACKWARD", "LEFT", "RIGHT",
            "BASE", "SHOULDER", "ELBOW", "WRIST",
            "ARM_HOME", "GRIP_OPEN", "GRIP_CLOSE",
        ):
            log.info(f"Motor-disabled mode: {command} acknowledged but not executed")
            return {
                "success": True,
                "command_id": "",
                "status": "MOTORS_DISABLED",
                "error": None,
                "latency_ms": 0,
                "retries": 0,
            }

        # Create the protocol message
        try:
            msg = create_command(command, params)
        except ValueError as e:
            return self._failure_result("", "INVALID_COMMAND", str(e))

        # Retry loop
        last_error = ""
        for attempt in range(self._max_retries + 1):
            send_time = time.monotonic()

            # Create a future for the ACK
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending[msg.id] = future

            # Send
            serialized = msg.serialize()
            sent = await self._transport.send(serialized)
            self._packets_sent += 1

            if not sent:
                self._pending.pop(msg.id, None)
                last_error = "Send failed"
                continue

            # Wait for ACK
            try:
                response = await asyncio.wait_for(future, timeout=self._command_timeout)
            except asyncio.TimeoutError:
                self._pending.pop(msg.id, None)
                self._packets_failed += 1
                last_error = f"Timeout after {self._command_timeout}s"
                log.warning(
                    f"Command {msg.id} ({command}) timeout "
                    f"(attempt {attempt + 1}/{self._max_retries + 1})"
                )
                continue

            self._pending.pop(msg.id, None)
            latency = (time.monotonic() - send_time) * 1000

            if response is None:
                last_error = "No response received"
                continue

            # Process response
            if response.is_ack():
                self._packets_acked += 1
                self._latency_ms = latency

                # Track movement for watchdog
                if command in ("FORWARD", "BACKWARD", "LEFT", "RIGHT"):
                    self._is_moving = True
                    self._last_movement_cmd_time = time.monotonic()
                elif command == "STOP" or command == "EMERGENCY_STOP":
                    self._is_moving = False

                self._update_esp32_state(connected=True)
                return {
                    "success": True,
                    "command_id": msg.id,
                    "status": response.status or "EXECUTED",
                    "error": None,
                    "latency_ms": round(latency, 1),
                    "retries": attempt,
                }

            elif response.is_nak():
                return {
                    "success": False,
                    "command_id": msg.id,
                    "status": "NAK",
                    "error": response.code or "Unknown rejection",
                    "latency_ms": round(latency, 1),
                    "retries": attempt,
                }

        # All retries exhausted
        return self._failure_result(msg.id, "TIMEOUT", last_error, self._max_retries)

    # ============================================================
    # EMERGENCY STOP (priority — bypasses queue)
    # ============================================================

    async def emergency_stop(self) -> dict:
        """
        Send EMERGENCY_STOP with highest priority.
        Bypasses normal retry and goes directly.
        """
        log.warning("EMERGENCY STOP via serial bridge")

        msg = create_command("EMERGENCY_STOP")
        serialized = msg.serialize()

        # Send immediately, don't wait for queue
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        await self._transport.send(serialized)
        self._packets_sent += 1
        self._is_moving = False

        try:
            response = await asyncio.wait_for(future, timeout=self._command_timeout)
            self._pending.pop(msg.id, None)

            if response and response.is_ack():
                self._packets_acked += 1
                return {"success": True, "status": "EMERGENCY_STOPPED"}

        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)
            log.error("EMERGENCY_STOP: no ACK received (ESP32 may be unresponsive)")

        # Even without ACK, mark as stopped locally
        return {"success": False, "status": "EMERGENCY_STOP_NO_ACK"}

    # ============================================================
    # HEARTBEAT
    # ============================================================

    async def send_ping(self) -> Optional[float]:
        """
        Send a PING and wait for PONG.
        Returns latency in ms, or None on failure.
        """
        if not self._connected:
            return None

        msg = create_ping()
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        send_time = time.monotonic()
        sent = await self._transport.send(msg.serialize())
        if not sent:
            self._pending.pop(msg.id, None)
            return None

        try:
            response = await asyncio.wait_for(future, timeout=self._heartbeat_timeout)
            self._pending.pop(msg.id, None)

            if response and response.is_pong():
                latency = (time.monotonic() - send_time) * 1000
                self._latency_ms = latency
                self._last_seen = datetime.now(timezone.utc)
                self._update_esp32_state(connected=True)
                return round(latency, 1)

        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)
            log.warning("Heartbeat timeout — ESP32 not responding")

        return None

    # ============================================================
    # STATUS REQUEST
    # ============================================================

    async def request_status(self) -> Optional[dict]:
        """Request status from ESP32 and return the data dict."""
        if not self._connected:
            return None

        msg = create_status_request()
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg.id] = future

        sent = await self._transport.send(msg.serialize())
        if not sent:
            self._pending.pop(msg.id, None)
            return None

        try:
            response = await asyncio.wait_for(future, timeout=self._command_timeout)
            self._pending.pop(msg.id, None)
            if response and response.data:
                return response.data
        except asyncio.TimeoutError:
            self._pending.pop(msg.id, None)

        return None

    # ============================================================
    # BACKGROUND LOOPS
    # ============================================================

    async def _receive_loop(self) -> None:
        """Continuously read from transport and dispatch responses."""
        log.info("Receive loop started")
        while self._running:
            try:
                raw = await self._transport.receive(timeout=0.5)
                if raw is None:
                    continue

                try:
                    msg = Message.deserialize(raw)
                except ValueError as e:
                    log.warning(f"Malformed message received: {e}")
                    continue

                # Duplicate check
                if self._dedup.is_duplicate(msg.id):
                    log.debug(f"Duplicate message {msg.id} — ignored")
                    continue
                self._dedup.mark_seen(msg.id)

                self._last_seen = datetime.now(timezone.utc)

                # Dispatch by type
                if msg.is_ack() or msg.is_nak() or msg.is_pong():
                    # Resolve pending future
                    future = self._pending.get(msg.id)
                    if future and not future.done():
                        future.set_result(msg)
                    else:
                        log.debug(f"Unexpected response {msg.type} for {msg.id}")

                elif msg.type == MessageType.STATUS:
                    # STATUS response (resolve pending)
                    future = self._pending.get(msg.id)
                    if future and not future.done():
                        future.set_result(msg)
                    # Also update state if data present
                    if msg.data:
                        self._handle_telemetry(msg.data)

                elif msg.is_telemetry():
                    if msg.data:
                        self._handle_telemetry(msg.data)

                elif msg.is_error():
                    log.error(f"ESP32 error: {msg.code} — {msg.data}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Receive loop error: {e}")
                await asyncio.sleep(0.1)

        log.info("Receive loop stopped")

    async def _heartbeat_loop(self) -> None:
        """Periodically send PING and check for PONG."""
        log.info("Heartbeat loop started")
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)

                if not self._connected:
                    # Try to reconnect
                    log.info("Attempting reconnect...")
                    success = await self._transport.connect()
                    if success:
                        self._connected = True
                        self._update_esp32_state(connected=True)
                        log.info("Reconnected to ESP32")
                    continue

                latency = await self.send_ping()
                if latency is None:
                    # Heartbeat failed
                    self._handle_connection_lost()

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Heartbeat error: {e}")
                await asyncio.sleep(1)

        log.info("Heartbeat loop stopped")

    async def _movement_watchdog_loop(self) -> None:
        """
        Auto-stop if the rover is moving and no new movement command
        has been received within MOVEMENT_TIMEOUT.
        """
        log.info("Movement watchdog started")
        while self._running:
            try:
                await asyncio.sleep(0.5)

                if self._is_moving and self._last_movement_cmd_time > 0:
                    elapsed = time.monotonic() - self._last_movement_cmd_time
                    if elapsed > self._movement_timeout:
                        log.warning(
                            f"Movement watchdog: no command for {elapsed:.1f}s — "
                            "sending auto-stop"
                        )
                        await self.send_command("STOP")
                        self._is_moving = False

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Watchdog error: {e}")
                await asyncio.sleep(1)

        log.info("Movement watchdog stopped")

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _handle_telemetry(self, data: dict) -> None:
        """Update robot state from telemetry data."""
        if "battery_pct" in data:
            robot_state.battery_pct = data["battery_pct"]
        if "temperature_c" in data:
            robot_state.sensors.temperature_c = data["temperature_c"]
        if "motors_enabled" in data:
            robot_state.esp32.motors_enabled = data["motors_enabled"]
        if "firmware_version" in data:
            robot_state.esp32.firmware_version = data["firmware_version"]

        if self._telemetry_callback:
            asyncio.create_task(self._telemetry_callback(data))

    def _handle_connection_lost(self) -> None:
        """Handle ESP32 communication loss."""
        if self._connected:
            log.warning("ESP32 connection lost")
            self._connected = False
            self._is_moving = False
            self._update_esp32_state(connected=False)

            # Enter safe state if rover was moving
            robot_state.rover.is_moving = False
            robot_state.rover.direction = "STOPPED"
            robot_state.rover.speed = 0

    def _update_esp32_state(self, connected: bool) -> None:
        """Update the ESP32 state in robot_state."""
        robot_state.esp32.connected = connected
        robot_state.esp32.last_seen = self._last_seen
        robot_state.esp32.latency_ms = self._latency_ms
        robot_state.esp32.packets_sent = self._packets_sent
        robot_state.esp32.packets_acked = self._packets_acked
        robot_state.esp32.motors_enabled = self._motors_enabled

        if self._packets_sent > 0:
            loss = ((self._packets_sent - self._packets_acked) / self._packets_sent) * 100
            robot_state.esp32.packet_loss_pct = round(loss, 1)

    @staticmethod
    def _failure_result(
        cmd_id: str, status: str, error: str, retries: int = 0
    ) -> dict:
        return {
            "success": False,
            "command_id": cmd_id,
            "status": status,
            "error": error,
            "latency_ms": 0,
            "retries": retries,
        }

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latency_ms(self) -> float:
        return self._latency_ms

    @property
    def motors_enabled(self) -> bool:
        return self._motors_enabled

    @motors_enabled.setter
    def motors_enabled(self, value: bool) -> None:
        self._motors_enabled = value
        self._update_esp32_state(connected=self._connected)
        log.info(f"Motors {'ENABLED' if value else 'DISABLED'}")

    def set_telemetry_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """Register a callback for incoming telemetry data."""
        self._telemetry_callback = callback
