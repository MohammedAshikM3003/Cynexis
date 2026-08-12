"""
CYNEXIS — Hand Gesture Recognition Engine
===========================================
Telemetry-only gesture classifier for 2-finger (Thumb + Index) flex sensor data.

Key Guarantees:
- Telemetry-only: No actuator, servo, motor, or command dispatching.
- Hysteresis: Prevents oscillation near threshold boundaries.
- Temporal stability: Requires N consecutive matching observations before updating stable gesture.
- Deterministic confidence: Continuous bounded metric (0.0 to 1.0) based on threshold distance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from core.constants import GestureType
from core.logger import get_logger

log = get_logger("gestures")


@dataclass
class GestureThresholds:
    """Configurable thresholds for 2-finger gesture recognition."""
    straight_threshold: float = 25.0   # <= 25% bend considered straight
    bent_threshold: float = 60.0       # >= 60% bend considered bent
    hysteresis: float = 5.0            # Boundary buffer for state retention
    stability_frames: int = 3          # Consecutive matching frames required for stability


@dataclass
class GestureResult:
    """Output structure of a gesture recognition frame."""
    gesture: str
    confidence: float
    thumb_bend_pct: float
    index_bend_pct: float
    is_stable: bool
    stable_count: int
    raw_candidate: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HandGestureRecognizer:
    """
    Classifies normalized thumb and index bend percentages into discrete hand gestures.
    """

    def __init__(self, thresholds: Optional[GestureThresholds] = None):
        self.thresholds = thresholds or GestureThresholds()

        self._current_gesture: str = GestureType.UNKNOWN.value
        self._candidate_gesture: str = GestureType.UNKNOWN.value
        self._candidate_count: int = 0
        self._stable_gesture: str = GestureType.UNKNOWN.value

    def process(self, thumb_bend_pct: float, index_bend_pct: float) -> GestureResult:
        """
        Process a single normalized frame and return the classified GestureResult.
        """
        # Clamp inputs to valid domain
        t_bend = max(0.0, min(100.0, float(thumb_bend_pct)))
        i_bend = max(0.0, min(100.0, float(index_bend_pct)))

        # 1. Evaluate candidate gesture with hysteresis
        candidate = self._classify_with_hysteresis(t_bend, i_bend)

        # 2. Update temporal stability tracking
        if candidate == self._candidate_gesture:
            self._candidate_count += 1
        else:
            self._candidate_gesture = candidate
            self._candidate_count = 1

        is_stable = self._candidate_count >= self.thresholds.stability_frames
        if is_stable:
            self._stable_gesture = candidate

        # 3. Compute deterministic confidence
        confidence = self._compute_confidence(candidate, t_bend, i_bend)

        return GestureResult(
            gesture=self._stable_gesture,
            confidence=confidence,
            thumb_bend_pct=t_bend,
            index_bend_pct=i_bend,
            is_stable=is_stable,
            stable_count=self._candidate_count,
            raw_candidate=candidate,
            timestamp=datetime.now(timezone.utc),
        )

    def _classify_with_hysteresis(self, thumb: float, index: float) -> str:
        """Classify candidate gesture applying hysteresis against current state."""
        t = self.thresholds
        s_th = t.straight_threshold
        b_th = t.bent_threshold
        hyst = t.hysteresis

        curr = self._candidate_gesture

        # Hysteresis checks for remaining in active state
        if curr == GestureType.OPEN.value:
            # Stays OPEN until either finger exceeds straight + hysteresis
            if thumb <= (s_th + hyst) and index <= (s_th + hyst):
                return GestureType.OPEN.value

        elif curr in (GestureType.CLOSED.value, GestureType.FIST.value):
            # Stays CLOSED until either finger drops below bent - hysteresis
            if thumb >= (b_th - hyst) and index >= (b_th - hyst):
                return GestureType.CLOSED.value

        elif curr == GestureType.POINT.value:
            # Stays POINT until thumb drops or index exceeds straight + hysteresis
            if thumb >= (b_th - hyst) and index <= (s_th + hyst):
                return GestureType.POINT.value

        elif curr == GestureType.THUMB_UP.value:
            # Stays THUMB_UP until thumb exceeds straight + hyst or index drops below bent - hyst
            if thumb <= (s_th + hyst) and index >= (b_th - hyst):
                return GestureType.THUMB_UP.value

        # Fresh classification rules
        is_thumb_straight = thumb <= s_th
        is_thumb_bent = thumb >= b_th
        is_index_straight = index <= s_th
        is_index_bent = index >= b_th

        if is_thumb_straight and is_index_straight:
            return GestureType.OPEN.value
        elif is_thumb_bent and is_index_bent:
            return GestureType.CLOSED.value
        elif is_thumb_bent and is_index_straight:
            return GestureType.POINT.value
        elif is_thumb_straight and is_index_bent:
            return GestureType.THUMB_UP.value
        else:
            return GestureType.UNKNOWN.value

    def _compute_confidence(self, gesture: str, thumb: float, index: float) -> float:
        """
        Compute deterministic confidence score [0.0 - 1.0] based on threshold margins.
        """
        t = self.thresholds
        s_th = t.straight_threshold
        b_th = t.bent_threshold

        if gesture == GestureType.OPEN.value:
            # Proximity to 0% bend
            t_score = max(0.0, 1.0 - (thumb / s_th)) if s_th > 0 else 1.0
            i_score = max(0.0, 1.0 - (index / s_th)) if s_th > 0 else 1.0
            raw_conf = (t_score + i_score) / 2.0
            return round(0.5 + (0.5 * raw_conf), 2)

        elif gesture in (GestureType.CLOSED.value, GestureType.FIST.value):
            # Proximity to 100% bend
            t_denom = 100.0 - b_th
            i_denom = 100.0 - b_th
            t_score = min(1.0, max(0.0, (thumb - b_th) / t_denom)) if t_denom > 0 else 1.0
            i_score = min(1.0, max(0.0, (index - b_th) / i_denom)) if i_denom > 0 else 1.0
            raw_conf = (t_score + i_score) / 2.0
            return round(0.5 + (0.5 * raw_conf), 2)

        elif gesture == GestureType.POINT.value:
            t_denom = 100.0 - b_th
            t_score = min(1.0, max(0.0, (thumb - b_th) / t_denom)) if t_denom > 0 else 1.0
            i_score = max(0.0, 1.0 - (index / s_th)) if s_th > 0 else 1.0
            raw_conf = (t_score + i_score) / 2.0
            return round(0.5 + (0.5 * raw_conf), 2)

        elif gesture == GestureType.THUMB_UP.value:
            t_score = max(0.0, 1.0 - (thumb / s_th)) if s_th > 0 else 1.0
            i_denom = 100.0 - b_th
            i_score = min(1.0, max(0.0, (index - b_th) / i_denom)) if i_denom > 0 else 1.0
            raw_conf = (t_score + i_score) / 2.0
            return round(0.5 + (0.5 * raw_conf), 2)

        return 0.0

    def reset(self) -> None:
        """Reset internal recognition tracking."""
        self._current_gesture = GestureType.UNKNOWN.value
        self._candidate_gesture = GestureType.UNKNOWN.value
        self._candidate_count = 0
        self._stable_gesture = GestureType.UNKNOWN.value
