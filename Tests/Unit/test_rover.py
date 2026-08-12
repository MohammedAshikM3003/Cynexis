"""Tests for mock rover controller."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from Backend.Robot.rover import MockRoverController
from core.state import robot_state


@pytest.fixture
def rover():
    """Create a mock rover and reset state."""
    robot_state.rover.direction = "STOPPED"
    robot_state.rover.speed = 0
    robot_state.rover.is_moving = False
    return MockRoverController()


@pytest.mark.asyncio
async def test_forward(rover):
    await rover.forward(150)
    assert robot_state.rover.direction == "FORWARD"
    assert robot_state.rover.speed == 150
    assert robot_state.rover.is_moving is True


@pytest.mark.asyncio
async def test_backward(rover):
    await rover.backward(100)
    assert robot_state.rover.direction == "BACKWARD"
    assert robot_state.rover.is_moving is True


@pytest.mark.asyncio
async def test_left(rover):
    await rover.left()
    assert robot_state.rover.direction == "LEFT"


@pytest.mark.asyncio
async def test_right(rover):
    await rover.right()
    assert robot_state.rover.direction == "RIGHT"


@pytest.mark.asyncio
async def test_stop(rover):
    await rover.forward()
    await rover.stop()
    assert robot_state.rover.direction == "STOPPED"
    assert robot_state.rover.speed == 0
    assert robot_state.rover.is_moving is False


@pytest.mark.asyncio
async def test_emergency_stop(rover):
    await rover.forward(200)
    await rover.emergency_stop()
    assert robot_state.rover.direction == "STOPPED"
    assert robot_state.rover.speed == 0
    assert robot_state.rover.is_moving is False


@pytest.mark.asyncio
async def test_speed_clamped(rover):
    """Speed cannot exceed MAX_ROVER_SPEED."""
    await rover.forward(999)
    assert robot_state.rover.speed == 255
