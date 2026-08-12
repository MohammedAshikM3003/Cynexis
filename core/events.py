"""
CYNEXIS — Event Bus
Simple pub/sub for decoupled inter-module communication.
"""

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine
from core.logger import get_logger

log = get_logger("events")

# Type alias for event handlers
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """
    Async publish/subscribe event bus.

    Usage:
        bus = EventBus()
        bus.subscribe("robot.stopped", my_handler)
        await bus.publish("robot.stopped", reason="timeout")
    """

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        self._subscribers[event].append(handler)
        log.debug(f"Subscribed {handler.__name__} to '{event}'")

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        if handler in self._subscribers[event]:
            self._subscribers[event].remove(handler)

    async def publish(self, event: str, **kwargs) -> None:
        """Publish an event, calling all registered handlers."""
        handlers = self._subscribers.get(event, [])
        if not handlers:
            return
        log.debug(f"Publishing '{event}' to {len(handlers)} handler(s)")
        for handler in handlers:
            try:
                await handler(**kwargs)
            except Exception as e:
                log.error(f"Handler {handler.__name__} failed on '{event}': {e}")


# Singleton instance
event_bus = EventBus()
