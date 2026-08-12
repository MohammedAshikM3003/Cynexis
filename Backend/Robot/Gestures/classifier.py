"""
CYNEXIS — Gesture Classifier
Pipeline: raw sensor → filter → calibrate → classify → robot command.
Separate from AI — purely sensor-driven.
"""

from typing import Optional
from core.constants import GestureType, ActionName
from core.logger import get_logger

log = get_logger("gestures")


# Configurable thresholds (calibrate with real hardware)
DEFAULT_THRESHOLDS = {
    "fist_min_bend": 60,      # All fingers above this = FIST
    "open_max_bend": 20,      # All fingers below this = OPEN
    "point_index_max": 20,    # Index below this + others bent = POINT
    "point_others_min": 60,
    "pitch_forward": 30.0,    # Tilt forward beyond this = FORWARD
    "pitch_backward": -30.0,  # Tilt backward beyond this = BACKWARD
    "roll_left": -30.0,       # Roll left beyond this = LEFT
    "roll_right": 30.0,       # Roll right beyond this = RIGHT
}


class GestureClassifier:
    """
    Classifies raw sensor data into gestures and robot commands.

    Pipeline:
        Raw flex ADC → normalize to 0-100% bend → classify gesture
        Raw IMU → roll/pitch → classify tilt direction
    """

    def __init__(self, thresholds: dict = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS.copy()
        self._flex_straight = [1500] * 5  # ADC values when straight
        self._flex_bent = [3500] * 5      # ADC values when fully bent
        log.info("GestureClassifier initialized")

    def calibrate(self, straight_values: list[int], bent_values: list[int]) -> None:
        """Set calibration values for flex sensors."""
        assert len(straight_values) == 5 and len(bent_values) == 5
        self._flex_straight = straight_values
        self._flex_bent = bent_values
        log.info(f"Calibrated: straight={straight_values}, bent={bent_values}")

    def normalize_flex(self, raw_values: list[int]) -> list[int]:
        """Convert raw ADC values to 0-100% bend."""
        bend = []
        for i, raw in enumerate(raw_values):
            straight = self._flex_straight[i]
            bent = self._flex_bent[i]
            if bent == straight:
                bend.append(0)
            else:
                pct = int((raw - straight) / (bent - straight) * 100)
                bend.append(max(0, min(100, pct)))
        return bend

    def classify_gesture(self, bend_values: list[int]) -> GestureType:
        """Classify finger bend values into a gesture type."""
        t = self.thresholds
        thumb, index, middle, ring, pinky = bend_values

        all_bent = all(b > t["fist_min_bend"] for b in bend_values)
        all_open = all(b < t["open_max_bend"] for b in bend_values)
        index_only = (
            index < t["point_index_max"]
            and middle > t["point_others_min"]
            and ring > t["point_others_min"]
            and pinky > t["point_others_min"]
        )

        if all_bent:
            return GestureType.FIST
        elif all_open:
            return GestureType.OPEN
        elif index_only:
            return GestureType.POINT
        else:
            return GestureType.PARTIAL

    def classify_tilt(self, roll: float, pitch: float) -> Optional[ActionName]:
        """Classify IMU tilt into a movement command."""
        t = self.thresholds

        if pitch > t["pitch_forward"]:
            return ActionName.FORWARD
        elif pitch < t["pitch_backward"]:
            return ActionName.BACKWARD
        elif roll < t["roll_left"]:
            return ActionName.LEFT
        elif roll > t["roll_right"]:
            return ActionName.RIGHT
        return None

    def process(self, raw_flex: list[int], roll: float, pitch: float) -> dict:
        """
        Full classification pipeline.

        Returns:
            {
                "bend": [0-100 per finger],
                "gesture": GestureType,
                "tilt_command": ActionName or None,
                "grip_command": ActionName or None (FIST=close, OPEN=open)
            }
        """
        bend = self.normalize_flex(raw_flex)
        gesture = self.classify_gesture(bend)
        tilt_cmd = self.classify_tilt(roll, pitch)

        grip_cmd = None
        if gesture == GestureType.FIST:
            grip_cmd = ActionName.GRIP_CLOSE
        elif gesture == GestureType.OPEN:
            grip_cmd = ActionName.GRIP_OPEN

        return {
            "bend": bend,
            "gesture": gesture,
            "tilt_command": tilt_cmd,
            "grip_command": grip_cmd,
        }
