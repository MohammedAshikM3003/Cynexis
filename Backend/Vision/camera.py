"""
CYNEXIS — Camera System
Thread-safe OpenCV video capture, mock camera, JPEG frame streaming, photo capture, and video recording.
"""

import io
import time
import threading
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from datetime import datetime

import numpy as np
import cv2

from core.config import settings
from core.state import robot_state
from core.logger import get_logger

log = get_logger("camera")


class CameraInterface(ABC):
    """Abstract camera interface. All camera implementations adhere to this."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def capture(self) -> Optional[str]: ...

    @abstractmethod
    async def start_recording(self) -> None: ...

    @abstractmethod
    async def stop_recording(self) -> Optional[str]: ...

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]: ...

    @abstractmethod
    def get_jpeg_frame(self) -> Optional[bytes]: ...

    @abstractmethod
    def status(self) -> dict: ...


class MockCamera(CameraInterface):
    """Simulated high-fidelity synthetic camera for headless execution and testing."""

    def __init__(self):
        self._active = False
        self._recording = False
        self._photo_count = 0
        self._photo_dir = settings.resolve_path(settings.photo_path)
        self._video_dir = settings.resolve_path(settings.video_path)
        self._width = getattr(settings, "camera_width", 640)
        self._height = getattr(settings, "camera_height", 480)
        log.info("MockCamera initialized")

    async def start(self) -> None:
        self._active = True
        robot_state.camera.is_active = True
        log.info("MOCK: Camera started")

    async def stop(self) -> None:
        if self._recording:
            await self.stop_recording()
        self._active = False
        robot_state.camera.is_active = False
        log.info("MOCK: Camera stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        """Generate a simulated 640x480 RGB frame with telemetry overlay."""
        if not self._active:
            return None

        img = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        # Background gradient
        img[:, :] = (30, 20, 20)

        # Crosshair and bounding box
        cx, cy = self._width // 2, self._height // 2
        cv2.line(img, (cx - 40, cy), (cx + 40, cy), (0, 255, 128), 1)
        cv2.line(img, (cx, cy - 40), (cx, cy + 40), (0, 255, 128), 1)
        cv2.circle(img, (cx, cy), 25, (0, 255, 128), 1)

        # Telemetry HUD Text
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"CYNEXIS SIMULATED OPTICAL FEED", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(img, f"TIME: {now_str}", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(img, f"RES: {self._width}x{self._height} | FPS: 30", (20, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(img, f"MODE: NORMAL | STATUS: ONLINE", (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        return img

    def get_jpeg_frame(self) -> Optional[bytes]:
        """Return compressed JPEG bytes of the current simulated frame."""
        frame = self.get_frame()
        if frame is None:
            return None
        success, encoded_img = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return encoded_img.tobytes() if success else None

    async def capture(self) -> Optional[str]:
        if not self._active:
            log.warning("Cannot capture: camera not active")
            return None

        self._photo_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cynexis_photo_{ts}.jpg"
        filepath = self._photo_dir / filename

        frame = self.get_frame()
        if frame is not None:
            cv2.imwrite(str(filepath), frame)
        else:
            filepath.write_bytes(b"MOCK_IMAGE")

        self._photo_count += 1
        robot_state.camera.photos_taken = self._photo_count
        log.info(f"MOCK: Photo captured -> {filename}")
        return str(filepath)

    async def start_recording(self) -> None:
        if not self._active:
            log.warning("Cannot record: camera not active")
            return
        self._recording = True
        robot_state.camera.is_recording = True
        log.info("MOCK: Recording started")

    async def stop_recording(self) -> Optional[str]:
        self._recording = False
        robot_state.camera.is_recording = False
        log.info("MOCK: Recording stopped")
        return None

    def status(self) -> dict:
        return {
            "active": self._active,
            "recording": self._recording,
            "photos_taken": self._photo_count,
            "width": self._width,
            "height": self._height,
        }


class OpenCVCamera(CameraInterface):
    """
    OpenCV Camera implementation with threaded non-blocking frame capture.
    """

    def __init__(self, camera_id: Optional[int] = None):
        self._camera_id = camera_id if camera_id is not None else getattr(settings, "camera_device_index", 0)
        self._cap = None
        self._recording = False
        self._writer = None
        self._latest_frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._photo_dir = settings.resolve_path(settings.photo_path)
        self._video_dir = settings.resolve_path(settings.video_path)
        self._width = getattr(settings, "camera_width", 640)
        self._height = getattr(settings, "camera_height", 480)
        log.info(f"OpenCVCamera initialized (device={self._camera_id}, size={self._width}x{self._height})")

    def _capture_worker(self):
        """Dedicated background thread to continuously fetch frames."""
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                if self._recording and self._writer is not None:
                    self._writer.write(frame)
            time.sleep(0.01)

    async def start(self) -> None:
        if self._running:
            return

        def _open_camera():
            cap = cv2.VideoCapture(self._camera_id, cv2.CAP_DSHOW if cv2.__file__ else cv2.CAP_ANY)
            if not cap.isOpened():
                # Fallback to default API
                cap = cv2.VideoCapture(self._camera_id)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                ret, frame = cap.read()
                if ret and frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                return cap
            return None

        self._cap = await asyncio.to_thread(_open_camera)
        if self._cap and self._cap.isOpened():
            self._running = True
            robot_state.camera.is_active = True
            self._thread = threading.Thread(target=self._capture_worker, daemon=True)
            self._thread.start()
            log.info("OpenCV camera thread started successfully")
        else:
            log.warning(f"Could not open OpenCV camera index {self._camera_id}")
            robot_state.camera.is_active = False

    async def stop(self) -> None:
        self._running = False
        if self._recording:
            await self.stop_recording()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        robot_state.camera.is_active = False
        log.info("OpenCV camera stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_jpeg_frame(self) -> Optional[bytes]:
        frame = self.get_frame()
        if frame is None:
            return None
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return encoded.tobytes() if success else None

    async def capture(self) -> Optional[str]:
        frame = self.get_frame()
        if frame is None:
            return None

        self._photo_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cynexis_photo_{ts}.jpg"
        filepath = self._photo_dir / filename

        cv2.imwrite(str(filepath), frame)
        robot_state.camera.photos_taken += 1
        log.info(f"Photo captured -> {filename}")
        return str(filepath)

    async def start_recording(self) -> None:
        if not self._running or self._cap is None:
            return
        self._video_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cynexis_recording_{ts}.mp4"
        filepath = self._video_dir / filename
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(filepath), fourcc, 20.0, (self._width, self._height))
        self._recording = True
        robot_state.camera.is_recording = True
        log.info(f"Recording started -> {filename}")

    async def stop_recording(self) -> Optional[str]:
        if self._writer:
            self._writer.release()
            self._writer = None
        self._recording = False
        robot_state.camera.is_recording = False
        log.info("Recording stopped")
        return None

    def status(self) -> dict:
        return {
            "active": self._running and self._cap is not None and self._cap.isOpened(),
            "recording": self._recording,
            "photos_taken": robot_state.camera.photos_taken,
            "width": self._width,
            "height": self._height,
        }
