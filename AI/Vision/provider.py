"""
CYNEXIS — Vision Provider
Abstract Vision-Language Model interface + Mock provider for CI and deterministic testing.
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.logger import get_logger

log = get_logger("vision")


class VisionProvider(ABC):
    """Abstract Vision Provider for analyzing camera images and visual queries."""

    @abstractmethod
    async def describe_image(self, image_data: bytes, prompt: str = "Describe what you see.") -> str: ...

    @abstractmethod
    async def load(self) -> bool: ...

    @abstractmethod
    async def unload(self) -> None: ...

    @abstractmethod
    def is_loaded(self) -> bool: ...


class MockVisionProvider(VisionProvider):
    """Mock Vision Provider returning deterministic scene descriptions."""

    def __init__(self):
        self._loaded = False
        self._descriptions = [
            "I see a clear testing arena with an unobstructed pathway ahead.",
            "I see a robotic arm and gripper positioned above the workspace.",
            "I observe an open laboratory floor with no obstacles in my immediate vicinity.",
            "I see a person standing in the field of view with an open workspace.",
        ]
        self._index = 0
        log.info("MockVisionProvider initialized")

    async def load(self) -> bool:
        self._loaded = True
        log.info("MockVisionProvider loaded")
        return True

    async def unload(self) -> None:
        self._loaded = False
        log.info("MockVisionProvider unloaded")

    def is_loaded(self) -> bool:
        return self._loaded

    async def describe_image(self, image_data: bytes, prompt: str = "Describe what you see.") -> str:
        if not image_data:
            return "No optical data available to analyze."
        desc = self._descriptions[self._index % len(self._descriptions)]
        self._index += 1
        log.info(f"MOCK VISION: '{desc}' (Prompt: '{prompt}')")
        return desc
