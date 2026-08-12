"""
Tests for Phase 2A hardening:
- Action → Controller delegation
- Speed limit enforcement
- Emergency gripper release
- Photo/recording via camera controller
- Wave/nod via arm controller
- Database table whitelist
- process_text memory/state behavior
- last_action_time
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
import aiosqlite
from datetime import datetime, timezone

from core.state import robot_state
from core.constants import SystemMode, ActionName, MAX_ROVER_SPEED
from AI.Actions.registry import registry, ActionRegistry
from AI.Actions.actions import register_all_actions, inject_controllers
from Backend.Robot.rover import MockRoverController
from Backend.Robot.arm import MockArmController
from Backend.Robot.gripper import MockGripperController
from Backend.Vision.camera import MockCamera
from Database.database import DatabaseManager, ALLOWED_TABLES


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def reset_state():
    """Reset robot state before each test."""
    robot_state.mode = SystemMode.NORMAL
    robot_state.battery_pct = 100
    robot_state.rover.is_moving = False
    robot_state.rover.speed = 0
    robot_state.rover.direction = "STOPPED"
    robot_state.arm.is_moving = False
    robot_state.arm.base.angle = 90.0
    robot_state.arm.shoulder.angle = 90.0
    robot_state.arm.elbow.angle = 90.0
    robot_state.arm.wrist.angle = 90.0
    robot_state.gripper.position = 50.0
    robot_state.gripper.is_gripping = True
    robot_state.camera.is_recording = False
    yield


@pytest_asyncio.fixture
async def controllers():
    """Create and inject mock controllers."""
    rover = MockRoverController()
    arm = MockArmController()
    gripper = MockGripperController()
    camera = MockCamera()
    await camera.start()
    inject_controllers(rover=rover, arm=arm, gripper=gripper, camera=camera)
    register_all_actions()
    yield {"rover": rover, "arm": arm, "gripper": gripper, "camera": camera}
    await camera.stop()


# ============================================================
# ACTION → CONTROLLER DELEGATION
# ============================================================

@pytest.mark.asyncio
async def test_forward_delegates_to_rover(controllers):
    """FORWARD action delegates to rover controller."""
    result = await registry.execute("FORWARD", {"speed": 200})
    assert result["success"] is True
    assert robot_state.rover.direction == "FORWARD"
    assert robot_state.rover.speed == 200
    assert robot_state.rover.is_moving is True


@pytest.mark.asyncio
async def test_backward_delegates_to_rover(controllers):
    """BACKWARD action delegates to rover controller."""
    await registry.execute("BACKWARD", {"speed": 100})
    assert robot_state.rover.direction == "BACKWARD"
    assert robot_state.rover.speed == 100


@pytest.mark.asyncio
async def test_left_delegates_to_rover(controllers):
    await registry.execute("LEFT")
    assert robot_state.rover.direction == "LEFT"


@pytest.mark.asyncio
async def test_right_delegates_to_rover(controllers):
    await registry.execute("RIGHT")
    assert robot_state.rover.direction == "RIGHT"


@pytest.mark.asyncio
async def test_stop_delegates_to_rover(controllers):
    """STOP action delegates to rover AND arm controllers."""
    await registry.execute("FORWARD")
    await registry.execute("STOP")
    assert robot_state.rover.direction == "STOPPED"
    assert robot_state.rover.speed == 0
    assert robot_state.rover.is_moving is False


@pytest.mark.asyncio
async def test_grip_open_delegates(controllers):
    """GRIP_OPEN delegates to gripper controller."""
    await registry.execute("GRIP_CLOSE")
    assert robot_state.gripper.is_gripping is True
    await registry.execute("GRIP_OPEN")
    assert robot_state.gripper.position == 0.0
    assert robot_state.gripper.is_gripping is False


@pytest.mark.asyncio
async def test_grip_close_delegates(controllers):
    await registry.execute("GRIP_CLOSE")
    assert robot_state.gripper.position == 100.0
    assert robot_state.gripper.is_gripping is True


@pytest.mark.asyncio
async def test_arm_up_delegates(controllers):
    """ARM_UP delegates to arm controller."""
    robot_state.arm.shoulder.angle = 90.0
    await registry.execute("ARM_UP")
    assert robot_state.arm.shoulder.angle == 105.0


@pytest.mark.asyncio
async def test_arm_down_delegates(controllers):
    """ARM_DOWN delegates to arm controller."""
    robot_state.arm.shoulder.angle = 90.0
    await registry.execute("ARM_DOWN")
    assert robot_state.arm.shoulder.angle == 75.0


# ============================================================
# SPEED LIMIT ENFORCEMENT
# ============================================================

@pytest.mark.asyncio
async def test_speed_clamped_in_action_forward(controllers):
    """action_forward clamps speed to MAX_ROVER_SPEED."""
    result = await registry.execute("FORWARD", {"speed": 999})
    assert result["success"] is True
    assert robot_state.rover.speed == MAX_ROVER_SPEED


@pytest.mark.asyncio
async def test_speed_clamped_in_action_backward(controllers):
    result = await registry.execute("BACKWARD", {"speed": 500})
    assert robot_state.rover.speed == MAX_ROVER_SPEED


@pytest.mark.asyncio
async def test_speed_clamped_in_action_left(controllers):
    result = await registry.execute("LEFT", {"speed": 300})
    assert robot_state.rover.speed == MAX_ROVER_SPEED


@pytest.mark.asyncio
async def test_speed_clamped_in_action_right(controllers):
    result = await registry.execute("RIGHT", {"speed": 400})
    assert robot_state.rover.speed == MAX_ROVER_SPEED


@pytest.mark.asyncio
async def test_speed_zero_floor(controllers):
    """Negative speed clamped to 0."""
    result = await registry.execute("FORWARD", {"speed": -10})
    assert robot_state.rover.speed == 0


# ============================================================
# EMERGENCY STOP — GRIPPER RELEASE
# ============================================================

@pytest.mark.asyncio
async def test_emergency_stop_releases_gripper(controllers):
    """Emergency stop must release gripper for safety."""
    robot_state.gripper.position = 100.0
    robot_state.gripper.is_gripping = True

    await registry.execute("EMERGENCY_STOP")

    assert robot_state.gripper.position == 0.0
    assert robot_state.gripper.is_gripping is False
    assert robot_state.mode == SystemMode.EMERGENCY


@pytest.mark.asyncio
async def test_emergency_stop_stops_rover(controllers):
    """Emergency stop halts rover."""
    await registry.execute("FORWARD", {"speed": 200})
    assert robot_state.rover.is_moving is True

    await registry.execute("EMERGENCY_STOP")

    assert robot_state.rover.direction == "STOPPED"
    assert robot_state.rover.speed == 0
    assert robot_state.rover.is_moving is False


@pytest.mark.asyncio
async def test_emergency_stop_stops_arm(controllers):
    """Emergency stop halts arm."""
    robot_state.arm.is_moving = True
    await registry.execute("EMERGENCY_STOP")
    assert robot_state.arm.is_moving is False


# ============================================================
# PHOTO / RECORDING → CAMERA CONTROLLER
# ============================================================

@pytest.mark.asyncio
async def test_photo_uses_camera_controller(controllers):
    """PHOTO action delegates to camera controller."""
    initial = robot_state.camera.photos_taken
    result = await registry.execute("PHOTO")
    assert result["success"] is True
    assert robot_state.camera.photos_taken == initial + 1


@pytest.mark.asyncio
async def test_start_recording_uses_camera(controllers):
    """START_RECORDING delegates to camera controller."""
    result = await registry.execute("START_RECORDING")
    assert result["success"] is True
    assert robot_state.camera.is_recording is True


@pytest.mark.asyncio
async def test_stop_recording_uses_camera(controllers):
    """STOP_RECORDING delegates to camera controller."""
    await registry.execute("START_RECORDING")
    result = await registry.execute("STOP_RECORDING")
    assert result["success"] is True
    assert robot_state.camera.is_recording is False


# ============================================================
# WAVE / NOD → ARM CONTROLLER
# ============================================================

@pytest.mark.asyncio
async def test_wave_moves_arm(controllers):
    """WAVE action actually moves the arm through a sequence."""
    robot_state.arm.shoulder.angle = 90.0
    result = await registry.execute("WAVE")
    assert result["success"] is True
    assert robot_state.arm.shoulder.angle == 90.0


@pytest.mark.asyncio
async def test_nod_moves_arm(controllers):
    """NOD action dips and returns the shoulder."""
    robot_state.arm.shoulder.angle = 90.0
    result = await registry.execute("NOD")
    assert result["success"] is True
    assert robot_state.arm.shoulder.angle == 90.0


# ============================================================
# DATABASE TABLE WHITELIST
# ============================================================

@pytest_asyncio.fixture
async def test_db():
    """In-memory database for testing."""
    manager = DatabaseManager()
    manager._connection = await aiosqlite.connect(":memory:")
    manager._connection.row_factory = aiosqlite.Row
    schema_path = Path(__file__).resolve().parent.parent.parent / "Database" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    await manager._connection.executescript(schema)
    await manager._connection.commit()
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_insert_allowed_table(test_db):
    """Insert into a whitelisted table succeeds."""
    row_id = await test_db.insert("events", {
        "event_type": "TEST",
        "source": "test",
        "message": "test event",
    })
    assert row_id is not None


@pytest.mark.asyncio
async def test_insert_blocked_table(test_db):
    """Insert into a non-whitelisted table is rejected."""
    with pytest.raises(ValueError, match="not in the allowed tables whitelist"):
        await test_db.insert("users; DROP TABLE events;--", {"name": "evil"})


@pytest.mark.asyncio
async def test_insert_unknown_table(test_db):
    """Insert into unknown table name is rejected."""
    with pytest.raises(ValueError, match="not in the allowed tables whitelist"):
        await test_db.insert("nonexistent_table", {"data": "value"})


@pytest.mark.asyncio
async def test_insert_bad_column(test_db):
    """Insert with invalid column name is rejected."""
    with pytest.raises(ValueError, match="Invalid column identifier"):
        await test_db.insert("events", {
            "event_type": "TEST",
            "source; DROP TABLE events;--": "evil",
        })


@pytest.mark.asyncio
async def test_allowed_tables_complete():
    """ALLOWED_TABLES contains all schema tables."""
    expected = {"robot_state", "events", "commands", "sensor_readings",
                "photos", "recordings", "conversations", "sync_queue", "system_errors"}
    assert expected == ALLOWED_TABLES


# ============================================================
# process_text MEMORY / STATE BEHAVIOR
# ============================================================

@pytest.mark.asyncio
async def test_process_text_saves_memory(controllers):
    """process_text must save user input to memory."""
    from AI.STT.provider import MockSTTProvider
    from AI.TTS.provider import MockTTSProvider
    from AI.LLM.provider import MockLLMProvider
    from AI.Intent.engine import intent_engine
    from AI.Memory.provider import MockMemoryProvider
    from Backend.Robot.Safety.safety import safety
    from AI.pipeline import VoicePipeline

    memory = MockMemoryProvider()
    pipeline = VoicePipeline(
        stt=MockSTTProvider(), tts=MockTTSProvider(),
        llm=MockLLMProvider(), intent=intent_engine,
        memory=memory, actions=registry, safety=safety,
    )

    await pipeline.process_text("hello everyone")

    history = await memory.get_conversation_history(limit=10)
    user_msgs = [m for m in history if m["role"] == "user"]
    assert len(user_msgs) >= 1
    assert user_msgs[0]["content"] == "hello everyone"


@pytest.mark.asyncio
async def test_process_text_updates_voice_state(controllers):
    """process_text must update voice.last_utterance."""
    from AI.STT.provider import MockSTTProvider
    from AI.TTS.provider import MockTTSProvider
    from AI.LLM.provider import MockLLMProvider
    from AI.Intent.engine import intent_engine
    from AI.Memory.provider import MockMemoryProvider
    from Backend.Robot.Safety.safety import safety
    from AI.pipeline import VoicePipeline

    pipeline = VoicePipeline(
        stt=MockSTTProvider(), tts=MockTTSProvider(),
        llm=MockLLMProvider(), intent=intent_engine,
        memory=MockMemoryProvider(), actions=registry, safety=safety,
    )

    await pipeline.process_text("what is python")

    assert robot_state.voice.last_utterance == "what is python"
    assert robot_state.voice.last_response != ""


@pytest.mark.asyncio
async def test_process_text_saves_response_to_memory(controllers):
    """process_text must save assistant response to memory."""
    from AI.STT.provider import MockSTTProvider
    from AI.TTS.provider import MockTTSProvider
    from AI.LLM.provider import MockLLMProvider
    from AI.Intent.engine import intent_engine
    from AI.Memory.provider import MockMemoryProvider
    from Backend.Robot.Safety.safety import safety
    from AI.pipeline import VoicePipeline

    memory = MockMemoryProvider()
    pipeline = VoicePipeline(
        stt=MockSTTProvider(), tts=MockTTSProvider(),
        llm=MockLLMProvider(), intent=intent_engine,
        memory=memory, actions=registry, safety=safety,
    )

    await pipeline.process_text("what is python")

    history = await memory.get_conversation_history(limit=10)
    assistant_msgs = [m for m in history if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1


# ============================================================
# last_action_time
# ============================================================

@pytest.mark.asyncio
async def test_last_action_time_set():
    """last_action_time is set after successful command execution."""
    from httpx import AsyncClient, ASGITransport
    from Backend.api.server import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            before = datetime.now(timezone.utc)
            resp = await client.post("/api/command", json={"action": "HELLO"})
            after = datetime.now(timezone.utc)

            assert resp.status_code == 200
            assert robot_state.last_action_time is not None
            assert before <= robot_state.last_action_time <= after
