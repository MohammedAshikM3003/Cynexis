"""
CYNEXIS — Conversational API Routes
Endpoints for full end-to-end conversation processing, speech stopping, and history.
"""

import base64
import time
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field

from core.logger import get_logger
from core.config import settings
from AI.TTS.voice_manager import voice_manager, is_valid_voice, MIN_TTS_SPEED, MAX_TTS_SPEED
from AI.TTS.voices import list_voice_profiles

log = get_logger("routes_conversation")
router = APIRouter(prefix="/conversation", tags=["Conversational AI"])


class TextConversationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Input text from user")
    voice: Optional[str] = Field(default=None, description="Optional override voice ID")
    speed: Optional[float] = Field(default=None, ge=MIN_TTS_SPEED, le=MAX_TTS_SPEED, description="Speech speed")
    play_local: Optional[bool] = Field(default=None, description="Whether to play audio via speaker")


class AudioConversationRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio WAV/PCM bytes")
    voice: Optional[str] = Field(default=None, description="Optional override voice ID")
    speed: Optional[float] = Field(default=None, ge=MIN_TTS_SPEED, le=MAX_TTS_SPEED, description="Speech speed")
    play_local: Optional[bool] = Field(default=None, description="Whether to play audio via speaker")


@router.post("/text")
async def process_text_conversation(payload: TextConversationRequest, request: Request):
    """
    Process text input through the full pipeline:
    Intent Engine → Safety / Action Registry OR LLM → Kokoro TTS → Output.
    """
    clean_text = payload.text.strip()
    if not clean_text:
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

    pipeline = getattr(request.app.state, "pipeline", None)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VoicePipeline is not initialized on server",
        )

    try:
        pipeline_result = await pipeline.process_text(
            clean_text,
            voice=voice_id,
            speed=payload.speed,
            play_local=payload.play_local,
        )

        audio_bytes = pipeline_result.get("audio_bytes", b"")
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else ""
        duration_s = (len(audio_bytes) / 48000.0) if audio_bytes else 0.0

        return {
            "success": pipeline_result.get("error") is None,
            "recognized_text": pipeline_result.get("text", clean_text),
            "is_command": pipeline_result.get("is_command", False),
            "action": pipeline_result.get("action"),
            "action_result": pipeline_result.get("action_result"),
            "intent": pipeline_result.get("action") if pipeline_result.get("is_command") else "CONVERSATION",
            "response": pipeline_result.get("response", ""),
            "voice": pipeline_result.get("voice", voice_id),
            "speed": pipeline_result.get("speed", 1.0),
            "tts_provider": pipeline_result.get("tts_provider", "kokoro"),
            "duration_s": round(duration_s, 2),
            "latencies": pipeline_result.get("latencies", {}),
            "audio_base64": audio_b64,
            "error": pipeline_result.get("error"),
        }
    except Exception as e:
        log.error(f"Error in /conversation/text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation processing failed: {e}",
        )


@router.post("/audio")
async def process_audio_conversation(payload: AudioConversationRequest, request: Request):
    """
    Process raw audio bytes through the full pipeline:
    STT → Intent Engine → Safety / Action Registry OR LLM → Kokoro TTS.
    """
    try:
        audio_bytes = base64.b64decode(payload.audio_base64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 audio data: {e}",
        )

    pipeline = getattr(request.app.state, "pipeline", None)
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VoicePipeline is not initialized on server",
        )

    voice_id = payload.voice or voice_manager.get_current_voice()
    if not is_valid_voice(voice_id):
        valid = [p.id for p in list_voice_profiles()]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid voice '{voice_id}'. Available voices: {valid}",
        )

    try:
        pipeline_result = await pipeline.process_audio(
            audio_data=audio_bytes,
            voice=voice_id,
            speed=payload.speed,
            play_local=payload.play_local,
        )

        out_audio = pipeline_result.get("audio_bytes", b"")
        audio_b64 = base64.b64encode(out_audio).decode("utf-8") if out_audio else ""
        duration_s = (len(out_audio) / 48000.0) if out_audio else 0.0

        return {
            "success": pipeline_result.get("error") is None,
            "recognized_text": pipeline_result.get("text", ""),
            "is_command": pipeline_result.get("is_command", False),
            "action": pipeline_result.get("action"),
            "action_result": pipeline_result.get("action_result"),
            "intent": pipeline_result.get("action") if pipeline_result.get("is_command") else "CONVERSATION",
            "response": pipeline_result.get("response", ""),
            "voice": pipeline_result.get("voice", voice_id),
            "speed": pipeline_result.get("speed", 1.0),
            "tts_provider": pipeline_result.get("tts_provider", "kokoro"),
            "duration_s": round(duration_s, 2),
            "latencies": pipeline_result.get("latencies", {}),
            "audio_base64": audio_b64,
            "error": pipeline_result.get("error"),
        }
    except Exception as e:
        log.error(f"Error in /conversation/audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio conversation processing failed: {e}",
        )


@router.post("/stop")
async def stop_conversation_speech(request: Request):
    """
    Preemptively stop active speech playback.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline:
        pipeline.stop_speech()
    return {"success": True, "message": "Speech playback stopped"}


@router.get("/history")
async def get_conversation_history(request: Request, limit: int = 10):
    """
    Get recent conversation history from memory.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if not pipeline or not pipeline.memory:
        return {"history": []}

    try:
        history = await pipeline.memory.get_conversation_history(limit=limit)
        return {"history": history, "count": len(history)}
    except Exception as e:
        log.error(f"Error fetching conversation history: {e}")
        return {"history": [], "error": str(e)}


# ── LLM Status & Test Endpoints ───────────────────────────────────────────────

llm_router = APIRouter(prefix="/llm", tags=["LLM"])


@llm_router.get("/status")
async def get_llm_status(request: Request):
    """
    Return the current LLM provider status and last-inference telemetry.
    """
    pipeline = getattr(request.app.state, "pipeline", None)
    if not pipeline or not pipeline.llm:
        return {
            "provider": "none",
            "status": "NOT_INITIALIZED",
            "telemetry": {},
        }

    llm = pipeline.llm
    provider_name = type(llm).__name__
    telemetry = llm.llm_telemetry if hasattr(llm, "llm_telemetry") else {}

    health = {}
    try:
        health = await llm.health_check()
    except Exception as e:
        health = {"ok": False, "error": str(e)}

    return {
        "provider": provider_name,
        "loaded": llm.is_loaded(),
        "status": health.get("status", "UNKNOWN"),
        "model": getattr(llm, "_model", "mock"),
        "base_url": getattr(llm, "_base_url", None),
        "health": health,
        "telemetry": telemetry,
    }


@llm_router.get("/model")
async def get_llm_model(request: Request):
    """
    Return information about the currently configured LLM model.
    """
    from core.config import settings

    pipeline = getattr(request.app.state, "pipeline", None)
    model_name = getattr(settings, "ollama_model", "mock")
    if pipeline and hasattr(pipeline.llm, "_model"):
        model_name = pipeline.llm._model

    # Try to get model details from Ollama
    try:
        import httpx
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base_url}/api/tags")
            if r.status_code == 200:
                models = r.json().get("models", [])
                for m in models:
                    if m.get("name", "").startswith(model_name.split(":")[0]):
                        details = m.get("details", {})
                        return {
                            "model": m.get("name"),
                            "size_bytes": m.get("size"),
                            "parameter_size": details.get("parameter_size"),
                            "quantization": details.get("quantization_level"),
                            "context_length": details.get("context_length"),
                            "family": details.get("family"),
                            "capabilities": m.get("capabilities", []),
                        }
    except Exception as e:
        log.warning(f"Could not fetch model details from Ollama: {e}")

    return {"model": model_name, "status": "details_unavailable"}


class LLMTestRequest(BaseModel):
    prompt: str = Field(default="What is CYNEXIS?", max_length=500)


@llm_router.post("/test")
async def test_llm_inference(payload: LLMTestRequest, request: Request):
    """
    Run a single LLM inference and return the response with telemetry.
    Useful for benchmarking and verifying the real LLM is responding.
    """
    import time

    pipeline = getattr(request.app.state, "pipeline", None)
    if not pipeline or not pipeline.llm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM pipeline is not initialized",
        )

    t0 = time.time()
    try:
        response = await pipeline.llm.generate(payload.prompt, context="")
        elapsed = time.time() - t0
        telemetry = pipeline.llm.llm_telemetry if hasattr(pipeline.llm, "llm_telemetry") else {}
        return {
            "prompt": payload.prompt,
            "response": response,
            "model": getattr(pipeline.llm, "_model", "mock"),
            "elapsed_s": round(elapsed, 3),
            "telemetry": telemetry,
        }
    except Exception as e:
        log.error(f"LLM test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM test failed: {e}",
        )

