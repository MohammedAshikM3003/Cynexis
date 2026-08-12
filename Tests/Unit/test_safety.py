"""Tests for safety layer — command validation and rejection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from Backend.Robot.Safety.safety import SafetyValidator
from core.state import robot_state, RobotState
from core.constants import SystemMode, ActionName
from core.exceptions import SafetyError, CommandError


@pytest.fixture(autouse=True)
def reset_state():
    """Reset robot state before each test."""
    robot_state.mode = SystemMode.NORMAL
    robot_state.battery_pct = 100
    robot_state.rover.is_moving = False
    yield


safety = SafetyValidator()


def test_valid_action_passes():
    """Known actions pass validation."""
    safety.validate_action("HELLO")
    safety.validate_action("FORWARD")
    safety.validate_action("STOP")
    safety.validate_action("PHOTO")


def test_unknown_action_rejected():
    """Unknown actions are rejected — whitelist enforcement."""
    with pytest.raises(CommandError):
        safety.validate_action("HACK_MOTORS")


def test_arbitrary_command_rejected():
    """Arbitrary strings are rejected."""
    with pytest.raises(CommandError):
        safety.validate_action("DESTROY_EVERYTHING")


def test_eval_rejected():
    """eval() attempt is rejected."""
    with pytest.raises(CommandError):
        safety.validate_action("eval()")


def test_emergency_mode_blocks_movement():
    """In EMERGENCY mode, only EMERGENCY_STOP and GET_STATUS are allowed."""
    robot_state.mode = SystemMode.EMERGENCY
    with pytest.raises(SafetyError):
        safety.validate_action("FORWARD")
    # These should pass
    safety.validate_action("EMERGENCY_STOP")
    safety.validate_action("GET_STATUS")


def test_shutdown_blocks_all_except_status():
    """In SHUTDOWN, only GET_STATUS allowed."""
    robot_state.mode = SystemMode.SHUTDOWN
    with pytest.raises(SafetyError):
        safety.validate_action("FORWARD")
    with pytest.raises(SafetyError):
        safety.validate_action("HELLO")
    safety.validate_action("GET_STATUS")


def test_low_battery_blocks_movement():
    """Critical battery blocks movement but allows STOP."""
    robot_state.battery_pct = 10
    with pytest.raises(SafetyError):
        safety.validate_action("FORWARD")
    safety.validate_action("STOP")
    safety.validate_action("GET_STATUS")


def test_arm_blocked_while_moving():
    """ARM_UP is blocked while rover is moving."""
    robot_state.rover.is_moving = True
    with pytest.raises(SafetyError):
        safety.validate_action("ARM_UP")


def test_servo_angle_limits():
    """Invalid servo angles are rejected."""
    with pytest.raises(SafetyError):
        safety.validate_action("ARM_UP", {"angle": 999})
    with pytest.raises(SafetyError):
        safety.validate_action("ARM_UP", {"angle": -10})


def test_speed_limits():
    """Invalid speeds are rejected."""
    with pytest.raises(SafetyError):
        safety.validate_action("FORWARD", {"speed": 500})


def test_is_action_allowed():
    """Non-throwing check works correctly."""
    assert safety.is_action_allowed("HELLO") is True
    assert safety.is_action_allowed("HACK") is False


def test_llm_cannot_execute_arbitrary():
    """LLM cannot bypass safety by sending arbitrary strings."""
    arbitrary_commands = [
        "GPIO_SET_HIGH_12",
        "SERVO_WRITE_180",
        "MOTOR_FULL_SPEED",
        "exec('import os')",
        "system('rm -rf /')",
        "CUSTOM_MOVEMENT_PATTERN",
    ]
    for cmd in arbitrary_commands:
        assert safety.is_action_allowed(cmd) is False, f"Should reject: {cmd}"
