# CYNEXIS — Camera System Specification & Architecture

## 1. Main Purpose & Vision
The Cynexis Camera System gives the Cynexis Agent **eyes**. It is a robot-mounted visual system connected directly to the Cynexis agent, web dashboard, and cloud repository, supporting:
- 📷 Photograph Capture
- 🎥 Live Video Feed & Teleoperation Stream
- 🤖 Agent-Assisted Visual Analysis (VLM Integration)
- ☁️ Cloud Storage of Captured Images
- 🖼️ Remote Retrieval of Previous Images
- 🎬 Comprehensive Camera Status & Health Monitoring
- 🔦 Controllable White LED Illumination / Flash System
- 🔄 Remote Camera Controls via Web Dashboard and API
- 🌐 Cynexis Web & App Dashboard Integration
- 🗂️ Indexed Image History & Gallery
- 📍 Spatial Context via GPS Metadata Association

> **Architectural Principle**: Cloud storage is the primary image repository. Physical microSD card storage is **optional** and reserved strictly for offline buffering.

---

## 2. Overall Cynexis Camera Architecture

```text
                    ┌──────────────────────────┐
                    │       CYNEXIS AGENT      │
                    │                          │
                    │  Vision / AI Processing  │
                    └────────────┬─────────────┘
                                 │
                         Commands / Analysis
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────┐
│                     CYNEXIS ROVER                          │
│                                                            │
│   ┌──────────────┐       ┌─────────────────────────────┐  │
│   │ Camera       │──────▶│ Camera Controller           │  │
│   │ Module       │       │                             │  │
│   └──────────────┘       │ Capture / Stream / Control  │  │
│          │               └──────────────┬──────────────┘  │
│          │                              │                 │
│          ▼                              ▼                 │
│   ┌──────────────┐              ┌───────────────┐        │
│   │ LED / Light  │              │ Rover Network │        │
│   └──────────────┘              └───────┬───────┘        │
│                                         │                 │
└─────────────────────────────────────────┼─────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │   Internet / Cloud   │
                              └──────────┬───────────┘
                                         │
                         ┌───────────────┴──────────────┐
                         ▼                              ▼
                 ┌───────────────┐              ┌──────────────┐
                 │ Image Storage │              │ Cynexis Web  │
                 │ / Database    │              │ Dashboard    │
                 └───────────────┘              └──────────────┘
```

---

## 3. Hardware & Illumination Specifications
- **Optical Sensor**: Dedicated low-power, high-resolution digital camera module mounted on the rover.
- **Video & Still Capabilities**: 1080p RGB resolution at 25-30 FPS with low-latency encoding.
- **Illumination**: Separate controllable White LED light system (Camera sensor ≠ Illumination). Allows Cynexis agent and user to toggle flash/spotlight for low-light vision without saturation into the lens.
- **Drivers**: OpenCV VideoCapture (`cv2.CAP_DSHOW` / `cv2.CAP_ANY`) with background non-blocking frame buffer thread (`_capture_worker`).

---

## 4. Physical Mounting & Mechanical Geometry
Positioned at the front section of the rover chassis:
- **Arm Clearance**: Mounted clear of the top 4-DOF robotic arm sweep radius.
- **Obstruction Free**: Ensures unobstructed forward navigation FOV.
- **Protection**: Recessed housing protecting against physical impacts and vibration.
- **Interference Avoidance**: Separated from GPS antenna to avoid EMI.
- **Illumination Angle**: LED mounted adjacent but angled away from lens to avoid direct lens flare.

---

## 5. Software Operating Modes

### Mode 1 — Live View
Low-latency MJPEG stream (`/api/camera/stream`) delivered to the Cynexis Web Dashboard allowing real-time teleoperation.

### Mode 2 — Image Capture
Upon receiving a `Capture` command:
1. Trigger frame capture from buffer
2. Assign unique ID (e.g., `CYN-YYYYMMDD-HHMMSS-XXX`)
3. Attach timestamp & optional GPS coordinates
4. Upload image payload to Cloud Object Storage
5. Write metadata record to Database
6. Return structured JSON confirmation to client / agent

### Mode 3 — AI Vision Integration
Triggered by agent voice/text queries (e.g., *"What is in front of the rover?"*):
1. Snapshot frame requested by Agent Intent Engine
2. Sent to Vision-Language Model (VLM, e.g. Moondream2 / SmolVLM)
3. Scene description generated and returned to agent conversational loop

---

## 6. Cloud & Database Architecture

```text
                  ┌────────────────────────┐
                  │      CAPTURE ACTION    │
                  └───────────┬────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
   ┌──────────────────────┐     ┌──────────────────────┐
   │ Cloud Object Storage │     │ Metadata Database    │
   │  (image.jpg payload) │     │ (image_id, timestamp,│
   └──────────────────────┘     │  GPS, URLs, status)  │
                                └──────────────────────┘
```

### Database Schema (Image Metadata)
- `image_id`: String (Unique identifier)
- `timestamp`: ISO-8601 Datetime string
- `camera_id`: String (Front / Main camera identifier)
- `gps_latitude`: Float (Optional)
- `gps_longitude`: Float (Optional)
- `file_url`: String (Cloud storage URL)
- `thumbnail_url`: String (Optimized preview URL)
- `file_size`: Integer (Bytes)
- `resolution`: String ("1920x1080")
- `upload_status`: String ("completed", "pending", "failed")
- `ai_analysis_status`: String ("processed", "none")

---

## 7. Visual Data Tiers

1. **Live Feed**: Temporary streaming frames (not permanently stored).
2. **Captured Photographs**: Permanent high-res cloud artifacts with metadata.
3. **AI Vision Frames**: Ephemeral frames extracted specifically for VLM analysis.

---

## 8. Offline & Reliability Strategy

```text
             ┌── Network Available ──────▶ Direct Cloud Upload
             │
Captured ────┤
Photograph   │
             └── Network Unavailable ────▶ Temporary Local Buffer
                                                │
                                                ▼
                                           Auto-retry on reconnect
```

- When connected, photos stream straight to Cloud Storage.
- When offline, photos buffer to local disk (`./Photos/buffer/`), auto-uploading and clearing upon network recovery.

---

## 9. Security & Authentication
- Authenticated control API endpoints (`POST /api/camera/capture`, `POST /api/camera/light`).
- Authorized tokens for live stream access.
- Encrypted HTTPS/WSS transport between Rover, Server, and Dashboard.

---

## 10. Development Roadmap
- **Phase 1**: Camera hardware initialization & threaded OpenCV capture worker.
- **Phase 2**: Rover chassis mount, LED light control relay integration.
- **Phase 3**: Web Dashboard live stream & camera control page.
- **Phase 4**: Cloud Object Storage upload pipeline & metadata SQLite/Database sync.
- **Phase 5**: VLM Agent visual command integration ("What do you see?").
- **Phase 6**: GPS telemetry association & spatial image map overlay.
- **Phase 7**: Offline buffer retry queue & health monitor telemetry.
