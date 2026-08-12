"""Tests for action registry and predefined actions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio

from AI.Actions.registry import ActionRegistry, ActionDefinition
from AI.Actions.actions import register_all_actions, inject_controllers
from core.constants import ActionName, SafetyLevel, SystemMode
from core.state import robot_state

from Backend.Robot.rover import MockRoverController
from Backend.Robot.arm import MockArmController
from Backend.Robot.gripper import MockGripperController
from Backend.Vision.camera import MockCamera


@pytest_asyncio.fixture(autouse=True)
async def setup_controllers():
    """Inject mock controllers into action layer for every test."""
    rover = MockRoverController()
    arm = MockArmController()
    gripper = MockGripperController()
    camera = MockCamera()
    await camera.start()
    inject_controllers(rover=rover, arm=arm, gripper=gripper, camera=camera)
    robot_state.camera.photos_taken = 0  # Reset counter between tests
    yield
    await camera.stop()


@pytest.fixture
def fresh_registry():
    """Create a fresh registry with all actions registered."""
    reg = ActionRegistry()
    from AI.Actions import actions as act
    definitions = [
        ActionDefinition(ActionName.HELLO, "Greet", act.action_hello),
        ActionDefinition(ActionName.STOP, "Stop", act.action_stop, SafetyLevel.CRITICAL),
        ActionDefinition(ActionName.FORWARD, "Forward", act.action_forward, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.PHOTO, "Photo", act.action_photo),
        ActionDefinition(ActionName.GET_STATUS, "Status", act.action_get_status),
        ActionDefinition(ActionName.EMERGENCY_STOP, "E-Stop", act.action_emergency_stop, SafetyLevel.CRITICAL),
    ]
    for d in definitions:
        reg.register(d)
    return reg


def test_action_registered(fresh_registry):
    """All key actions are registered."""
    assert fresh_registry.exists("HELLO")
    assert fresh_registry.exists("STOP")
    assert fresh_registry.exists("FORWARD")
    assert fresh_registry.exists("PHOTO")


def test_unknown_action_not_found(fresh_registry):
    """Unknown actions return None."""
    assert fresh_registry.get("HACK_MOTORS") is None
    assert fresh_registry.get("DESTROY") is None
    assert not fresh_registry.exists("ARBITRARY_CODE")


def test_action_has_handler(fresh_registry):
    """Each registered action has a callable handler."""
    defn = fresh_registry.get("HELLO")
    assert defn is not None
    assert defn.handler is not None
    assert callable(defn.handler)


@pytest.mark.asyncio
async def test_hello_executes(fresh_registry):
    """HELLO action executes and returns speech."""
    result = await fresh_registry.execute("HELLO")
    assert result["success"] is True
    assert "speech" in result.get("data", {})


@pytest.mark.asyncio
async def test_stop_executes(fresh_registry):
    """STOP action executes and stops rover."""
    result = await fresh_registry.execute("STOP")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_photo_increments_count(fresh_registry):
    """PHOTO action increments photo counter via camera controller."""
    initial = robot_state.camera.photos_taken
    await fresh_registry.execute("PHOTO")
    assert robot_state.camera.photos_taken == initial + 1


@pytest.mark.asyncio
async def test_unknown_action_fails(fresh_registry):
    """Executing unknown action returns failure."""
    result = await fresh_registry.execute("NONEXISTENT")
    assert result["success"] is False
