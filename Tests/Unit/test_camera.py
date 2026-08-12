"""
CYNEXIS — Camera Unit Tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio
import pytest
import numpy as np
from Backend.Vision.camera import MockCamera, OpenCVCamera
from core.state import robot_state


@pytest.fixture
def camera():
    robot_state.camera.is_active = False
    robot_state.camera.is_recording = False
    robot_state.camera.photos_taken = 0
    return MockCamera()


@pytest.mark.asyncio
async def test_start_stop(camera):
    await camera.start()
    assert robot_state.camera.is_active is True
    await camera.stop()
    assert robot_state.camera.is_active is False


@pytest.mark.asyncio
async def test_capture(camera):
    await camera.start()
    filepath = await camera.capture()
    assert filepath is not None
    assert robot_state.camera.photos_taken == 1


@pytest.mark.asyncio
async def test_capture_fails_when_inactive(camera):
    filepath = await camera.capture()
    assert filepath is None


@pytest.mark.asyncio
async def test_recording(camera):
    await camera.start()
    await camera.start_recording()
    assert robot_state.camera.is_recording is True
    await camera.stop_recording()
    assert robot_state.camera.is_recording is False


@pytest.mark.asyncio
async def test_frame_retrieval(camera):
    await camera.start()
    frame = camera.get_frame()
    assert frame is not None
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)

    jpeg_bytes = camera.get_jpeg_frame()
    assert jpeg_bytes is not None
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0


@pytest.mark.asyncio
async def test_status(camera):
    await camera.start()
    status = camera.status()
    assert status["active"] is True
    assert status["recording"] is False
    assert status["photos_taken"] == 0
    assert status["width"] == 640
    assert status["height"] == 480


@pytest.mark.asyncio
async def test_opencv_camera_lifecycle():
    cam = OpenCVCamera(camera_id=0)
    await cam.start()
    st = cam.status()
    assert "active" in st
    assert "recording" in st
    assert "photos_taken" in st
    if st["active"]:
        await asyncio.sleep(0.2)
        frame = cam.get_frame()
        assert frame is not None
        jpeg = cam.get_jpeg_frame()
        assert jpeg is not None
    await cam.stop()
    assert cam._running is False
    assert cam.status()["active"] is False
