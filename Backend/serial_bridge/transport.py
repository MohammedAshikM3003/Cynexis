"""
CYNEXIS — Transport Layer
==========================
Abstract transport interface + Mock and Serial implementations.

Transport handles raw bytes/lines between the laptop and ESP32 gateway.
It does NOT understand the protocol — that's the bridge's job.

Architecture:
    Transport (ABC)
    ├── MockTransport      — in-memory, simulates responses
    ├── SerialTransport    — pyserial wrapper
    └── (future: NetworkTransport)
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Optional
from collections import deque

from core.logger import get_logger
from core.config import settings

log = get_logger("transport")


# ============================================================
# ABSTRACT TRANSPORT
# ============================================================

class Transport(ABC):
    """Abstract transport interface for ESP32 communication."""

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish the transport connection.
        Returns True on success, False on failure.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport connection gracefully."""
        ...

    @abstractmethod
    async def send(self, data: str) -> bool:
        """
        Send a string over the transport.
        Returns True if sent successfully.
        """
        ...

    @abstractmethod
    async def receive(self, timeout: float = 1.0) -> Optional[str]:
        """
        Receive a single line from the transport.
        Returns None on timeout or if disconnected.
        """
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport is currently connected."""
        ...

    @property
    def name(self) -> str:
        """Human-readable transport name."""
        return self.__class__.__name__


# ============================================================
# MOCK TRANSPORT
# ============================================================

class MockTransport(Transport):
    """
    In-memory transport for testing.
    Simulates an ESP32 gateway that auto-responds to commands.

    Features:
    - Queues sent data in `sent_history`
    - Auto-generates ACK/PONG responses
    - Can inject arbitrary responses via `inject_response()`
    - Simulates disconnect/reconnect
    """

    def __init__(self, auto_respond: bool = True):
        self._connected = False
        self._auto_respond = auto_respond
        self._inbox: deque[str] = deque()       # Responses to be read
        self._sent_history: list[str] = []       # All sent messages
        self._connect_count = 0
        log.info("MockTransport created")

    async def connect(self) -> bool:
        self._connected = True
        self._connect_count += 1
        log.info(f"MockTransport connected (#{self._connect_count})")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        log.info("MockTransport disconnected")

    async def send(self, data: str) -> bool:
        if not self._connected:
            log.warning("MockTransport: cannot send — not connected")
            return False

        self._sent_history.append(data)

        if self._auto_respond:
            self._generate_response(data)

        return True

    async def receive(self, timeout: float = 1.0) -> Optional[str]:
        if not self._connected:
            return None

        # Wait for data with timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._inbox:
                return self._inbox.popleft()
            await asyncio.sleep(0.01)

        return None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def inject_response(self, response: str) -> None:
        """Inject a response line into the receive queue."""
        self._inbox.append(response)

    @property
    def sent_history(self) -> list[str]:
        """All messages sent through this transport."""
        return self._sent_history

    def clear_history(self) -> None:
        self._sent_history.clear()
        self._inbox.clear()

    def _generate_response(self, sent_data: str) -> None:
        """Auto-generate appropriate response based on sent message."""
        import json
        try:
            d = json.loads(sent_data.strip())
            msg_type = d.get("type", "")
            msg_id = d.get("id", "")

            if msg_type == "PING":
                # Respond with PONG
                from Backend.serial_bridge.protocol import create_pong
                pong = create_pong(msg_id)
                self._inbox.append(pong.serialize())

            elif msg_type == "COMMAND":
                # Respond with ACK
                from Backend.serial_bridge.protocol import create_ack, AckStatus
                ack = create_ack(msg_id, AckStatus.EXECUTED)
                self._inbox.append(ack.serialize())

            elif msg_type == "STATUS":
                # Respond with STATUS data
                from Backend.serial_bridge.protocol import (
                    Message, MessageType, _now_ms
                )
                status_resp = Message(
                    type=MessageType.STATUS,
                    id=msg_id,
                    timestamp=_now_ms(),
                    data={
                        "battery_pct": 85,
                        "temperature_c": 32.5,
                        "motors_enabled": False,
                        "firmware_version": "1.0.0-mock",
                        "state": "IDLE",
                        "uptime_ms": 120000,
                    },
                )
                self._inbox.append(status_resp.serialize())

        except (json.JSONDecodeError, Exception) as e:
            log.debug(f"MockTransport: could not auto-respond: {e}")


# ============================================================
# SERIAL TRANSPORT
# ============================================================

class SerialTransport(Transport):
    """
    Real serial transport using pyserial.
    Communicates with the ESP32 Gateway via USB.

    Configuration from settings:
        - esp32_serial_port (e.g., "COM5", "/dev/ttyUSB0")
        - esp32_baud_rate (default: 115200)
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: Optional[int] = None,
    ):
        self._port = port or settings.esp32_serial_port
        self._baud_rate = baud_rate or settings.esp32_baud_rate
        self._serial = None
        self._reader = None
        self._writer = None
        self._connected = False
        self._lock = asyncio.Lock()
        log.info(f"SerialTransport created (port={self._port}, baud={self._baud_rate})")

    async def connect(self) -> bool:
        if not self._port:
            log.error("SerialTransport: no port configured (set ESP32_SERIAL_PORT)")
            return False

        try:
            import serial_asyncio
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self._port,
                baudrate=self._baud_rate,
            )
            self._connected = True
            log.info(f"SerialTransport connected to {self._port} @ {self._baud_rate}")
            return True

        except ImportError:
            log.error(
                "SerialTransport requires 'pyserial-asyncio'. "
                "Install with: pip install pyserial-asyncio"
            )
            return False

        except Exception as e:
            log.error(f"SerialTransport connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None
        log.info("SerialTransport disconnected")

    async def send(self, data: str) -> bool:
        if not self._connected or not self._writer:
            log.warning("SerialTransport: cannot send — not connected")
            return False

        try:
            async with self._lock:
                self._writer.write(data.encode("utf-8"))
                await self._writer.drain()
            return True
        except Exception as e:
            log.error(f"SerialTransport send failed: {e}")
            self._connected = False
            return False

    async def receive(self, timeout: float = 1.0) -> Optional[str]:
        if not self._connected or not self._reader:
            return None

        try:
            line = await asyncio.wait_for(
                self._reader.readline(),
                timeout=timeout,
            )
            return line.decode("utf-8").strip()
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            log.error(f"SerialTransport receive failed: {e}")
            self._connected = False
            return None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def port(self) -> str:
        return self._port
