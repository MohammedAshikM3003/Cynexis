"""Tests for gesture classifier."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from Backend.Robot.Gestures.classifier import GestureClassifier
from core.constants import GestureType, ActionName


clf = GestureClassifier()


def test_fist_gesture():
    """All fingers bent → FIST."""
    bend = [80, 80, 80, 80, 80]
    assert clf.classify_gesture(bend) == GestureType.FIST


def test_open_gesture():
    """All fingers straight → OPEN."""
    bend = [5, 5, 5, 5, 5]
    assert clf.classify_gesture(bend) == GestureType.OPEN


def test_point_gesture():
    """Index straight, others bent → POINT."""
    bend = [70, 10, 80, 80, 80]
    assert clf.classify_gesture(bend) == GestureType.POINT


def test_partial_gesture():
    """Some bent, some straight → PARTIAL."""
    bend = [50, 50, 10, 80, 20]
    assert clf.classify_gesture(bend) == GestureType.PARTIAL


def test_tilt_forward():
    assert clf.classify_tilt(0.0, 40.0) == ActionName.FORWARD


def test_tilt_backward():
    assert clf.classify_tilt(0.0, -40.0) == ActionName.BACKWARD


def test_tilt_left():
    assert clf.classify_tilt(-40.0, 0.0) == ActionName.LEFT


def test_tilt_right():
    assert clf.classify_tilt(40.0, 0.0) == ActionName.RIGHT


def test_tilt_neutral():
    """No significant tilt → None."""
    assert clf.classify_tilt(5.0, 5.0) is None


def test_normalize_flex():
    """ADC values normalized to 0-100%."""
    raw = [1500, 2500, 3500, 1500, 1500]
    bend = clf.normalize_flex(raw)
    assert bend[0] == 0    # Straight
    assert bend[1] == 50   # Half bent
    assert bend[2] == 100  # Fully bent


def test_full_pipeline():
    """Full process() returns gesture + tilt + grip."""
    result = clf.process(
        raw_flex=[3500, 3500, 3500, 3500, 3500],  # All bent
        roll=0.0, pitch=40.0,  # Tilted forward
    )
    assert result["gesture"] == GestureType.FIST
    assert result["tilt_command"] == ActionName.FORWARD
    assert result["grip_command"] == ActionName.GRIP_CLOSE
