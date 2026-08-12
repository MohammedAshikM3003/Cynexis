"""
CYNEXIS — TTS Provider
Abstract Text-to-Speech interface + Mock.
"""

from typing import Optional
from abc import ABC, abstractmethod
from core.logger import get_logger

log = get_logger("tts")


class TTSProvider(ABC):
    """Abstract text-to-speech provider."""

    @abstractmethod
    async def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """Synthesize text and play audio locally if configured."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """Synthesize text and return audio bytes without forced local playback."""
        ...

    @abstractmethod
    async def load(self) -> bool: ...

    @abstractmethod
    async def unload(self) -> None: ...

    @abstractmethod
    def is_loaded(self) -> bool: ...

    def stop(self) -> None:
        """Stop active speech synthesis and playback."""
        pass



class MockTTSProvider(TTSProvider):
    """Mock TTS — logs speech output instead of generating real audio."""

    def __init__(self):
        self._loaded = False
        log.info("MockTTSProvider initialized")

    async def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """Log the text and return empty audio bytes."""
        voice_str = f" [voice={voice}]" if voice else ""
        speed_str = f" [speed={speed}]" if speed else ""
        log.info(f"MOCK TTS: \"{text}\"{voice_str}{speed_str}")
        return b""

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """Mock synthesis returning empty audio bytes."""
        return b""

    async def load(self) -> bool:
        self._loaded = True
        log.info("MockTTS loaded")
        return True

    async def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    def stop(self) -> None:
        log.info("MockTTS stopped")


