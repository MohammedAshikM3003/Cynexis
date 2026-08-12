"""
CYNEXIS — Integration Tests for Kokoro TTS & Voice API
Tests actual local Kokoro model synthesis and FastAPI endpoints.
"""

import pytest
import io
import soundfile as sf
from httpx import AsyncClient, ASGITransport

from AI.TTS.kokoro import KokoroTTSProvider
from AI.TTS.audio_output import MockAudioOutput
from Backend.api.server import app


@pytest.mark.asyncio
async def test_kokoro_synthesis_all_locked_voices():
    """Verify local Kokoro synthesis for all 3 locked voices."""
    provider = KokoroTTSProvider(audio_output=MockAudioOutput())
    await provider.load()
    assert provider.is_loaded() is True

    test_voices = ["am_michael", "af_bella", "bm_lewis"]
    sample_text = "Hello everyone. I am CYNEXIS."

    for voice_id in test_voices:
        wav_bytes = await provider.synthesize(sample_text, voice=voice_id, speed=1.0)
        assert len(wav_bytes) > 1000, f"Synthesis output too small for voice {voice_id}"

        # Verify WAV format with soundfile
        audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes))
        assert sample_rate == 24000
        assert len(audio_data) > 0


@pytest.mark.asyncio
async def test_kokoro_dynamic_ai_response_synthesis():
    """Verify synthesis of arbitrary dynamic AI response text."""
    provider = KokoroTTSProvider(audio_output=MockAudioOutput())
    await provider.load()

    dynamic_text = (
        "I can monitor my systems, communicate with my sensors, "
        "capture images, and perform predefined robotic actions."
    )
    wav_bytes = await provider.synthesize(dynamic_text, voice="am_michael", speed=1.0)
    assert len(wav_bytes) > 2000

    audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes))
    assert sample_rate == 24000
    duration_s = len(audio_data) / sample_rate
    assert duration_s > 3.0  # Should be ~4-6 seconds of speech


@pytest.mark.asyncio
async def test_voice_api_endpoints():
    """Test voice status, list, select, and speak REST endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET /api/voice/status
        res = await ac.get("/api/voice/status")
        assert res.status_code == 200
        data = res.json()
        assert "current_voice" in data
        assert "enabled" in data

        # GET /api/voice/list
        res = await ac.get("/api/voice/list")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 3
        voice_ids = [v["id"] for v in data["voices"]]
        assert "am_michael" in voice_ids
        assert "af_bella" in voice_ids
        assert "bm_lewis" in voice_ids

        # POST /api/voice/select (valid)
        res = await ac.post("/api/voice/select", json={"voice": "af_bella"})
        assert res.status_code == 200
        assert res.json()["voice"]["name"] == "Bella"

        # POST /api/voice/select (invalid)
        res = await ac.post("/api/voice/select", json={"voice": "unknown_voice_xyz"})
        assert res.status_code == 400

        # POST /api/voice/speed (valid)
        res = await ac.post("/api/voice/speed", json={"speed": 1.1})
        assert res.status_code == 200

        # POST /api/voice/speed (out of range)
        res = await ac.post("/api/voice/speed", json={"speed": 5.0})
        assert res.status_code == 422 or res.status_code == 400

        # POST /api/voice/speak
        res = await ac.post(
            "/api/voice/speak",
            json={"text": "CYNEXIS voice test.", "voice": "am_michael", "play_local": False},
        )
        assert res.status_code == 200
        speak_data = res.json()
        assert speak_data["success"] is True
        assert speak_data["voice"] == "am_michael"
