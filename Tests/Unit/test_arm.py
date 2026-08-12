"""Tests for mock arm controller (4-DOF: base + shoulder + elbow + wrist)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from Backend.Robot.arm import MockArmController
from core.state import robot_state


@pytest.fixture
def arm():
    robot_state.arm.base.angle = 90.0
    robot_state.arm.shoulder.angle = 90.0
    robot_state.arm.elbow.angle = 90.0
    robot_state.arm.wrist.angle = 90.0
    return MockArmController()


@pytest.mark.asyncio
async def test_base_position(arm):
    await arm.base_position(45.0)
    assert robot_state.arm.base.angle == 45.0


@pytest.mark.asyncio
async def test_shoulder_position(arm):
    await arm.shoulder_position(45.0)
    assert robot_state.arm.shoulder.angle == 45.0


@pytest.mark.asyncio
async def test_elbow_position(arm):
    await arm.elbow_position(120.0)
    assert robot_state.arm.elbow.angle == 120.0


@pytest.mark.asyncio
async def test_wrist_position(arm):
    await arm.wrist_position(180.0)
    assert robot_state.arm.wrist.angle == 180.0


@pytest.mark.asyncio
async def test_home(arm):
    await arm.shoulder_position(45.0)
    await arm.base_position(180.0)
    await arm.home()
    assert robot_state.arm.base.angle == 90.0
    assert robot_state.arm.shoulder.angle == 90.0
    assert robot_state.arm.elbow.angle == 90.0
    assert robot_state.arm.wrist.angle == 90.0


@pytest.mark.asyncio
async def test_angle_clamped_high(arm):
    """Angle clamped to MAX_SERVO_ANGLE (270)."""
    await arm.shoulder_position(999.0)
    assert robot_state.arm.shoulder.angle == 270.0


@pytest.mark.asyncio
async def test_angle_clamped_low(arm):
    """Angle clamped to MIN_SERVO_ANGLE (0)."""
    await arm.shoulder_position(-50.0)
    assert robot_state.arm.shoulder.angle == 0.0


@pytest.mark.asyncio
async def test_base_clamped(arm):
    """Base angle also clamped."""
    await arm.base_position(999.0)
    assert robot_state.arm.base.angle == 270.0
    await arm.base_position(-10.0)
    assert robot_state.arm.base.angle == 0.0


@pytest.mark.asyncio
async def test_stop(arm):
    robot_state.arm.is_moving = True
    await arm.stop()
    assert robot_state.arm.is_moving is False


@pytest.mark.asyncio
async def test_4dof_count():
    """Arm has exactly 4 joints."""
    joints = [f for f in robot_state.arm.model_fields if f != "is_moving"]
    assert len(joints) == 4
    assert "base" in joints
    assert "shoulder" in joints
    assert "elbow" in joints
    assert "wrist" in joints
