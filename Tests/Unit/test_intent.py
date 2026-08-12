"""Tests for intent engine — natural language to action mapping."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from AI.Intent.engine import IntentEngine
from core.constants import ActionName


engine = IntentEngine()


# ============================================================
# CRITICAL INTENT MAPPING TESTS
# These are the tests specified in the master prompt.
# ============================================================

def test_hello_everyone():
    """'hello everyone' → HELLO"""
    assert engine.classify("hello everyone") == ActionName.HELLO


def test_move_forward():
    """'move forward' → FORWARD"""
    assert engine.classify("move forward") == ActionName.FORWARD


def test_stop():
    """'stop' → STOP"""
    assert engine.classify("stop") == ActionName.STOP


def test_take_a_picture():
    """'take a picture' → PHOTO"""
    assert engine.classify("take a picture") == ActionName.PHOTO


# ============================================================
# ADDITIONAL COVERAGE
# ============================================================

def test_say_hello():
    assert engine.classify("say hello") == ActionName.HELLO


def test_cynexis_say_hello():
    assert engine.classify("CYNEXIS say hello") == ActionName.HELLO


def test_greet_everyone():
    assert engine.classify("greet everyone") == ActionName.HELLO


def test_go_forward():
    assert engine.classify("go forward") == ActionName.FORWARD


def test_go_back():
    assert engine.classify("go back") == ActionName.BACKWARD


def test_turn_left():
    assert engine.classify("turn left") == ActionName.LEFT


def test_turn_right():
    assert engine.classify("turn right") == ActionName.RIGHT


def test_take_photo():
    assert engine.classify("take a photo") == ActionName.PHOTO


def test_capture():
    assert engine.classify("capture") == ActionName.PHOTO


def test_open_gripper():
    assert engine.classify("open gripper") == ActionName.GRIP_OPEN


def test_close_gripper():
    assert engine.classify("close gripper") == ActionName.GRIP_CLOSE


def test_raise_arm():
    assert engine.classify("raise arm") == ActionName.ARM_UP


def test_lower_arm():
    assert engine.classify("lower arm") == ActionName.ARM_DOWN


def test_emergency_stop():
    assert engine.classify("emergency stop") == ActionName.EMERGENCY_STOP


def test_get_status():
    assert engine.classify("status") == ActionName.GET_STATUS


def test_introduce():
    assert engine.classify("introduce yourself") == ActionName.INTRODUCE_SELF


def test_no_match():
    """Random text should return None (not a command)."""
    assert engine.classify("what is the weather today") is None


def test_empty_string():
    assert engine.classify("") is None


def test_is_robot_command():
    assert engine.is_robot_command("move forward") is True
    assert engine.is_robot_command("what is python") is False
