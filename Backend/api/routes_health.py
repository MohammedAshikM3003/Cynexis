"""
CYNEXIS — Health & Diagnostics Routes
GET /health, GET /api/diagnostics
"""

from fastapi import APIRouter, Request
from core.constants import CYNEXIS_VERSION
from core.config import settings
from core.state import robot_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "ok",
        "name": settings.cynexis_name,
        "version": CYNEXIS_VERSION,
        "mock_mode": settings.mock_mode,
    }


@router.get("/api/diagnostics")
async def diagnostics(request: Request):
    """Full system diagnostics."""
    robot_state.update_uptime()
    results = {
        "version": CYNEXIS_VERSION,
        "environment": settings.environment,
        "mock_mode": settings.mock_mode,
        "uptime_s": round(robot_state.uptime_s, 1),
        "subsystems": {
            "database": "ok",  # If we got here, DB is working
            "rover": "mock" if settings.mock_mode else robot_state.connection.value
                     if hasattr(robot_state.connection, 'value') else str(robot_state.connection),
            "arm": "mock" if settings.mock_mode else "unknown",
            "gripper": "mock" if settings.mock_mode else "unknown",
            "camera": "active" if robot_state.camera.is_active else "inactive",
            "ai_llm": "loaded" if robot_state.ai.llm_loaded else "not_loaded",
            "ai_stt": "loaded" if robot_state.ai.stt_loaded else "not_loaded",
            "ai_tts": "loaded" if robot_state.ai.tts_loaded else "not_loaded",
            "intent": "ready" if robot_state.ai.intent_ready else "not_ready",
            "network": "online" if robot_state.network.internet_available else "offline",
        },
        "features": {
            "camera_enabled": settings.camera_enabled,
            "voice_enabled": settings.voice_enabled,
            "ai_enabled": settings.ai_enabled,
            "sync_enabled": settings.sync_enabled,
        },
    }
    return results
