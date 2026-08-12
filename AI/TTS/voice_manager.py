"""
CYNEXIS — Voice Manager
Manages active voice profile, selection, validation, and speech parameters.
"""

from typing import Optional
from core.logger import get_logger
from core.config import settings
from AI.TTS.voices import (
    VoiceProfile,
    VOICE_PROFILES,
    DEFAULT_VOICE_ID,
    get_voice_profile,
    is_valid_voice,
    list_voice_profiles,
)

log = get_logger("voice_manager")

# Speed limits
MIN_TTS_SPEED = 0.5
MAX_TTS_SPEED = 2.0
DEFAULT_TTS_SPEED = 1.2  # 1.2x is 15% faster synthesis, still natural quality


class VoiceManager:
    """
    Manages active voice selection and speech speed configuration for CYNEXIS.
    Strictly validates voice IDs against registered Kokoro voices.
    """

    def __init__(self, default_voice: Optional[str] = None, default_speed: Optional[float] = None):
        configured_voice = default_voice or getattr(settings, "tts_voice", DEFAULT_VOICE_ID)
        if is_valid_voice(configured_voice):
            self._current_voice_id = configured_voice
        else:
            log.warning(
                f"Configured voice '{configured_voice}' is not a valid Kokoro voice. "
                f"Falling back to default '{DEFAULT_VOICE_ID}'."
            )
            self._current_voice_id = DEFAULT_VOICE_ID

        configured_speed = default_speed if default_speed is not None else getattr(settings, "tts_speed", DEFAULT_TTS_SPEED)
        try:
            self._speed = self._validate_speed(configured_speed)
        except ValueError:
            log.warning(f"Configured speed '{configured_speed}' out of range. Using {DEFAULT_TTS_SPEED}.")
            self._speed = DEFAULT_TTS_SPEED

        log.info(
            f"VoiceManager initialized with voice='{self._current_voice_id}', speed={self._speed}"
        )

    @staticmethod
    def _validate_speed(speed: float) -> float:
        """Validate speed is within safe numerical bounds."""
        if not isinstance(speed, (int, float)):
            raise ValueError(f"Speed must be a number, got {type(speed).__name__}")
        if speed < MIN_TTS_SPEED or speed > MAX_TTS_SPEED:
            raise ValueError(
                f"TTS speed {speed} is out of safe range [{MIN_TTS_SPEED}, {MAX_TTS_SPEED}]"
            )
        return float(speed)

    def set_voice(self, voice_id: str) -> VoiceProfile:
        """
        Set active voice ID.
        Raises ValueError if voice_id is not a valid registered Kokoro voice.
        """
        if not is_valid_voice(voice_id):
            valid_ids = list(VOICE_PROFILES.keys())
            raise ValueError(
                f"Invalid voice ID '{voice_id}'. Available Kokoro voices: {valid_ids}"
            )
        self._current_voice_id = voice_id
        log.info(f"Active voice switched to: '{voice_id}' ({VOICE_PROFILES[voice_id].name})")
        return VOICE_PROFILES[voice_id]

    def get_current_voice(self) -> str:
        """Return the active voice identifier."""
        return self._current_voice_id

    def current_voice(self) -> VoiceProfile:
        """Return the active VoiceProfile model."""
        return VOICE_PROFILES[self._current_voice_id]

    def list_available_voices(self) -> list[VoiceProfile]:
        """Return all available voice profiles."""
        return list_voice_profiles()

    def available_voices(self) -> list[VoiceProfile]:
        """Alias for list_available_voices."""
        return self.list_available_voices()

    def set_speed(self, speed: float) -> float:
        """Set speech speed. Validates bounds between 0.5 and 2.0."""
        self._speed = self._validate_speed(speed)
        log.info(f"TTS speed set to {self._speed}")
        return self._speed

    def get_speed(self) -> float:
        """Return current speech speed."""
        return self._speed

    @property
    def speed(self) -> float:
        """Property for speech speed."""
        return self._speed


# Singleton instance
voice_manager = VoiceManager()
