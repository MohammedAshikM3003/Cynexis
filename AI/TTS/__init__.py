"""
CYNEXIS — Text-to-Speech Subsystem
Exports TTS provider abstractions, Kokoro provider, VoiceManager, and audio outputs.
"""

from .provider import TTSProvider, MockTTSProvider
from .voices import (
    VoiceProfile,
    VOICE_PROFILES,
    DEFAULT_VOICE_ID,
    get_voice_profile,
    is_valid_voice,
    list_voice_profiles,
)
from .voice_manager import (
    VoiceManager,
    voice_manager,
    MIN_TTS_SPEED,
    MAX_TTS_SPEED,
    DEFAULT_TTS_SPEED,
)
from .audio_output import AudioOutput, MockAudioOutput, LocalAudioOutput
from .kokoro import KokoroTTSProvider

__all__ = [
    "TTSProvider",
    "MockTTSProvider",
    "KokoroTTSProvider",
    "VoiceProfile",
    "VOICE_PROFILES",
    "DEFAULT_VOICE_ID",
    "get_voice_profile",
    "is_valid_voice",
    "list_voice_profiles",
    "VoiceManager",
    "voice_manager",
    "MIN_TTS_SPEED",
    "MAX_TTS_SPEED",
    "DEFAULT_TTS_SPEED",
    "AudioOutput",
    "MockAudioOutput",
    "LocalAudioOutput",
]
