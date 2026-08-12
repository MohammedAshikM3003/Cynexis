# CYNEXIS — Development Setup

## Prerequisites

- Python 3.12+
- Git
- Arduino IDE (for ESP32 firmware)

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/Cynexis.git
cd Cynexis
```

### 2. Create virtual environment (already done)
```bash
python -m venv .venv
```

### 3. Activate virtual environment
```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate

# Windows (CMD)
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate
```

### 4. Install dependencies
```bash
# Production
pip install -r requirements.txt

# Development (includes testing tools)
pip install -r requirements-dev.txt
```

### 5. Create .env
```bash
copy .env.example .env
```

## Running

### Start the server (mock mode)
```bash
python main.py --mock
```

### Start with custom port
```bash
python main.py --port 9000
```

### Start with auto-reload (development)
```bash
python main.py --mock --reload
```

### API will be available at:
```
http://localhost:8000/health          → Health check
http://localhost:8000/api/status      → Full robot state
http://localhost:8000/api/diagnostics → System diagnostics
http://localhost:8000/api/voice/status→ Voice & TTS subsystem status
http://localhost:8000/voice           → Voice Pipeline Laboratory Web UI
http://localhost:8000/docs            → Swagger UI (auto-generated)
```

## Testing

### Run all tests
```bash
python -m pytest Tests/ -v
```

### Run only unit tests
```bash
python -m pytest Tests/Unit/ -v
```

### Run only integration tests
```bash
python -m pytest Tests/Integration/ -v
```

### Run specific test file
```bash
python -m pytest Tests/Unit/test_intent.py -v
```

## Project Structure (Software)

```
D:\Cynexis\
├── main.py                          ← Entry point
├── .env.example                     ← Environment template
├── requirements.txt                 ← Production dependencies
├── requirements-dev.txt             ← Dev dependencies
│
├── core/                            ← Core system
│   ├── config.py                    ← Settings from .env
│   ├── logger.py                    ← Structured logging
│   ├── state.py                     ← Central robot state
│   ├── constants.py                 ← Enums, limits, whitelist
│   ├── events.py                    ← Pub/sub event bus
│   └── exceptions.py               ← Error hierarchy
│
├── Backend/
│   ├── api/                         ← FastAPI server + routes
│   │   ├── server.py                ← App + lifespan
│   │   ├── routes_health.py         ← /health, /diagnostics
│   │   ├── routes_robot.py          ← /status, /robot, /arm, /gripper
│   │   ├── routes_camera.py         ← /camera, /photos, /capture
│   │   ├── routes_command.py        ← /command (safety-validated)
│   │   └── ws_telemetry.py          ← /ws/telemetry
│   ├── Robot/
│   │   ├── rover.py                 ← Mock + ESP32 rover
│   │   ├── arm.py                   ← Mock arm (4-DOF)
│   │   ├── gripper.py               ← Mock gripper
│   │   ├── Safety/safety.py         ← Command validation
│   │   └── Gestures/classifier.py   ← Sensor→command pipeline
│   ├── Vision/
│   │   ├── camera.py                ← Mock + OpenCV camera
│   │   └── streaming.py             ← Transport abstraction
│   ├── Sensors/
│   │   ├── base.py                  ← Sensor interface
│   │   ├── mpu6050.py               ← Mock IMU
│   │   └── flex.py                  ← Mock flex sensor
│   └── Sync/
│       ├── sync_manager.py          ← Offline-first sync
│       └── connection_monitor.py    ← Internet detection
│
├── AI/
│   ├── Actions/
│   │   ├── registry.py              ← Action registry
│   │   ├── actions.py               ← 18 predefined actions
│   │   └── sequences.py             ← Compound sequences
│   ├── Intent/engine.py             ← Pattern-based NLU
│   ├── LLM/provider.py              ← Abstract + Mock LLM
│   ├── STT/provider.py              ← Abstract + Mock STT
│   ├── TTS/provider.py              ← Abstract + Mock TTS
│   ├── Memory/provider.py           ← Conversation memory
│   ├── pipeline.py                  ← Voice processing pipeline
│   └── personality.py               ← CYNEXIS personality
│
├── Database/
│   ├── schema.sql                   ← SQLite schema
│   └── database.py                  ← Async DB manager
│
└── Tests/
    ├── conftest.py                  ← Shared fixtures
    ├── Unit/                        ← 9 test files, 79 tests
    └── Integration/                 ← 1 test file, 7 tests
```
