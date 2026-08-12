"""
CYNEXIS — Voice API Routes
Endpoints for status, voice selection, synthesis, and voice test laboratory.
"""

import base64
import time
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.config import settings
from core.state import robot_state
from AI.TTS.voices import list_voice_profiles, is_valid_voice, get_voice_profile
from AI.TTS.voice_manager import voice_manager, MIN_TTS_SPEED, MAX_TTS_SPEED

log = get_logger("routes_voice")
router = APIRouter(prefix="/voice", tags=["Voice & TTS"])


class VoiceSelectRequest(BaseModel):
    voice: str = Field(..., description="Voice identifier, e.g. 'am_michael', 'af_bella', 'bm_lewis'")


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=MIN_TTS_SPEED, le=MAX_TTS_SPEED, description="Speech speed factor (0.5 - 2.0)")


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize")
    voice: Optional[str] = Field(default=None, description="Optional override voice ID")
    speed: Optional[float] = Field(default=None, ge=MIN_TTS_SPEED, le=MAX_TTS_SPEED, description="Optional speed override")
    play_local: Optional[bool] = Field(default=None, description="Whether to play audio via laptop/robot speaker")


@router.get("/status")
async def get_voice_status(request: Request):
    """
    Get current voice and TTS status.
    """
    tts = getattr(request.app.state, "tts", None)
    # Derive real provider name from the TTS instance class, not just config.
    # This prevents mock_mode from incorrectly labelling real Kokoro as 'mock'.
    backend = "unknown"
    if tts is not None:
        cls = type(tts).__name__
        if 'Kokoro' in cls:
            provider_name = 'kokoro'
            backend = getattr(tts, 'backend', 'pytorch')
        elif 'Mock' in cls:
            provider_name = 'mock'
            backend = 'mock'
        else:
            provider_name = cls.lower().replace('ttsprovider', '')
    else:
        provider_name = getattr(settings, "tts_provider", "kokoro")

    is_loaded = tts.is_loaded() if tts else False
    current_profile = voice_manager.current_voice()

    return {
        "provider": provider_name,
        "enabled": getattr(settings, "tts_enabled", True),
        "current_voice": current_profile.id,
        "current_voice_name": current_profile.name,
        "speed": voice_manager.get_speed(),
        "available": True,
        "model_loaded": is_loaded,
        "is_speaking": robot_state.voice.is_speaking,
        "last_utterance": robot_state.voice.last_utterance,
        "last_response": robot_state.voice.last_response,
    }


@router.get("/list")
async def get_voice_list():
    """
    List all available Kokoro voices.
    """
    profiles = list_voice_profiles()
    return {
        "voices": [p.model_dump() for p in profiles],
        "current_voice": voice_manager.get_current_voice(),
        "total": len(profiles),
    }


@router.post("/select")
async def select_voice(payload: VoiceSelectRequest):
    """
    Select active voice profile. Rejects invalid IDs.
    """
    if not is_valid_voice(payload.voice):
        valid = [p.id for p in list_voice_profiles()]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice '{payload.voice}'. Available voices: {valid}",
        )

    try:
        profile = voice_manager.set_voice(payload.voice)
        return {
            "success": True,
            "message": f"Voice set to {profile.name} ({profile.id})",
            "voice": profile.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/speed")
async def set_speech_speed(payload: SpeedRequest):
    """
    Set speech playback speed factor.
    """
    try:
        new_speed = voice_manager.set_speed(payload.speed)
        return {
            "success": True,
            "speed": new_speed,
            "message": f"TTS speed updated to {new_speed}x",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/speak")
async def speak_text(payload: SpeakRequest, request: Request):
    """
    Synthesize text to speech using configured provider.
    Returns audio metadata and base64 WAV data for web playback.
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty or whitespace only",
        )

    voice_id = payload.voice or voice_manager.get_current_voice()
    if not is_valid_voice(voice_id):
        valid = [p.id for p in list_voice_profiles()]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice '{voice_id}'. Available voices: {valid}",
        )

    tts = getattr(request.app.state, "tts", None)
    if not tts:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS provider is not initialized on server",
        )

    speed = payload.speed if payload.speed is not None else voice_manager.get_speed()
    play_local = payload.play_local if payload.play_local is not None else getattr(settings, "tts_play_local", False)

    try:
        t0 = time.time()
        if play_local:
            wav_bytes = await tts.speak(text, voice=voice_id, speed=speed)
        else:
            wav_bytes = await tts.synthesize(text, voice=voice_id, speed=speed)
        elapsed_s = time.time() - t0

        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8") if wav_bytes else ""
        duration_s = (len(wav_bytes) / 48000.0) if wav_bytes else 0.0

        return {
            "success": True,
            "text": text,
            "voice": voice_id,
            "speed": speed,
            "audio_bytes_len": len(wav_bytes),
            "duration_s": round(duration_s, 2),
            "synthesis_time_s": round(elapsed_s, 3),
            "played_local": play_local,
            "audio_base64": audio_b64,
        }
    except Exception as e:
        log.error(f"Error in /voice/speak endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS synthesis failed: {e}",
        )


@router.get("/wav")
async def stream_wav(text: str, voice: Optional[str] = None, speed: Optional[float] = 1.0, request: Request = None):
    """
    Direct WAV stream endpoint for HTML5 <audio> elements.
    """
    clean_text = text.strip() if text else ""
    if not clean_text:
        raise HTTPException(status_code=400, detail="Query parameter 'text' is required")

    voice_id = voice or voice_manager.get_current_voice()
    if not is_valid_voice(voice_id):
        raise HTTPException(status_code=400, detail=f"Invalid voice '{voice_id}'")

    tts = getattr(request.app.state, "tts", None) if request else None
    if not tts:
        raise HTTPException(status_code=503, detail="TTS provider not available")

    wav_bytes = await tts.synthesize(clean_text, voice=voice_id, speed=speed or 1.0)
    return Response(content=wav_bytes, media_type="audio/wav")
