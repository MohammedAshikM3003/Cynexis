"""
CYNEXIS — Sync Manager
Local-to-cloud synchronization with retry and offline queuing.
"""

import asyncio
from typing import Optional
from core.constants import SyncState
from core.config import settings
from core.logger import get_logger

log = get_logger("sync")


class SyncManager:
    """
    Manages local-to-cloud synchronization.

    States: PENDING → SYNCING → SYNCED / FAILED
    Retry: exponential backoff on failure.
    Offline: queue locally, sync when connection returns.
    """

    def __init__(self, db=None):
        self._db = db
        self._is_syncing = False
        self._retry_delay = 5  # seconds, doubles on failure
        self._max_retry_delay = 300  # 5 minutes max
        log.info("SyncManager initialized")

    async def queue_sync(self, table: str, record_id: int,
                         operation: str = "INSERT") -> None:
        """Add an item to the sync queue."""
        if not settings.sync_enabled:
            return
        if self._db:
            await self._db.insert("sync_queue", {
                "table_name": table,
                "record_id": record_id,
                "operation": operation,
                "status": SyncState.PENDING.value,
            })
            log.debug(f"Queued sync: {table}#{record_id} ({operation})")

    async def process_queue(self) -> dict:
        """Process pending sync items."""
        if not settings.sync_enabled or not settings.sync_api_url:
            return {"processed": 0, "failed": 0, "reason": "sync disabled"}

        if not self._db:
            return {"processed": 0, "failed": 0, "reason": "no database"}

        pending = await self._db.fetch_all(
            "SELECT * FROM sync_queue WHERE status = ? ORDER BY timestamp LIMIT 10",
            (SyncState.PENDING.value,),
        )

        processed = 0
        failed = 0

        for item in pending:
            try:
                # Mark as syncing
                await self._db.execute(
                    "UPDATE sync_queue SET status = ? WHERE id = ?",
                    (SyncState.SYNCING.value, item["id"]),
                )

                # TODO: actual HTTP sync to cloud API
                # For now, mark as synced (mock)
                await self._db.execute(
                    "UPDATE sync_queue SET status = ? WHERE id = ?",
                    (SyncState.SYNCED.value, item["id"]),
                )
                processed += 1

            except Exception as e:
                log.error(f"Sync failed for item {item['id']}: {e}")
                await self._db.execute(
                    "UPDATE sync_queue SET status = ?, retry_count = retry_count + 1, "
                    "error_message = ? WHERE id = ?",
                    (SyncState.FAILED.value, str(e), item["id"]),
                )
                failed += 1

        return {"processed": processed, "failed": failed}

    async def start_background_sync(self) -> None:
        """Start background sync loop with exponential backoff."""
        if not settings.sync_enabled:
            log.info("Sync disabled, background loop not started")
            return

        log.info("Background sync loop started")
        delay = self._retry_delay

        while True:
            try:
                result = await self.process_queue()
                if result["processed"] > 0:
                    delay = self._retry_delay  # Reset on success
                elif result["failed"] > 0:
                    delay = min(delay * 2, self._max_retry_delay)
            except Exception as e:
                log.error(f"Background sync error: {e}")
                delay = min(delay * 2, self._max_retry_delay)

            await asyncio.sleep(delay)
