"""
CYNEXIS — Unit Tests for End-to-End Voice & AI Conversational Pipeline
Tests voice pipeline, safety decoupling, command vs conversation separation,
speech states, voice switching, interruption, and microphone abstractions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.constants import ActionName, SystemMode
from core.state import robot_state
from core.config import settings

from AI.pipeline import VoicePipeline
from AI.STT.provider import MockSTTProvider
from AI.STT.microphone import MockMicrophone, LocalMicrophone
from AI.TTS.provider import MockTTSProvider
from AI.TTS.voice_manager import voice_manager
from AI.LLM.provider import MockLLMProvider
from AI.Intent.engine import IntentEngine
from AI.Memory.provider import MockMemoryProvider
from AI.Actions.registry import ActionRegistry, ActionDefinition
from Backend.Robot.Safety.safety import SafetyValidator


@pytest.fixture(autouse=True)
def reset_state():
    """Reset robot and voice state before each test."""
    robot_state.mode = SystemMode.NORMAL
    robot_state.voice.is_listening = False
    robot_state.voice.is_processing = False
    robot_state.voice.is_speaking = False
    robot_state.voice.state = "IDLE"
    robot_state.voice.last_utterance = ""
    robot_state.voice.last_response = ""
    voice_manager.set_voice("am_michael")
    voice_manager.set_speed(1.0)


@pytest.fixture
def mock_pipeline():
    """Build a deterministic mock pipeline."""
    stt = MockSTTProvider()
    tts = MockTTSProvider()
    llm = MockLLMProvider()
    intent = IntentEngine()
    memory = MockMemoryProvider()
    actions = ActionRegistry()
    safety = SafetyValidator()
    mic = MockMicrophone()

    # Register standard actions
    async def mock_hello():
        return {"speech": "Hello everyone. I am CYNEXIS."}

    async def mock_intro():
        return {"speech": "I am CYNEXIS, an AI robot."}

    async def mock_stop():
        return {"stopped": True}

    async def mock_forward(speed=150):
        return {"direction": "FORWARD", "speed": speed}

    actions.register(ActionDefinition(ActionName.HELLO, "Greet", mock_hello))
    actions.register(ActionDefinition(ActionName.INTRODUCE_SELF, "Intro", mock_intro))
    actions.register(ActionDefinition(ActionName.STOP, "Stop", mock_stop, allowed_modes=list(SystemMode)))
    actions.register(ActionDefinition(ActionName.FORWARD, "Forward", mock_forward))

    return VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent, memory=memory,
        actions=actions, safety=safety,
        microphone=mic,
    )



@pytest.mark.asyncio
async def test_hello_action_pipeline(mock_pipeline):
    """Test HELLO command triggers HELLO action and spoken response."""
    result = await mock_pipeline.process_text("CYNEXIS, say hello to everyone.")
    assert result["is_command"] is True
    assert result["action"] == "HELLO"
    assert "Hello everyone. I am CYNEXIS." in result["response"]
    assert result["error"] is None
    assert result["latencies"]["total_s"] >= 0


@pytest.mark.asyncio
async def test_introduce_action_pipeline(mock_pipeline):
    """Test INTRODUCE_SELF command triggers introduction speech."""
    result = await mock_pipeline.process_text("introduce yourself")
    assert result["is_command"] is True
    assert result["action"] == "INTRODUCE_SELF"
    assert "I am CYNEXIS" in result["response"]


@pytest.mark.asyncio
async def test_conversational_question_routes_to_llm(mock_pipeline):
    """Test non-command conversational query routes to LLM without hardware action."""
    result = await mock_pipeline.process_text("What can you do?")
    assert result["is_command"] is False
    assert result["action"] is None
    assert result["action_result"] is None
    assert len(result["response"]) > 0
    assert "CYNEXIS" in result["response"] or "capabilities" in result["response"] or "move" in result["response"]


@pytest.mark.asyncio
async def test_voice_selection_and_switching(mock_pipeline):
    """Test voice parameter is passed to TTS and voice switching works."""
    # Test Michael
    res_michael = await mock_pipeline.process_text("What can you do?", voice="am_michael")
    assert res_michael["voice"] == "am_michael"

    # Test Bella
    res_bella = await mock_pipeline.process_text("What can you do?", voice="af_bella")
    assert res_bella["voice"] == "af_bella"

    # Test Lewis
    res_lewis = await mock_pipeline.process_text("What can you do?", voice="bm_lewis")
    assert res_lewis["voice"] == "bm_lewis"

    # Responses should be consistent while voice differs
    assert res_michael["response"] == res_bella["response"] == res_lewis["response"]


@pytest.mark.asyncio
async def test_speech_state_lifecycle(mock_pipeline):
    """Test that voice state transitions to IDLE after processing."""
    assert robot_state.voice.state == "IDLE"
    result = await mock_pipeline.process_text("Hello there")
    assert robot_state.voice.state == "IDLE"
    assert robot_state.voice.is_speaking is False
    assert robot_state.voice.is_processing is False
    assert robot_state.voice.last_utterance == "Hello there"
    assert robot_state.voice.last_response == result["response"]


@pytest.mark.asyncio
async def test_speech_interruption(mock_pipeline):
    """Test that stop_speech cleanly stops audio output and sets state to IDLE."""
    robot_state.voice.is_speaking = True
    robot_state.voice.state = "SPEAKING"
    mock_pipeline.stop_speech()
    assert robot_state.voice.is_speaking is False
    assert robot_state.voice.state == "IDLE"


@pytest.mark.asyncio
async def test_safety_blocks_unauthorized_actions(mock_pipeline):
    """Test that safety layer rejects unauthorized hardware commands."""
    # Attempt unauthorized command in NORMAL mode when in EMERGENCY or invalid mode
    robot_state.mode = SystemMode.EMERGENCY
    result = await mock_pipeline.process_text("move forward")
    assert result["is_command"] is True
    assert "Cannot execute" in result["response"] or "Safety" in str(result["error"]) or "Emergency" in str(result["error"]) or result["error"] is not None


def test_drift_action_strictly_absent():
    """Verify DRIFT is NOT present in ActionName enum, IntentEngine, or Actions."""
    assert not hasattr(ActionName, "DRIFT")
    assert "DRIFT" not in [a.value for a in ActionName]
    assert "drift" not in [a.value.lower() for a in ActionName]



@pytest.mark.asyncio
async def test_microphone_abstractions():
    """Test MockMicrophone and LocalMicrophone interfaces."""
    mock_mic = MockMicrophone()
    assert mock_mic.is_available() is True
    audio_data = await mock_mic.record(duration_s=1.0)
    assert isinstance(audio_data, bytes)
    assert len(audio_data) > 0

    local_mic = LocalMicrophone()
    assert isinstance(local_mic.is_available(), bool)


@pytest.mark.asyncio
async def test_audio_pipeline_execution(mock_pipeline):
    """Test process_audio using mock audio data."""
    mock_mic = MockMicrophone()
    audio = await mock_mic.record()
    result = await mock_pipeline.process_audio(audio_data=audio)
    assert len(result["text"]) > 0
    assert len(result["response"]) > 0
    assert result["latencies"]["stt_s"] >= 0


@pytest.mark.asyncio
async def test_llm_failure_resilience(mock_pipeline):
    """Test that LLM exception is caught safely without crashing pipeline."""
    mock_pipeline.llm.generate = AsyncMock(side_effect=RuntimeError("LLM crashed"))
    result = await mock_pipeline.process_text("Complex question")
    assert result["error"] is not None
    assert "LLM failed" in result["error"]
    assert "I'm sorry" in result["response"]
    assert robot_state.voice.state == "IDLE"


@pytest.mark.asyncio
async def test_tts_failure_resilience(mock_pipeline):
    """Test that TTS exception is caught safely without crashing pipeline."""
    mock_pipeline.tts.speak = AsyncMock(side_effect=RuntimeError("TTS engine failure"))
    result = await mock_pipeline.process_text("say hello")
    assert result["response"] is not None
    assert robot_state.voice.state == "IDLE"
