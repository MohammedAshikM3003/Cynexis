"""
CYNEXIS — Unit Tests for Hand Gesture Recognition Engine (Phase 9D)
====================================================================
Validates:
- Telemetry-only hand gesture recognition: OPEN, CLOSED/FIST, POINT, THUMB_UP, UNKNOWN
- Configurable thresholds and boundary conditions
- Hysteresis behavior preventing boundary oscillation
- 3-frame temporal stability filter (transient noise rejection)
- Deterministic confidence calculations (0.0 to 1.0)
- Out-of-domain input clamping
- robot_state.hand state updates and JSON serialization
- Backward compatibility with GestureType enum
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from datetime import datetime, timezone

from core.constants import GestureType
from core.state import robot_state
from core.gestures import (
    HandGestureRecognizer,
    GestureThresholds,
    GestureResult,
)


@pytest.fixture(autouse=True)
def reset_hand_state():
    """Reset robot_state.hand before each test."""
    robot_state.hand.gesture = "UNKNOWN"
    robot_state.hand.confidence = 0.0
    robot_state.hand.thumb_bend_pct = 0.0
    robot_state.hand.index_bend_pct = 0.0
    robot_state.hand.is_stable = False
    robot_state.hand.stable_count = 0
    yield


# ============================================================
# 1. CORE GESTURE CLASSIFICATION TESTS
# ============================================================

class TestCoreGestureClassification:
    """Validates classification logic for all supported gestures."""

    def test_open_recognition(self):
        recognizer = HandGestureRecognizer()
        # Feed 3 stable frames of OPEN (thumb=10%, index=10%)
        res = None
        for _ in range(3):
            res = recognizer.process(thumb_bend_pct=10.0, index_bend_pct=10.0)

        assert res is not None
        assert res.gesture == GestureType.OPEN.value
        assert res.is_stable is True
        assert res.stable_count >= 3
        assert 0.5 <= res.confidence <= 1.0

    def test_closed_recognition(self):
        recognizer = HandGestureRecognizer()
        # Feed 3 stable frames of CLOSED (thumb=85%, index=80%)
        res = None
        for _ in range(3):
            res = recognizer.process(thumb_bend_pct=85.0, index_bend_pct=80.0)

        assert res is not None
        assert res.gesture == GestureType.CLOSED.value
        assert res.is_stable is True
        assert 0.5 <= res.confidence <= 1.0

    def test_point_recognition(self):
        recognizer = HandGestureRecognizer()
        # Point: Thumb bent (75%), Index straight (15%)
        res = None
        for _ in range(3):
            res = recognizer.process(thumb_bend_pct=75.0, index_bend_pct=15.0)

        assert res is not None
        assert res.gesture == GestureType.POINT.value
        assert res.is_stable is True
        assert 0.5 <= res.confidence <= 1.0

    def test_thumb_up_recognition(self):
        recognizer = HandGestureRecognizer()
        # Thumb Up: Thumb straight (15%), Index bent (75%)
        res = None
        for _ in range(3):
            res = recognizer.process(thumb_bend_pct=15.0, index_bend_pct=75.0)

        assert res is not None
        assert res.gesture == GestureType.THUMB_UP.value
        assert res.is_stable is True
        assert 0.5 <= res.confidence <= 1.0

    def test_unknown_recognition(self):
        recognizer = HandGestureRecognizer()
        # Intermediate / ambiguous bend values (thumb=45%, index=45%)
        res = None
        for _ in range(3):
            res = recognizer.process(thumb_bend_pct=45.0, index_bend_pct=45.0)

        assert res is not None
        assert res.gesture == GestureType.UNKNOWN.value
        assert res.confidence == 0.0


# ============================================================
# 2. HYSTERESIS & BOUNDARY TESTS
# ============================================================

class TestGestureHysteresis:
    """Validates that boundary buffer prevents rapid oscillation."""

    def test_open_hysteresis_retention(self):
        # Default: straight=25.0, hysteresis=5.0 -> exit threshold is 30.0
        recognizer = HandGestureRecognizer()

        # Step 1: Establish stable OPEN state
        for _ in range(3):
            recognizer.process(thumb_bend_pct=20.0, index_bend_pct=20.0)

        # Step 2: Push to 28% (above 25% straight threshold, but below 25+5=30% hysteresis exit)
        res = recognizer.process(thumb_bend_pct=28.0, index_bend_pct=28.0)
        assert res.raw_candidate == GestureType.OPEN.value

        # Step 3: Push to 32% (exceeds 30% hysteresis exit) -> drops to UNKNOWN
        res = recognizer.process(thumb_bend_pct=32.0, index_bend_pct=32.0)
        assert res.raw_candidate == GestureType.UNKNOWN.value

    def test_closed_hysteresis_retention(self):
        # Default: bent=60.0, hysteresis=5.0 -> exit threshold is 55.0
        recognizer = HandGestureRecognizer()

        # Step 1: Establish stable CLOSED state
        for _ in range(3):
            recognizer.process(thumb_bend_pct=70.0, index_bend_pct=70.0)

        # Step 2: Drop to 57% (below 60% bent threshold, but above 60-5=55% hysteresis exit)
        res = recognizer.process(thumb_bend_pct=57.0, index_bend_pct=57.0)
        assert res.raw_candidate == GestureType.CLOSED.value

        # Step 3: Drop to 52% (below 55% hysteresis exit) -> drops to UNKNOWN
        res = recognizer.process(thumb_bend_pct=52.0, index_bend_pct=52.0)
        assert res.raw_candidate == GestureType.UNKNOWN.value


# ============================================================
# 3. TEMPORAL STABILITY & NOISE REJECTION
# ============================================================

class TestTemporalStability:
    """Validates the 3-frame stability requirement and transient spike immunity."""

    def test_requires_three_consecutive_frames(self):
        recognizer = HandGestureRecognizer(GestureThresholds(stability_frames=3))

        # Frame 1: OPEN detected
        r1 = recognizer.process(10.0, 10.0)
        assert r1.raw_candidate == GestureType.OPEN.value
        assert r1.is_stable is False
        assert r1.stable_count == 1
        assert r1.gesture == GestureType.UNKNOWN.value  # Previous stable state

        # Frame 2: OPEN detected
        r2 = recognizer.process(10.0, 10.0)
        assert r2.is_stable is False
        assert r2.stable_count == 2
        assert r2.gesture == GestureType.UNKNOWN.value

        # Frame 3: OPEN detected (stabilized!)
        r3 = recognizer.process(10.0, 10.0)
        assert r3.is_stable is True
        assert r3.stable_count == 3
        assert r3.gesture == GestureType.OPEN.value

    def test_single_frame_noise_does_not_flip_stable_gesture(self):
        recognizer = HandGestureRecognizer(GestureThresholds(stability_frames=3))

        # Establish stable OPEN
        for _ in range(3):
            recognizer.process(5.0, 5.0)

        # Single transient frame of CLOSED (e.g. sensor glitch)
        spike = recognizer.process(90.0, 90.0)
        assert spike.raw_candidate == GestureType.CLOSED.value
        assert spike.is_stable is False
        assert spike.gesture == GestureType.OPEN.value  # Retains stable OPEN!

        # Back to normal reading
        next_frame = recognizer.process(5.0, 5.0)
        assert next_frame.gesture == GestureType.OPEN.value


# ============================================================
# 4. CONFIDENCE SCORING & CLAMPING TESTS
# ============================================================

class TestConfidenceAndClamping:
    """Validates deterministic confidence bounds and input safety clamping."""

    def test_confidence_scaling(self):
        recognizer = HandGestureRecognizer()
        # Perfectly straight (0%, 0%) -> maximum confidence 1.0
        res_max = recognizer.process(0.0, 0.0)
        assert res_max.confidence == 1.0

        # Boundary straight (25%, 25%) -> baseline confidence 0.5
        res_edge = recognizer.process(25.0, 25.0)
        assert res_edge.confidence == 0.5

    def test_out_of_bounds_input_clamping(self):
        recognizer = HandGestureRecognizer()
        # Negative percentage input
        res_neg = recognizer.process(-20.0, -10.0)
        assert res_neg.thumb_bend_pct == 0.0
        assert res_neg.index_bend_pct == 0.0
        assert res_neg.raw_candidate == GestureType.OPEN.value

        # Above 100% input
        res_high = recognizer.process(150.0, 200.0)
        assert res_high.thumb_bend_pct == 100.0
        assert res_high.index_bend_pct == 100.0
        assert res_high.raw_candidate == GestureType.CLOSED.value


# ============================================================
# 5. STATE INTEGRATION & SERIALIZATION
# ============================================================

class TestStateIntegration:
    """Validates robot_state.hand schema and JSON export."""

    def test_hand_state_serialization(self):
        robot_state.hand.gesture = GestureType.POINT.value
        robot_state.hand.confidence = 0.88
        robot_state.hand.thumb_bend_pct = 75.0
        robot_state.hand.index_bend_pct = 15.0
        robot_state.hand.is_stable = True
        robot_state.hand.stable_count = 5
        robot_state.hand.last_updated = datetime.now(timezone.utc)

        data = robot_state.hand.model_dump()
        assert data["gesture"] == "POINT"
        assert data["confidence"] == 0.88
        assert data["thumb_bend_pct"] == 75.0
        assert data["index_bend_pct"] == 15.0
        assert data["is_stable"] is True
        assert data["stable_count"] == 5
        assert "last_updated" in data
