"""
CYNEXIS — Camera & Vision API Routes
Provides endpoints for live MJPEG video streaming, JPEG frames, photo capture, video recording, and visual scene descriptions.
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from core.logger import get_logger
from core.state import robot_state

log = get_logger("routes_camera")
router = APIRouter(prefix="/camera", tags=["Camera & Vision"])


class DescribeRequest(BaseModel):
    prompt: Optional[str] = "Describe what you see."


@router.get("/status")
async def get_camera_status(request: Request):
    """Return camera hardware and streaming status."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        return {
            "active": False,
            "recording": False,
            "photos_taken": robot_state.camera.photos_taken,
            "fps": robot_state.camera.fps,
        }
    return camera.status()


@router.get("/frame")
async def get_single_frame(request: Request):
    """Return the latest camera frame as a JPEG image."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera subsystem not initialized",
        )

    jpeg_bytes = camera.get_jpeg_frame()
    if not jpeg_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No camera frame available",
        )

    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.get("/stream")
async def get_mjpeg_stream(request: Request):
    """
    Stream live video as multipart MJPEG.
    Compatible with standard HTML <img> tags and browser dashboard viewports.
    """
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera subsystem not initialized",
        )

    async def _frame_generator():
        while True:
            jpeg_bytes = camera.get_jpeg_frame()
            if jpeg_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
            await asyncio.sleep(0.04)  # ~25 FPS stream throttle

    return StreamingResponse(
        _frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/photo")
@router.post("/capture")
async def capture_photo(request: Request):
    """Capture a snapshot and save to the local Photos directory."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera subsystem not initialized",
        )

    filepath = await camera.capture()
    if not filepath:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture photo",
        )

    return {
        "success": True,
        "filepath": filepath,
        "photos_taken": robot_state.camera.photos_taken,
    }


@router.post("/record/start")
async def start_recording(request: Request):
    """Start saving live video to local Recordings directory."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera subsystem not initialized",
        )

    await camera.start_recording()
    return {"success": True, "recording": robot_state.camera.is_recording}


@router.post("/record/stop")
async def stop_recording(request: Request):
    """Stop active video recording."""
    camera = getattr(request.app.state, "camera", None)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera subsystem not initialized",
        )

    filepath = await camera.stop_recording()
    return {
        "success": True,
        "recording": robot_state.camera.is_recording,
        "filepath": filepath,
    }


@router.post("/describe")
async def describe_current_scene(payload: DescribeRequest, request: Request):
    """
    Capture current optical frame and pass to Vision Provider for natural language description.
    """
    camera = getattr(request.app.state, "camera", None)
    vision = getattr(request.app.state, "vision", None)

    if not camera or not vision:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera or Vision subsystem not initialized",
        )

    jpeg_bytes = camera.get_jpeg_frame()
    if not jpeg_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No camera frame available to describe",
        )

    description = await vision.describe_image(jpeg_bytes, prompt=payload.prompt)
    return {
        "success": True,
        "prompt": payload.prompt,
        "description": description,
    }
