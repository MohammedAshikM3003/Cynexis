"""
CYNEXIS — Information Cache & Rate Limiting
Thread-safe in-memory cache with TTL expiration and request throttling for external retrieval.
"""

import time
import re
import asyncio
from typing import Optional, Any
from core.logger import get_logger
from core.config import settings

log = get_logger("router_cache")


class InformationCache:
    """
    In-memory LRU-style cache with time-to-live (TTL) and request rate throttling.
    Prevents redundant web scraping and protects against API/network abuse.
    """

    def __init__(
        self,
        default_ttl_s: Optional[int] = None,
        min_request_interval_s: Optional[float] = None,
        max_entries: int = 128,
    ):
        self.default_ttl_s = default_ttl_s or getattr(settings, "web_cache_ttl_s", 900)
        self.min_request_interval_s = min_request_interval_s or getattr(settings, "web_min_request_interval_s", 1.0)
        self.max_entries = max_entries
        self._cache: dict[str, dict[str, Any]] = {}
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()
        log.info(f"InformationCache initialized (default_ttl={self.default_ttl_s}s, min_interval={self.min_request_interval_s}s)")

    @staticmethod
    def normalize_key(query: str) -> str:
        """Normalize query string for consistent cache key resolution."""
        cleaned = query.lower().strip()
        # Remove excess whitespace and common leading/trailing punctuation
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    async def get(self, query: str) -> Optional[Any]:
        """Retrieve cached value if not expired."""
        key = self.normalize_key(query)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            now = time.time()
            if now - entry["timestamp"] > entry["ttl"]:
                # Expired
                del self._cache[key]
                log.debug(f"Cache expired for query: '{query}'")
                return None

            log.info(f"Cache HIT for query: '{query}'")
            return entry["data"]

    async def set(self, query: str, data: Any, ttl_s: Optional[int] = None) -> None:
        """Store value in cache with TTL."""
        key = self.normalize_key(query)
        ttl = ttl_s if ttl_s is not None else self.default_ttl_s
        async with self._lock:
            # Evict oldest entry if at capacity
            if len(self._cache) >= self.max_entries and key not in self._cache:
                oldest_k = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
                del self._cache[oldest_k]

            self._cache[key] = {
                "data": data,
                "timestamp": time.time(),
                "ttl": ttl,
            }
            log.debug(f"Cached result for: '{key}' (TTL: {ttl}s)")

    async def can_request(self) -> bool:
        """Check if enough time has elapsed since the last external request (rate limiter)."""
        async with self._lock:
            elapsed = time.time() - self._last_request_time
            return elapsed >= self.min_request_interval_s

    async def record_request(self) -> None:
        """Record the timestamp of an external request."""
        async with self._lock:
            self._last_request_time = time.time()

    async def clear(self) -> None:
        """Flush the cache."""
        async with self._lock:
            self._cache.clear()
            log.info("InformationCache cleared")


# Singleton instance
information_cache = InformationCache()
