"""
CYNEXIS — Memory Provider
Separates short-term conversation, long-term robot, and system memory.
"""

from abc import ABC, abstractmethod
from typing import Optional
from collections import deque
from core.logger import get_logger

log = get_logger("memory")


class MemoryProvider(ABC):
    """Abstract memory interface."""

    @abstractmethod
    async def add_conversation(self, role: str, content: str) -> None: ...

    @abstractmethod
    async def get_conversation_history(self, limit: int = 10) -> list[dict]: ...

    @abstractmethod
    async def clear_conversation(self) -> None: ...

    @abstractmethod
    async def store(self, key: str, value: str, category: str = "system") -> None: ...

    @abstractmethod
    async def recall(self, key: str, category: str = "system") -> Optional[str]: ...


class MockMemoryProvider(MemoryProvider):
    """In-memory implementation for development."""

    def __init__(self, max_conversation: int = 50):
        self._conversation: deque[dict] = deque(maxlen=max_conversation)
        self._storage: dict[str, dict[str, str]] = {
            "system": {},
            "user": {},
            "robot": {},
        }
        log.info("MockMemoryProvider initialized")

    async def add_conversation(self, role: str, content: str) -> None:
        self._conversation.append({"role": role, "content": content})
        log.debug(f"Memory: added {role} message ({len(content)} chars)")

    async def get_conversation_history(self, limit: int = 10) -> list[dict]:
        history = list(self._conversation)
        return history[-limit:]

    async def clear_conversation(self) -> None:
        self._conversation.clear()
        log.info("Conversation memory cleared")

    async def store(self, key: str, value: str, category: str = "system") -> None:
        if category not in self._storage:
            self._storage[category] = {}
        self._storage[category][key] = value
        log.debug(f"Memory stored: [{category}] {key}")

    async def recall(self, key: str, category: str = "system") -> Optional[str]:
        return self._storage.get(category, {}).get(key)
