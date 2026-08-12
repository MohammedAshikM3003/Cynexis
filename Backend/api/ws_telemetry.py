"""
CYNEXIS — WebSocket Telemetry
/ws/telemetry — broadcasts robot state as structured JSON at ~2 Hz.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.state import robot_state
from core.constants import TELEMETRY_RATE_HZ
from core.logger import get_logger

log = get_logger("ws.telemetry")

router = APIRouter()

# Connected WebSocket clients
_clients: set[WebSocket] = set()


@router.websocket("/ws/telemetry")
async def telemetry_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time robot telemetry.
    Broadcasts state at TELEMETRY_RATE_HZ (~2 Hz).
    """
    await websocket.accept()
    _clients.add(websocket)
    log.info(f"Telemetry client connected ({len(_clients)} total)")

    try:
        while True:
            robot_state.update_uptime()
            state_data = {
                "type": "telemetry",
                "mode": str(robot_state.mode),
                "connection": str(robot_state.connection),
                "battery_pct": robot_state.battery_pct,
                "uptime_s": round(robot_state.uptime_s, 1),
                "rover": robot_state.rover.model_dump(),
                "arm": {
                    "base": robot_state.arm.base.angle,
                    "shoulder": robot_state.arm.shoulder.angle,
                    "elbow": robot_state.arm.elbow.angle,
                    "wrist": robot_state.arm.wrist.angle,
                    "is_moving": robot_state.arm.is_moving,
                },
                "gripper": robot_state.gripper.model_dump(),
                "sensors": robot_state.sensors.model_dump(),
                "hand": robot_state.hand.model_dump(),
                "camera": {
                    "active": robot_state.camera.is_active,
                    "recording": robot_state.camera.is_recording,
                    "photos": robot_state.camera.photos_taken,
                },
                "ai": robot_state.ai.model_dump(),
                "current_action": robot_state.current_action.value
                                  if robot_state.current_action else None,
                "errors": robot_state.errors[-5:],  # Last 5 errors
            }
            await websocket.send_text(json.dumps(state_data))
            await asyncio.sleep(1.0 / TELEMETRY_RATE_HZ)

    except WebSocketDisconnect:
        _clients.discard(websocket)
        log.info(f"Telemetry client disconnected ({len(_clients)} remaining)")
    except Exception as e:
        _clients.discard(websocket)
        log.error(f"WebSocket error: {e}")
