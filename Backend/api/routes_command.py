"""
CYNEXIS — Command Routes
POST /api/command — validates via safety → action registry → execute.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import time
from datetime import datetime, timezone

from core.state import robot_state
from core.constants import ActionName
from core.logger import get_logger
from Backend.Robot.Safety.safety import safety
from AI.Actions.registry import registry

log = get_logger("api.command")

router = APIRouter(tags=["command"])


class CommandRequest(BaseModel):
    """API command request body."""
    action: str = Field(..., description="Action name from the whitelist")
    params: dict = Field(default_factory=dict, description="Action parameters")
    source: str = Field(default="api", description="Command source")


class CommandResponse(BaseModel):
    """API command response."""
    success: bool
    action: str
    message: str
    data: Optional[dict] = None
    duration_ms: int = 0


@router.post("/command", response_model=CommandResponse)
async def execute_command(cmd: CommandRequest, request: Request):
    """
    Execute a robot command.

    The command must:
    1. Be in the action whitelist
    2. Pass safety validation
    3. Have a registered handler
    """
    start = time.time()
    db = request.app.state.db

    # Step 1: Safety validation
    try:
        safety.validate_action(cmd.action, cmd.params)
    except Exception as e:
        await db.log_command(cmd.action, cmd.source, "rejected", error_message=str(e))
        log.warning(f"Command rejected: {cmd.action} — {e}")
        raise HTTPException(status_code=403, detail=str(e))

    # Step 2: Execute through action registry
    result = await registry.execute(cmd.action, cmd.params)
    duration_ms = int((time.time() - start) * 1000)

    # Step 3: Log to database
    status = "completed" if result.get("success") else "error"
    await db.log_command(
        cmd.action, cmd.source, status,
        error_message=result.get("message", ""),
        duration_ms=duration_ms,
    )

    # Step 4: Update robot state
    if result.get("success"):
        try:
            robot_state.current_action = ActionName(cmd.action)
            robot_state.last_action = ActionName(cmd.action)
            robot_state.last_action_time = datetime.now(timezone.utc)
        except ValueError:
            pass

    return CommandResponse(
        success=result.get("success", False),
        action=cmd.action,
        message=result.get("message", ""),
        data=result.get("data"),
        duration_ms=duration_ms,
    )
