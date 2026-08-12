"""
CYNEXIS — Safety Layer
Command validation, whitelisting, and protection.
NO eval(). NO exec(). NO arbitrary execution.
"""

from core.constants import (
    ActionName, SystemMode, SafetyLevel,
    MAX_SERVO_ANGLE, MIN_SERVO_ANGLE, MAX_ROVER_SPEED,
    BATTERY_CRITICAL_PCT,
)
from core.state import robot_state
from core.exceptions import SafetyError, CommandError
from core.logger import get_logger

log = get_logger("safety")

# Actions allowed in each system mode
ALLOWED_IN_EMERGENCY = {ActionName.EMERGENCY_STOP, ActionName.GET_STATUS}
ALLOWED_IN_SHUTDOWN = {ActionName.GET_STATUS}

# Actions that require rover to be stopped first
REQUIRES_STOPPED = {ActionName.ARM_UP, ActionName.ARM_DOWN, ActionName.WAVE, ActionName.NOD}


class SafetyValidator:
    """
    Validates all commands before execution.
    This is the ONLY gate between user intent and hardware.
    """

    def validate_action(self, action_name: str, params: dict = None) -> None:
        """
        Validate an action. Raises SafetyError or CommandError on failure.

        Args:
            action_name: Must be a valid ActionName enum value.
            params: Optional parameters for the action.
        """
        params = params or {}

        # 1. Whitelist check — is this a known action?
        try:
            action = ActionName(action_name)
        except ValueError:
            raise CommandError(
                f"Unknown action '{action_name}'. Only predefined actions are allowed.",
                command=action_name,
            )

        # 2. System mode check
        mode = robot_state.mode
        if mode == SystemMode.EMERGENCY and action not in ALLOWED_IN_EMERGENCY:
            raise SafetyError(
                f"System is in EMERGENCY mode. Only {ALLOWED_IN_EMERGENCY} are allowed."
            )
        if mode == SystemMode.SHUTDOWN and action not in ALLOWED_IN_SHUTDOWN:
            raise SafetyError("System is in SHUTDOWN mode. Only GET_STATUS is allowed.")

        # 3. Battery check
        if robot_state.battery_pct <= BATTERY_CRITICAL_PCT:
            if action not in {ActionName.STOP, ActionName.EMERGENCY_STOP,
                              ActionName.GET_STATUS}:
                raise SafetyError(
                    f"Battery critical ({robot_state.battery_pct}%). "
                    "Only STOP and GET_STATUS are allowed."
                )

        # 4. Movement while arm is active
        if action in REQUIRES_STOPPED and robot_state.rover.is_moving:
            raise SafetyError(
                f"Action '{action}' requires rover to be stopped first."
            )

        # 5. Servo angle limits
        if "angle" in params:
            angle = params["angle"]
            if not (MIN_SERVO_ANGLE <= angle <= MAX_SERVO_ANGLE):
                raise SafetyError(
                    f"Servo angle {angle}° is out of range "
                    f"[{MIN_SERVO_ANGLE}°, {MAX_SERVO_ANGLE}°]."
                )

        # 6. Speed limits
        if "speed" in params:
            speed = params["speed"]
            if not (0 <= speed <= MAX_ROVER_SPEED):
                raise SafetyError(
                    f"Speed {speed} is out of range [0, {MAX_ROVER_SPEED}]."
                )

        log.debug(f"Safety check PASSED for '{action_name}'")

    def is_action_allowed(self, action_name: str, params: dict = None) -> bool:
        """Non-throwing version of validate_action."""
        try:
            self.validate_action(action_name, params)
            return True
        except (SafetyError, CommandError):
            return False


# Singleton
safety = SafetyValidator()
