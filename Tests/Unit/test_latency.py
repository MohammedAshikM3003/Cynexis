"""
CYNEXIS — Unit Tests for Low-Latency Real-Time Voice Optimization
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.constants import ActionName, SystemMode
from core.state import robot_state
from core.config import settings

from AI.pipeline import VoicePipeline, concat_wavs
from AI.STT.provider import MockSTTProvider
from AI.STT.microphone import MockMicrophone
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
    """Build a deterministic mock pipeline for low-latency testing."""
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
        return {"speech": "I am CYNEXIS, an autonomous robotic assistant."}

    async def mock_stop():
        return {"stopped": True}

    async def mock_forward(speed=150):
        return {"direction": "FORWARD", "speed": speed}

    actions.register(ActionDefinition(ActionName.HELLO, "Greet", mock_hello))
    actions.register(ActionDefinition(ActionName.INTRODUCE_SELF, "Intro", mock_intro))
    actions.register(ActionDefinition(ActionName.STOP, "Stop", mock_stop, allowed_modes=list(SystemMode)))
    actions.register(ActionDefinition(ActionName.FORWARD, "Forward", mock_forward))

    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent, memory=memory,
        actions=actions, safety=safety,
        microphone=mic,
    )
    return pipeline


@pytest.mark.asyncio
async def test_command_bypasses_llm(mock_pipeline):
    """Verify simple command bypasses LLM generation."""
    mock_pipeline.llm.stream = MagicMock()
    mock_pipeline.llm.generate = AsyncMock()

    result = await mock_pipeline.process_text("move forward")
    assert result["is_command"] is True
    assert mock_pipeline.llm.stream.call_count == 0
    assert mock_pipeline.llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_hello_bypasses_llm(mock_pipeline):
    """Verify HELLO action bypasses LLM generation."""
    mock_pipeline.llm.stream = MagicMock()
    mock_pipeline.llm.generate = AsyncMock()

    result = await mock_pipeline.process_text("CYNEXIS, say hello to everyone.")
    assert result["is_command"] is True
    assert result["action"] == "HELLO"
    assert mock_pipeline.llm.stream.call_count == 0
    assert mock_pipeline.llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_introduce_self_bypasses_llm(mock_pipeline):
    """Verify INTRODUCE_SELF action bypasses LLM generation."""
    mock_pipeline.llm.stream = MagicMock()
    mock_pipeline.llm.generate = AsyncMock()

    result = await mock_pipeline.process_text("introduce yourself")
    assert result["is_command"] is True
    assert result["action"] == "INTRODUCE_SELF"
    assert mock_pipeline.llm.stream.call_count == 0
    assert mock_pipeline.llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_stop_bypasses_llm(mock_pipeline):
    """Verify STOP action bypasses LLM generation."""
    mock_pipeline.llm.stream = MagicMock()
    mock_pipeline.llm.generate = AsyncMock()

    result = await mock_pipeline.process_text("stop")
    assert result["is_command"] is True
    assert result["action"] == "STOP"
    assert mock_pipeline.llm.stream.call_count == 0
    assert mock_pipeline.llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_conversation_invokes_llm(mock_pipeline):
    """Verify conversational query invokes LLM streaming."""
    # Mock LLM stream method to yield some chunks
    async def mock_stream(prompt, context=""):
        yield "I can "
        yield "help."

    mock_pipeline.llm.stream = mock_stream
    mock_pipeline.llm.generate = AsyncMock()

    result = await mock_pipeline.process_text("What can you do?")
    assert result["is_command"] is False
    assert result["action"] is None
    assert "I can help." in result["response"]


@pytest.mark.asyncio
async def test_sentence_chunking():
    """Verify that sentence chunker correctly splits token stream into sentences."""
    pipeline = VoicePipeline(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
    
    async def token_generator():
        yield "Hello "
        yield "world! "
        yield "This is a "
        yield "test. "
        yield "Yay."

    sentences = []
    async for s in pipeline._sentence_chunker(token_generator()):
        sentences.append(s)

    assert sentences == ["Hello world!", "This is a test.", "Yay."]
    if pipeline.playback_task:
        pipeline.playback_task.cancel()


@pytest.mark.asyncio
async def test_audio_queue_sequence(mock_pipeline):
    """Verify chunks are enqueued sequentially to the playback queue."""
    mock_pipeline.playback_queue = asyncio.Queue()  # clean queue
    text = "Hello world. This is a test. Yes."
    
    # We must ensure playback task is initialized to mock it
    mock_pipeline._ensure_playback_task()
    if mock_pipeline.playback_task:
        mock_pipeline.playback_task.cancel()

    wav_chunks, _ = await mock_pipeline._synthesize_and_queue_response(
        text, "am_michael", 1.0, {"latencies": {}}, 0.0, 0.0, play_local=True
    )
    
    assert len(wav_chunks) == 3
    assert mock_pipeline.playback_queue.qsize() == 3
    
    first = await mock_pipeline.playback_queue.get()
    assert first[0] == wav_chunks[0]
    assert first[1] is True


@pytest.mark.asyncio
async def test_speech_interruption_clears_queue(mock_pipeline):
    """Verify that stop_speech clears the queue and interrupts playback."""
    mock_pipeline.playback_queue = asyncio.Queue()
    await mock_pipeline.playback_queue.put((b"chunk1", True))
    await mock_pipeline.playback_queue.put((b"chunk2", True))
    
    assert mock_pipeline.playback_queue.qsize() == 2
    
    mock_pipeline.tts.stop = MagicMock()
    mock_pipeline.stop_speech()
    
    assert mock_pipeline.playback_queue.qsize() == 0
    mock_pipeline.tts.stop.assert_called_once()


@pytest.mark.asyncio
async def test_latency_metrics_measurement(mock_pipeline):
    """Verify that all pipeline latency metrics are measured and returned."""
    # Ensure mock pipeline streams
    async def mock_stream(prompt, context=""):
        yield "I can "
        yield "help."
    mock_pipeline.llm.stream = mock_stream
    
    result = await mock_pipeline.process_text("What can you do?")
    lat = result["latencies"]
    
    assert "speech_end" in lat
    assert "stt_complete" in lat
    assert "intent_complete" in lat
    assert "response_ready" in lat
    assert "tts_first_audio_ready" in lat
    assert "playback_started" in lat
    assert "stt_s" in lat
    assert "intent_s" in lat
    assert "llm_or_action_s" in lat
    assert "tts_first_chunk_s" in lat
    assert "tts_s" in lat
    assert "time_to_first_audio_s" in lat
    assert "total_s" in lat


@pytest.mark.asyncio
async def test_safety_remains_enforced(mock_pipeline):
    """Verify safety check blocks forbidden actions on command path."""
    robot_state.mode = SystemMode.EMERGENCY
    result = await mock_pipeline.process_text("move forward")
    assert result["is_command"] is True
    assert "Cannot execute" in result["response"]
    assert result["error"] is not None


def test_drift_strictly_absent():
    """Verify DRIFT action remains absent from constants."""
    assert not hasattr(ActionName, "DRIFT")


@pytest.mark.asyncio
async def test_no_overlapping_audio(mock_pipeline):
    """Verify that playback worker handles only one chunk at a time sequentially."""
    mock_pipeline.playback_queue = asyncio.Queue()
    mock_pipeline.tts.audio_output = MagicMock()
    mock_pipeline.tts.audio_output.play = AsyncMock()

    # Disable background worker to manually run one step
    mock_pipeline._ensure_playback_task()
    if mock_pipeline.playback_task:
        mock_pipeline.playback_task.cancel()
    
    await mock_pipeline.playback_queue.put((b"chunk1", True))
    await mock_pipeline.playback_queue.put((b"chunk2", True))
    
    # Process first
    item = await mock_pipeline.playback_queue.get()
    await mock_pipeline.tts.audio_output.play(item[0], sample_rate=24000)
    mock_pipeline.tts.audio_output.play.assert_called_once_with(b"chunk1", sample_rate=24000)
    
    # Process second
    item = await mock_pipeline.playback_queue.get()
    await mock_pipeline.tts.audio_output.play(item[0], sample_rate=24000)
    assert mock_pipeline.tts.audio_output.play.call_count == 2
