"""
CYNEXIS — Intent Engine
Maps natural language to predefined actions. NO LLM dependency.
Uses keyword + pattern matching.
"""

import re
from typing import Optional
from core.constants import ActionName
from core.logger import get_logger

log = get_logger("intent")


# Intent mapping: pattern → ActionName
# Ordered by specificity (most specific first)
INTENT_PATTERNS: list[tuple[list[str], ActionName]] = [
    # Emergency
    (["emergency stop", "emergency", "e stop", "panic"], ActionName.EMERGENCY_STOP),

    # Greetings
    (["say hello", "hello everyone", "greet", "greet everyone", "cynexis say hello",
      "hi everyone"], ActionName.HELLO),
    (["introduce yourself", "introduce", "who are you", "tell about yourself",
      "introduction"], ActionName.INTRODUCE_SELF),
    (["wave", "wave hand", "wave hello"], ActionName.WAVE),
    (["nod", "nod head", "yes"], ActionName.NOD),

    # Camera & Vision
    (["take a photo", "take photo", "capture", "photo", "take picture",
      "take a picture", "snap", "capture image", "photograph"], ActionName.PHOTO),
    (["start recording", "record", "start video", "begin recording"], ActionName.START_RECORDING),
    (["stop recording", "stop video", "end recording", "finish recording"], ActionName.STOP_RECORDING),
    (["what do you see", "what are you seeing", "describe what you see", "look around",
      "what's in front of you", "identify object", "describe scene", "what is in front of you"], ActionName.DESCRIBE_SCENE),

    # Movement
    (["stop", "halt", "freeze", "don't move", "stand still"], ActionName.STOP),
    (["move forward", "go forward", "forward", "go ahead", "move ahead",
      "go straight"], ActionName.FORWARD),
    (["move backward", "go backward", "backward", "go back", "reverse",
      "move back"], ActionName.BACKWARD),
    (["turn left", "go left", "move left", "left"], ActionName.LEFT),
    (["turn right", "go right", "move right", "right"], ActionName.RIGHT),

    # Gripper
    (["open the gripper", "open gripper", "release", "grip open", "let go", "open hand",
      "open the hand", "open claw", "open the claw"], ActionName.GRIP_OPEN),
    (["close the gripper", "close gripper", "grab", "grip close", "grip", "hold",
      "close the hand", "close claw", "close the claw"], ActionName.GRIP_CLOSE),

    # Arm
    (["raise arm", "arm up", "lift arm", "raise"], ActionName.ARM_UP),
    (["lower arm", "arm down", "drop arm", "lower"], ActionName.ARM_DOWN),

    # Status
    (["status", "get status", "how are you", "system status", "report",
      "what's your status"], ActionName.GET_STATUS),
]


class IntentEngine:
    """
    Maps natural language text to predefined ActionNames.
    Does NOT use an LLM — purely rule-based pattern matching.
    """

    def __init__(self):
        log.info(f"IntentEngine initialized with {len(INTENT_PATTERNS)} patterns")

    def classify(self, text: str) -> Optional[ActionName]:
        """
        Classify text into an action. Returns None if no match.

        Args:
            text: Natural language input (e.g., "move forward")

        Returns:
            ActionName or None
        """
        text_lower = text.lower().strip()
        if not text_lower:
            return None

        for patterns, action in INTENT_PATTERNS:
            for pattern in patterns:
                if pattern in text_lower:
                    log.info(f"Intent: '{text}' -> {action.value} (matched: '{pattern}')")
                    return action

        log.debug(f"No intent match for: '{text}'")
        return None

    def is_robot_command(self, text: str) -> bool:
        """Check if text maps to a robot command (vs. a conversational query)."""
        return self.classify(text) is not None

    def get_all_patterns(self) -> dict[str, list[str]]:
        """Return all patterns for documentation/debugging."""
        return {
            action.value: patterns
            for patterns, action in INTENT_PATTERNS
        }


# Singleton
intent_engine = IntentEngine()
