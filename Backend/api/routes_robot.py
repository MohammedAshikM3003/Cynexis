"""
CYNEXIS — Robot State Routes
GET /api/status, GET /api/robot, GET /api/arm, GET /api/gripper, GET /api/sensors
"""

from fastapi import APIRouter, Request, HTTPException
from core.state import robot_state

router = APIRouter(tags=["robot"])


@router.get("/status")
async def get_status():
    """Full robot state."""
    robot_state.update_uptime()
    return robot_state.model_dump()


@router.get("/robot")
async def get_robot():
    """Rover subsystem state."""
    return {
        "mode": robot_state.mode,
        "connection": robot_state.connection,
        "battery_pct": robot_state.battery_pct,
        "rover": robot_state.rover.model_dump(),
    }


@router.get("/arm")
async def get_arm():
    """Arm subsystem state."""
    return robot_state.arm.model_dump()


@router.get("/gripper")
async def get_gripper():
    """Gripper subsystem state."""
    return robot_state.gripper.model_dump()


@router.get("/sensors")
async def get_sensors():
    """Sensor readings."""
    return robot_state.sensors.model_dump()


@router.get("/hand")
async def get_hand():
    """Hand gesture telemetry and bend state."""
    return robot_state.hand.model_dump()


@router.post("/capture")
async def capture_photo(request: Request):
    """POST /api/capture photo endpoint."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(status_code=503, detail="Camera subsystem not initialized")
    filepath = await camera.capture()
    return {
        "success": True,
        "filepath": filepath,
        "photos_taken": robot_state.camera.photos_taken,
    }
