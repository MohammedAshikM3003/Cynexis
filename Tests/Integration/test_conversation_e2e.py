"""
CYNEXIS — Integration Tests for Conversational API Endpoints
Tests /api/conversation/text, /api/conversation/audio, /api/conversation/stop,
and /api/conversation/history with FastAPI TestClient.
"""

import pytest
import base64
from fastapi.testclient import TestClient

from core.config import settings
from Backend.api.server import app
from AI.STT.microphone import MockMicrophone


@pytest.fixture(scope="module")
def client():
    """Create test client with mock mode enabled."""
    settings.mock_mode = True
    with TestClient(app) as c:
        yield c


def test_conversation_text_greeting(client):
    """Test text conversation with greeting command."""
    response = client.post("/api/conversation/text", json={
        "text": "CYNEXIS, say hello to everyone.",
        "voice": "am_michael",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_command"] is True
    assert data["action"] == "HELLO"
    assert "Hello everyone. I am CYNEXIS." in data["response"]
    assert data["voice"] == "am_michael"
    assert "latencies" in data


def test_conversation_text_question(client):
    """Test text conversation with general question."""
    response = client.post("/api/conversation/text", json={
        "text": "What can you do?",
        "voice": "af_bella",
        "speed": 1.1,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_command"] is False
    assert data["action"] is None
    assert data["voice"] == "af_bella"
    assert data["speed"] == 1.1
    assert len(data["response"]) > 0


def test_conversation_text_invalid_voice(client):
    """Test error on invalid voice profile."""
    response = client.post("/api/conversation/text", json={
        "text": "Hello",
        "voice": "invalid_voice_xyz",
    })
    assert response.status_code == 400
    assert "Invalid voice" in response.json()["detail"]


def test_conversation_text_empty(client):
    """Test error on empty text."""
    response = client.post("/api/conversation/text", json={
        "text": "   ",
    })
    assert response.status_code == 400


def test_conversation_audio_endpoint(client):
    """Test /api/conversation/audio with mock base64 audio."""
    mock_audio = MockMicrophone._generate_mock_wav()
    b64_audio = base64.b64encode(mock_audio).decode("utf-8")

    response = client.post("/api/conversation/audio", json={
        "audio_base64": b64_audio,
        "voice": "bm_lewis",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["voice"] == "bm_lewis"
    assert len(data["response"]) > 0


def test_conversation_stop_endpoint(client):
    """Test /api/conversation/stop interrupts playback."""
    response = client.post("/api/conversation/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "stopped" in data["message"].lower()


def test_conversation_history_endpoint(client):
    """Test /api/conversation/history returns logged messages."""
    response = client.get("/api/conversation/history?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert isinstance(data["history"], list)
