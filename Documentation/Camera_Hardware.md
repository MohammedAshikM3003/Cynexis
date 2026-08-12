# CYNEXIS — Camera Hardware Interface Specification

## 1. Physical Device Overview
* **Primary Optical Sensor**: Integrated Digital USB/DSHOW Camera (`Device 0`)
* **Backend Driver**: OpenCV VideoCapture (`cv2.CAP_DSHOW` / `cv2.CAP_ANY`)
* **Default Resolution**: 640 x 480 (VGA RGB)
* **Target Stream Frame Rate**: 25-30 FPS
* **Capture Architecture**: Threaded background frame buffer reader (`_capture_worker`) with atomic `threading.Lock` frame synchronization to prevent blocking the async FastAPI event loop.

## 2. Supported Features
1. **Continuous Video Streaming**: Real-time MJPEG delivery via `GET /api/camera/stream` (multipart/x-mixed-replace).
2. **Raw Single Frame Retrieval**: `GET /api/camera/frame` returning standard JPEG byte payload.
3. **High-Resolution Photo Capture**: `POST /api/camera/photo` and `POST /api/capture` saving timestamped images to `./Photos/cynexis_photo_%Y%m%d_%H%M%S.jpg`.
4. **Video Recording**: `POST /api/camera/record/start` and `POST /api/camera/record/stop` saving encoded `.avi` video clips to `./Recordings/`.
5. **Hardware Status Telemetry**: `GET /api/camera/status` reporting stream state, dimensions, and photo counts.

## 3. Fallback Mechanism
If the physical camera is missing or in use by another application, the system automatically falls back to `MockCamera` providing synthetic HUD overlays with timestamp telemetry.
