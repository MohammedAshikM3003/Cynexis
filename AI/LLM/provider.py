"""
CYNEXIS — LLM Provider
Abstract LLM interface + Mock. Model is NOT selected until onboard computer is confirmed.
"""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
import asyncio
from core.logger import get_logger

log = get_logger("llm")


class LLMProvider(ABC):
    """Abstract LLM provider. Replace implementation without rewriting system."""

    @abstractmethod
    async def generate(self, prompt: str, context: str = "") -> str: ...

    @abstractmethod
    def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]: ...

    @abstractmethod
    async def load(self) -> bool: ...

    @abstractmethod
    async def unload(self) -> None: ...

    @abstractmethod
    def is_loaded(self) -> bool: ...

    # Optional extras (default no-ops so MockLLMProvider doesn't need to implement)
    async def health_check(self) -> dict:
        """Return provider health. Override in real providers."""
        return {"ok": self.is_loaded(), "status": "MOCK" if not self.is_loaded() else "ONLINE"}

    @property
    def llm_telemetry(self) -> dict:
        """Return current inference telemetry. Override in real providers."""
        return {"provider": "mock", "status": "MOCK"}



class MockLLMProvider(LLMProvider):
    """
    Mock LLM that returns personality-consistent canned responses.
    Used for development and testing without downloading a large model.
    """

    def __init__(self):
        self._loaded = False
        self._responses = {
            "hello": "Hello! I'm CYNEXIS, an AI-powered robotic platform.",
            "who are you": "I am CYNEXIS, a gesture-controlled telepresence and robotic manipulation system.",
            "status": "All systems are operational. Battery is at 100%. Ready for commands.",
            "battery": "My battery is currently at 100 percent.",
            "help": "I can move, capture photos, wave, and respond to voice commands. Try saying 'move forward' or 'take a photo'.",
            "time": "I don't have a real-time clock connected yet, but my system clock is running.",
        }
        log.info("MockLLMProvider initialized")

    async def generate(self, prompt: str, context: str = "") -> str:
        prompt_lower = prompt.lower().strip()
        for key, response in self._responses.items():
            if key in prompt_lower:
                return response
        return (
            f"I understood your message: '{prompt}'. "
            "As a mock AI, I can respond to basic questions about my status and capabilities."
        )

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        full_text = await self.generate(prompt, context)
        # Yield word-by-word with small delay to simulate streaming
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield (word + " ") if i < len(words) - 1 else word
            await asyncio.sleep(0.01)

    async def load(self) -> bool:
        self._loaded = True
        log.info("MockLLM loaded (no actual model)")
        return True

    async def unload(self) -> None:
        self._loaded = False
        log.info("MockLLM unloaded")

    def is_loaded(self) -> bool:
        return self._loaded
