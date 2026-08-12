"""
CYNEXIS — STT Provider
Abstract Speech-to-Text interface + Mock.
"""

from abc import ABC, abstractmethod
from core.logger import get_logger

log = get_logger("stt")


class STTProvider(ABC):
    """Abstract speech-to-text provider."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str: ...

    @abstractmethod
    async def load(self) -> bool: ...

    @abstractmethod
    async def unload(self) -> None: ...

    @abstractmethod
    def is_loaded(self) -> bool: ...


class MockSTTProvider(STTProvider):
    """Mock STT — returns predefined text for testing the voice pipeline."""

    def __init__(self):
        self._loaded = False
        self._mock_responses = [
            "hello everyone",
            "move forward",
            "stop",
            "take a photo",
        ]
        self._index = 0
        log.info("MockSTTProvider initialized")

    async def transcribe(self, audio_data: bytes) -> str:
        """Return next mock transcription."""
        text = self._mock_responses[self._index % len(self._mock_responses)]
        self._index += 1
        log.info(f"MOCK STT: '{text}'")
        return text

    async def load(self) -> bool:
        self._loaded = True
        log.info("MockSTT loaded")
        return True

    async def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded
