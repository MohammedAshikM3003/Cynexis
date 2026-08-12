# CYNEXIS — Software Architecture

## Overview

CYNEXIS software follows a **layered, modular architecture** designed around safety and offline-first operation.

```
┌──────────────────────────────────────────────┐
│                  FRONTEND                    │
│              (React Dashboard)               │
├──────────────────────────────────────────────┤
│              FastAPI + WebSocket             │
│           /api/* endpoints + /ws/*           │
├──────────────────────────────────────────────┤
│    ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│    │  VOICE   │  │  GESTURE │  │   API   │  │
│    │ PIPELINE │  │  SYSTEM  │  │ COMMAND │  │
│    └────┬─────┘  └────┬─────┘  └────┬────┘  │
│         │             │             │        │
│    ┌────▼─────────────▼─────────────▼────┐   │
│    │         SAFETY VALIDATOR            │   │
│    └────────────────┬────────────────────┘   │
│                     │                        │
│    ┌────────────────▼────────────────────┐   │
│    │         ACTION REGISTRY             │   │
│    └────────────────┬────────────────────┘   │
│                     │                        │
│    ┌───────┐  ┌─────┴──┐  ┌────────┐        │
│    │ ROVER │  │  ARM   │  │ GRIPPER│        │
│    └───┬───┘  └───┬────┘  └───┬────┘        │
├────────┼──────────┼───────────┼──────────────┤
│   ┌────▼──────────▼───────────▼────┐         │
│   │          ESP32 SERIAL          │         │
│   └────────────────────────────────┘         │
└──────────────────────────────────────────────┘
```

## Safety Architecture

```
USER → MICROPHONE → STT → INTENT → COMMAND VALIDATOR →
ACTION REGISTRY → SAFETY LAYER → ROBOT CONTROLLER → ESP32 → MOTOR/SERVO
```

**The LLM NEVER directly controls hardware.**

- All actions pass through a whitelist.
- No `eval()`, no `exec()`, no arbitrary execution.
- Invalid commands are rejected.
- Emergency stop overrides everything.

## Module Map

| Module | Path | Purpose |
|--------|------|---------|
| Core Config | `core/config.py` | Settings from `.env` |
| Core Logger | `core/logger.py` | Structured JSON logging |
| Core State | `core/state.py` | Central robot state (Pydantic) |
| Core Constants | `core/constants.py` | Enums, action whitelist, limits |
| Core Events | `core/events.py` | Pub/sub event bus |
| Core Exceptions | `core/exceptions.py` | Error hierarchy |
| Database | `Database/database.py` | Async SQLite manager |
| Rover | `Backend/Robot/rover.py` | Mock + ESP32 rover control |
| Arm | `Backend/Robot/arm.py` | Mock arm control (4-DOF) |
| Gripper | `Backend/Robot/gripper.py` | Mock gripper control |
| Safety | `Backend/Robot/Safety/safety.py` | Command validation |
| Gestures | `Backend/Robot/Gestures/classifier.py` | Sensor-to-command pipeline |
| Camera | `Backend/Vision/camera.py` | Mock + OpenCV camera |
| Streaming | `Backend/Vision/streaming.py` | Transport abstraction |
| Sensors | `Backend/Sensors/` | MPU6050, flex sensor mocks |
| Sync | `Backend/Sync/` | Offline-first cloud sync |
| API Server | `Backend/API/server.py` | FastAPI app |
| API Routes | `Backend/API/routes_*.py` | REST endpoints |
| WebSocket | `Backend/API/ws_telemetry.py` | Real-time telemetry |
| LLM | `AI/LLM/provider.py` | Abstract + Mock LLM |
| STT | `AI/STT/provider.py` | Abstract + Mock STT |
| TTS | `AI/TTS/provider.py` | Abstract + Mock TTS |
| Intent | `AI/Intent/engine.py` | Pattern-based intent mapping |
| Memory | `AI/Memory/provider.py` | Conversation + system memory |
| Pipeline | `AI/pipeline.py` | Voice processing pipeline |
| Personality | `AI/personality.py` | CYNEXIS tone/responses |
| Actions | `AI/Actions/` | Registry + predefined actions |

## Mock Mode

When `MOCK_MODE=true` in `.env`:
- All hardware controllers use mock implementations
- Camera generates placeholder images
- AI uses canned responses
- System is fully testable without any hardware
