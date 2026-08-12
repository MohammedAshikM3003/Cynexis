"""
CYNEXIS — Streaming Abstraction
Abstract transport layer for live video streaming.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator
from core.logger import get_logger

log = get_logger("streaming")


class StreamTransport(ABC):
    """Abstract stream transport — replaceable without rewriting the system."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_frame(self, frame_data: bytes) -> None: ...

    @abstractmethod
    async def get_frames(self) -> AsyncGenerator[bytes, None]: ...


class MockStreamTransport(StreamTransport):
    """Mock stream transport for development."""

    def __init__(self):
        self._active = False
        self._frame_count = 0
        log.info("MockStreamTransport initialized")

    async def start(self) -> None:
        self._active = True
        log.info("MOCK: Stream started")

    async def stop(self) -> None:
        self._active = False
        log.info(f"MOCK: Stream stopped ({self._frame_count} frames sent)")

    async def send_frame(self, frame_data: bytes) -> None:
        if self._active:
            self._frame_count += 1

    async def get_frames(self) -> AsyncGenerator[bytes, None]:
        """Yield mock frames."""
        import asyncio
        while self._active:
            yield b"MOCK_FRAME"
            await asyncio.sleep(1.0 / 30)  # ~30 FPS
