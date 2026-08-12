"""
CYNEXIS — Connection Monitor
Detects online/offline state for sync decisions.
"""

import asyncio
from typing import Optional
from core.state import robot_state
from core.logger import get_logger

log = get_logger("connection")


class ConnectionMonitor:
    """Monitors internet connectivity for offline-first operation."""

    def __init__(self, check_url: str = "https://dns.google", interval: int = 30):
        self._check_url = check_url
        self._interval = interval
        self._running = False
        log.info("ConnectionMonitor initialized")

    async def check_once(self) -> bool:
        """Check internet connectivity once."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self._check_url)
                is_online = resp.status_code == 200
        except Exception:
            is_online = False

        robot_state.network.internet_available = is_online
        return is_online

    async def start(self) -> None:
        """Start periodic connectivity checks."""
        self._running = True
        log.info(f"Connection monitoring started (interval={self._interval}s)")
        while self._running:
            is_online = await self.check_once()
            status = "ONLINE" if is_online else "OFFLINE"
            log.debug(f"Internet: {status}")
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        log.info("Connection monitoring stopped")
