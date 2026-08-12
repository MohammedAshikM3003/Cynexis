"""
CYNEXIS — Unit Tests for local offline Faster-Whisper STT
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from core.state import robot_state
from core.config import settings
from AI.STT.whisper import WhisperSTTProvider
from AI.STT.microphone import MockMicrophone


@pytest.fixture
def clean_whisper_settings():
    """Temporarily override settings to use a tiny model for fast testing."""
    old_model = getattr(settings, "stt_whisper_model", "base.en")
    old_provider = getattr(settings, "stt_provider", "mock")
    settings.stt_whisper_model = "tiny.en"
    settings.stt_provider = "whisper"
    yield
    settings.stt_whisper_model = old_model
    settings.stt_provider = old_provider


@pytest.mark.asyncio
async def test_whisper_provider_lifecycle(clean_whisper_settings):
    """Test loading, transcribing silence, and unloading Faster-Whisper."""
    provider = WhisperSTTProvider()
    assert provider.is_loaded() is False

    # Load model
    success = await provider.load()
    assert success is True
    assert provider.is_loaded() is True
    assert robot_state.ai.stt_loaded is True

    # Generate mono silent WAV bytes
    silent_wav = MockMicrophone._generate_mock_wav(sample_rate=16000, duration_s=1.0)
    
    # Transcribe silence
    text = await provider.transcribe(silent_wav)
    # Silence transcription should result in empty or noise-filtered empty string
    assert isinstance(text, str)
    
    # Unload model
    await provider.unload()
    assert provider.is_loaded() is False
    assert robot_state.ai.stt_loaded is False


@pytest.mark.asyncio
async def test_whisper_transcribe_empty_input(clean_whisper_settings):
    """Test Whisper provider returns empty string on empty input without crashing."""
    provider = WhisperSTTProvider()
    
    # Transcribing empty bytes
    result = await provider.transcribe(b"")
    assert result == ""
