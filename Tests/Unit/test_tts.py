"""
CYNEXIS — Unit Tests for TTS Subsystem
Tests VoiceManager, voice registry, text validation, speed validation,
MockTTS, and pipeline fault-tolerance without requiring full model download.
"""

import pytest
from core.config import settings
from AI.TTS.voices import (
    VOICE_PROFILES,
    is_valid_voice,
    get_voice_profile,
    list_voice_profiles,
    DEFAULT_VOICE_ID,
)
from AI.TTS.voice_manager import (
    VoiceManager,
    MIN_TTS_SPEED,
    MAX_TTS_SPEED,
    DEFAULT_TTS_SPEED,
)
from AI.TTS.provider import TTSProvider, MockTTSProvider
from AI.TTS.audio_output import MockAudioOutput
from AI.TTS.kokoro import KokoroTTSProvider


class TestVoiceRegistry:
    """Test voice registry definitions and lookup functions."""

    def test_voice_registry_contains_locked_cynexis_voices(self):
        """Verify the 3 locked CYNEXIS voices are present."""
        assert "am_michael" in VOICE_PROFILES
        assert "af_bella" in VOICE_PROFILES
        assert "bm_lewis" in VOICE_PROFILES

    def test_voice_profile_metadata(self):
        michael = VOICE_PROFILES["am_michael"]
        assert michael.name == "Michael"
        assert michael.provider == "kokoro"
        assert michael.gender == "male"
        assert michael.available is True

        bella = VOICE_PROFILES["af_bella"]
        assert bella.name == "Bella"
        assert bella.provider == "kokoro"
        assert bella.gender == "female"
        assert bella.available is True

        lewis = VOICE_PROFILES["bm_lewis"]
        assert lewis.name == "Lewis"
        assert lewis.provider == "kokoro"
        assert lewis.gender == "male"
        assert lewis.available is True

    def test_is_valid_voice(self):
        assert is_valid_voice("am_michael") is True
        assert is_valid_voice("af_bella") is True
        assert is_valid_voice("bm_lewis") is True
        assert is_valid_voice("random_voice_123") is False
        assert is_valid_voice("") is False

    def test_list_voice_profiles(self):
        profiles = list_voice_profiles()
        assert len(profiles) >= 3
        ids = [p.id for p in profiles]
        assert "am_michael" in ids
        assert "af_bella" in ids
        assert "bm_lewis" in ids


class TestVoiceManager:
    """Test VoiceManager active state, voice switching, and speed validation."""

    def test_default_voice_initialization(self):
        vm = VoiceManager(default_voice="am_michael")
        assert vm.get_current_voice() == "am_michael"
        assert vm.current_voice().name == "Michael"

    def test_voice_switching(self):
        vm = VoiceManager(default_voice="am_michael")
        vm.set_voice("af_bella")
        assert vm.get_current_voice() == "af_bella"
        assert vm.current_voice().name == "Bella"

        vm.set_voice("bm_lewis")
        assert vm.get_current_voice() == "bm_lewis"
        assert vm.current_voice().name == "Lewis"

    def test_invalid_voice_rejected(self):
        vm = VoiceManager(default_voice="am_michael")
        with pytest.raises(ValueError, match="Invalid voice ID"):
            vm.set_voice("non_existent_voice")
        # Ensure voice was not changed
        assert vm.get_current_voice() == "am_michael"

    def test_speed_validation_valid(self):
        vm = VoiceManager()
        assert vm.set_speed(1.0) == 1.0
        assert vm.set_speed(0.5) == 0.5
        assert vm.set_speed(2.0) == 2.0
        assert vm.set_speed(1.2) == 1.2
        assert vm.get_speed() == 1.2

    def test_speed_validation_out_of_bounds(self):
        vm = VoiceManager()
        with pytest.raises(ValueError, match="out of safe range"):
            vm.set_speed(0.1)
        with pytest.raises(ValueError, match="out of safe range"):
            vm.set_speed(5.0)
        with pytest.raises(ValueError, match="out of safe range"):
            vm.set_speed(-1.0)


class TestMockTTSProvider:
    """Test MockTTSProvider behavior."""

    @pytest.mark.asyncio
    async def test_mock_tts_lifecycle(self):
        provider = MockTTSProvider()
        assert provider.is_loaded() is False
        loaded = await provider.load()
        assert loaded is True
        assert provider.is_loaded() is True

        audio = await provider.speak("Hello world", voice="am_michael", speed=1.0)
        assert isinstance(audio, bytes)

        audio_synth = await provider.synthesize("Hello world")
        assert isinstance(audio_synth, bytes)

        await provider.unload()
        assert provider.is_loaded() is False


class TestKokoroTTSProviderUnit:
    """Unit tests for KokoroTTSProvider validation and instantiation without heavy inference."""

    def test_provider_instantiation(self):
        mock_output = MockAudioOutput()
        provider = KokoroTTSProvider(audio_output=mock_output)
        assert isinstance(provider, TTSProvider)
        assert provider.is_loaded() is False

    def test_text_validation_valid(self):
        mock_output = MockAudioOutput()
        provider = KokoroTTSProvider(audio_output=mock_output)
        clean = provider._validate_text("  Hello CYNEXIS  ")
        assert clean == "Hello CYNEXIS"

    def test_text_validation_empty_rejected(self):
        mock_output = MockAudioOutput()
        provider = KokoroTTSProvider(audio_output=mock_output)
        with pytest.raises(ValueError, match="Text cannot be empty"):
            provider._validate_text("")
        with pytest.raises(ValueError, match="Text cannot be empty"):
            provider._validate_text("   \n\t  ")

    def test_text_validation_oversized_rejected(self):
        mock_output = MockAudioOutput()
        provider = KokoroTTSProvider(audio_output=mock_output)
        long_text = "a" * 1001
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            provider._validate_text(long_text)

    def test_voice_and_speed_resolution(self):
        mock_output = MockAudioOutput()
        provider = KokoroTTSProvider(audio_output=mock_output)
        v, s = provider._resolve_voice_and_speed("af_bella", 1.2)
        assert v == "af_bella"
        assert s == 1.2

        with pytest.raises(ValueError, match="Unknown or invalid voice ID"):
            provider._resolve_voice_and_speed("invalid_voice")

        with pytest.raises(ValueError, match="out of safe range"):
            provider._resolve_voice_and_speed("am_michael", 9.9)


class TestPipelineTTSIntegration:
    """Test VoicePipeline handling of TTS and fault tolerance."""

    @pytest.mark.asyncio
    async def test_pipeline_with_mock_tts(self):
        from AI.pipeline import VoicePipeline
        from AI.STT.provider import MockSTTProvider
        from AI.LLM.provider import MockLLMProvider
        from AI.Intent.engine import intent_engine
        from AI.Memory.provider import MockMemoryProvider
        from AI.Actions.registry import registry
        from Backend.Robot.Safety.safety import safety

        pipeline = VoicePipeline(
            stt=MockSTTProvider(),
            tts=MockTTSProvider(),
            llm=MockLLMProvider(),
            intent=intent_engine,
            memory=MockMemoryProvider(),
            actions=registry,
            safety=safety,
        )

        result = await pipeline.process_text("CYNEXIS, say hello to everyone.")
        assert result["is_command"] is True
        assert result["action"] == "HELLO"
        assert "response" in result

    @pytest.mark.asyncio
    async def test_pipeline_survives_tts_failure(self):
        """TTS failure must not crash the robot pipeline."""
        from AI.pipeline import VoicePipeline
        from AI.STT.provider import MockSTTProvider
        from AI.LLM.provider import MockLLMProvider
        from AI.Intent.engine import intent_engine
        from AI.Memory.provider import MockMemoryProvider
        from AI.Actions.registry import registry
        from Backend.Robot.Safety.safety import safety

        class FailingTTS(TTSProvider):
            async def speak(self, text, voice=None, speed=None):
                raise RuntimeError("Simulated Audio Hardware / TTS Failure")
            async def synthesize(self, text, voice=None, speed=None):
                raise RuntimeError("Simulated Synthesis Failure")
            async def load(self): return True
            async def unload(self): pass
            def is_loaded(self): return True

        pipeline = VoicePipeline(
            stt=MockSTTProvider(),
            tts=FailingTTS(),
            llm=MockLLMProvider(),
            intent=intent_engine,
            memory=MockMemoryProvider(),
            actions=registry,
            safety=safety,
        )

        # Must complete cleanly without raising unhandled exception
        result = await pipeline.process_text("CYNEXIS, say hello to everyone.")
        assert result["is_command"] is True
        assert result["action"] == "HELLO"
