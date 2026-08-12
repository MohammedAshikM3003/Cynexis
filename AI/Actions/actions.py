"""
CYNEXIS — Predefined Actions
All robot actions with their handlers. Registered at startup.

ARCHITECTURE RULE:
    Action handlers REQUEST operations via controllers.
    Controllers PERFORM operations and update state.
    Action handlers NEVER directly mutate hardware-related robot_state fields.
"""

from core.constants import ActionName, SafetyLevel, SystemMode, MAX_ROVER_SPEED
from core.state import robot_state
from core.logger import get_logger
from AI.Actions.registry import ActionDefinition, registry

log = get_logger("actions")

# ============================================================
# CONTROLLER REFERENCES
# Injected at startup by server.py lifespan. None until then.
# ============================================================
_rover = None
_arm = None
_gripper = None
_camera = None
_vision = None


def inject_controllers(rover=None, arm=None, gripper=None, camera=None, vision=None):
    """
    Inject controller references so action handlers can delegate.
    Called once during server lifespan startup.
    """
    global _rover, _arm, _gripper, _camera, _vision
    _rover = rover
    _arm = arm
    _gripper = gripper
    _camera = camera
    _vision = vision
    log.info("Controllers and Vision injected into action layer")


# ============================================================
# ACTION HANDLERS — delegate to controllers
# ============================================================

async def action_hello() -> dict:
    """Greet the audience."""
    log.info("CYNEXIS says hello!")
    return {"speech": "Hello everyone. I am CYNEXIS."}


async def action_introduce_self() -> dict:
    """Full introduction."""
    return {"speech": (
        "Hello. I am CYNEXIS, an AI-powered gesture-controlled robotic platform. "
        "I can be controlled with hand gestures, voice commands, and through my API."
    )}


async def action_wave() -> dict:
    """Wave gesture — arm movement sequence."""
    log.info("Performing wave gesture")
    if _arm:
        await _arm.shoulder_position(140.0)
        await _arm.wrist_position(45.0)
        await _arm.wrist_position(135.0)
        await _arm.wrist_position(45.0)
        await _arm.wrist_position(90.0)
        await _arm.shoulder_position(90.0)
    return {"arm_sequence": "wave", "speech": "Hello!"}


async def action_nod() -> dict:
    """Nod gesture — arm shoulder dip."""
    log.info("Performing nod gesture")
    if _arm:
        await _arm.shoulder_position(75.0)
        await _arm.shoulder_position(90.0)
    return {"arm_sequence": "nod"}


async def action_stop() -> dict:
    """Stop all movement immediately."""
    if _rover:
        await _rover.stop()
    if _arm:
        await _arm.stop()
    log.info("All movement stopped")
    return {"stopped": True}


async def action_forward(speed: int = 150) -> dict:
    """Move rover forward. Speed clamped to MAX_ROVER_SPEED."""
    speed = max(0, min(speed, MAX_ROVER_SPEED))
    if _rover:
        await _rover.forward(speed)
    return {"direction": "FORWARD", "speed": speed}


async def action_backward(speed: int = 150) -> dict:
    """Move rover backward. Speed clamped to MAX_ROVER_SPEED."""
    speed = max(0, min(speed, MAX_ROVER_SPEED))
    if _rover:
        await _rover.backward(speed)
    return {"direction": "BACKWARD", "speed": speed}


async def action_left(speed: int = 150) -> dict:
    """Turn rover left. Speed clamped to MAX_ROVER_SPEED."""
    speed = max(0, min(speed, MAX_ROVER_SPEED))
    if _rover:
        await _rover.left(speed)
    return {"direction": "LEFT", "speed": speed}


async def action_right(speed: int = 150) -> dict:
    """Turn rover right. Speed clamped to MAX_ROVER_SPEED."""
    speed = max(0, min(speed, MAX_ROVER_SPEED))
    if _rover:
        await _rover.right(speed)
    return {"direction": "RIGHT", "speed": speed}


async def action_grip_open() -> dict:
    """Open the gripper."""
    if _gripper:
        await _gripper.open()
    return {"gripper": "open"}


async def action_grip_close() -> dict:
    """Close the gripper."""
    if _gripper:
        await _gripper.close()
    return {"gripper": "closed"}


async def action_arm_up() -> dict:
    """Raise arm shoulder by 15°."""
    new_angle = min(robot_state.arm.shoulder.angle + 15, 270)
    if _arm:
        await _arm.shoulder_position(new_angle)
    return {"shoulder_angle": robot_state.arm.shoulder.angle}


async def action_arm_down() -> dict:
    """Lower arm shoulder by 15°."""
    new_angle = max(robot_state.arm.shoulder.angle - 15, 0)
    if _arm:
        await _arm.shoulder_position(new_angle)
    return {"shoulder_angle": robot_state.arm.shoulder.angle}


async def action_photo() -> dict:
    """Capture a photo via camera controller."""
    filepath = None
    if _camera:
        filepath = await _camera.capture()
    else:
        # Fallback for test without camera injection
        robot_state.camera.photos_taken += 1
    log.info(f"Photo captured (total: {robot_state.camera.photos_taken})")
    return {"photo_count": robot_state.camera.photos_taken, "filepath": filepath}


async def action_start_recording() -> dict:
    """Start video recording via camera controller."""
    if _camera:
        await _camera.start_recording()
    return {"recording": robot_state.camera.is_recording}


async def action_stop_recording() -> dict:
    """Stop video recording via camera controller."""
    if _camera:
        await _camera.stop_recording()
    return {"recording": robot_state.camera.is_recording}


async def action_describe_scene() -> dict:
    """Analyze current camera optical feed and describe visible objects/environment."""
    description = "I see an open laboratory workspace with clear pathways ahead."
    if _camera and _vision:
        jpeg_bytes = _camera.get_jpeg_frame()
        if jpeg_bytes:
            description = await _vision.describe_image(jpeg_bytes, prompt="Describe what you see.")
    elif _vision:
        description = await _vision.describe_image(b"MOCK_FRAME")
    log.info(f"Scene described: '{description}'")
    return {"speech": description, "description": description}


async def action_get_status() -> dict:
    """Return current robot state."""
    robot_state.update_uptime()
    return robot_state.model_dump()


async def action_emergency_stop() -> dict:
    """
    Emergency stop — halt ALL actuators immediately.
    Stops: rover, arm, AND releases gripper.
    """
    robot_state.mode = SystemMode.EMERGENCY
    if _rover:
        await _rover.emergency_stop()
    if _arm:
        await _arm.stop()
    if _gripper:
        await _gripper.open()  # Release gripper for safety
    log.warning("EMERGENCY STOP activated — all actuators halted, gripper released")
    return {"emergency": True}


# ============================================================
# REGISTER ALL ACTIONS
# ============================================================

def register_all_actions() -> None:
    """Register all predefined actions into the registry."""
    definitions = [
        ActionDefinition(ActionName.HELLO, "Greet the audience", action_hello),
        ActionDefinition(ActionName.INTRODUCE_SELF, "Full introduction", action_introduce_self),
        ActionDefinition(ActionName.WAVE, "Wave gesture", action_wave, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.NOD, "Nod gesture", action_nod, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.STOP, "Stop all movement", action_stop, SafetyLevel.CRITICAL,
                         allowed_modes=list(SystemMode)),
        ActionDefinition(ActionName.FORWARD, "Move forward", action_forward, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.BACKWARD, "Move backward", action_backward, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.LEFT, "Turn left", action_left, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.RIGHT, "Turn right", action_right, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.GRIP_OPEN, "Open gripper", action_grip_open, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.GRIP_CLOSE, "Close gripper", action_grip_close, SafetyLevel.MEDIUM),
        ActionDefinition(ActionName.ARM_UP, "Raise arm", action_arm_up, SafetyLevel.HIGH),
        ActionDefinition(ActionName.ARM_DOWN, "Lower arm", action_arm_down, SafetyLevel.HIGH),
        ActionDefinition(ActionName.PHOTO, "Take photo", action_photo),
        ActionDefinition(ActionName.START_RECORDING, "Start recording", action_start_recording),
        ActionDefinition(ActionName.STOP_RECORDING, "Stop recording", action_stop_recording),
        ActionDefinition(ActionName.DESCRIBE_SCENE, "Describe visible scene", action_describe_scene),
        ActionDefinition(ActionName.GET_STATUS, "Get robot status", action_get_status,
                         allowed_modes=list(SystemMode)),
        ActionDefinition(ActionName.EMERGENCY_STOP, "Emergency stop", action_emergency_stop,
                         SafetyLevel.CRITICAL, allowed_modes=list(SystemMode)),
    ]
    for defn in definitions:
        registry.register(defn)
    log.info(f"Registered {len(definitions)} actions")
