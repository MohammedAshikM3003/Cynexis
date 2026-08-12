"""
CYNEXIS — Audio Output Abstraction
Provides decoupled audio playback for laptop speaker and robot audio hardware.
"""

import io
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
import soundfile as sf
import sounddevice as sd

from core.logger import get_logger

log = get_logger("audio_output")


class AudioOutput(ABC):
    """Abstract audio output device interface."""

    @abstractmethod
    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        """Play audio bytes (WAV formatted or PCM). Returns True if played successfully."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if audio output device is available."""
        ...

    def stop(self) -> None:
        """Stop any active audio playback immediately."""
        pass



class MockAudioOutput(AudioOutput):
    """Mock audio output — logs playback simulation without touching audio hardware."""

    def __init__(self):
        log.info("MockAudioOutput initialized")

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        if not audio_data:
            log.debug("MockAudioOutput: Received empty audio bytes, skipping playback.")
            return True
        log.info(f"MOCK AUDIO: Simulated playback of {len(audio_data)} bytes ({sample_rate}Hz)")
        return True

    def is_available(self) -> bool:
        return True

    def stop(self) -> None:
        log.info("MockAudioOutput: Playback stopped")


class LocalAudioOutput(AudioOutput):
    """
    Local audio output — plays generated audio through the computer/robot default audio device.
    Uses non-blocking worker thread via asyncio.to_thread so event loop is never stalled.
    """

    def __init__(self, device: Optional[int] = None):
        self.device = device
        log.info(f"LocalAudioOutput initialized (device={self.device or 'default'})")

    def _play_sync(self, audio_data: bytes, sample_rate: int) -> bool:
        try:
            # Read WAV bytes with soundfile
            data, fs = sf.read(io.BytesIO(audio_data), dtype="float32")
            sd.play(data, samplerate=fs, device=self.device)
            sd.wait()
            return True
        except Exception as e:
            log.error(f"LocalAudioOutput playback failed: {e}")
            return False

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        """Play audio bytes asynchronously in background thread."""
        if not audio_data:
            log.warning("LocalAudioOutput: Cannot play empty audio data.")
            return False

        try:
            # Stop any ongoing playback before starting new speech
            self.stop()
            return await asyncio.to_thread(self._play_sync, audio_data, sample_rate)
        except Exception as e:
            log.error(f"Audio playback error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if any audio output device is detected."""
        try:
            devices = sd.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def stop(self) -> None:
        """Immediately stop any active sounddevice playback."""
        try:
            sd.stop()
            log.debug("LocalAudioOutput: sd.stop() executed")
        except Exception as e:
            log.warning(f"Error stopping audio playback: {e}")

