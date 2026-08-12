# CYNEXIS — Robot API Reference

## Base URL

```
http://localhost:8000
```

---

## Health

### `GET /health`
Basic health check.

**Response:**
```json
{
    "status": "ok",
    "name": "CYNEXIS",
    "version": "1.0.0",
    "mock_mode": true
}
```

### `GET /api/diagnostics`
Full system diagnostics including all subsystem states.

---

## Robot State

### `GET /api/status`
Full robot state (battery, rover, arm, gripper, camera, sensors, AI, network).

### `GET /api/robot`
Rover subsystem state (mode, connection, battery, rover direction/speed).

### `GET /api/arm`
Arm joint angles (shoulder, elbow, wrist).

### `GET /api/gripper`
Gripper state (position 0–100, is_gripping).

### `GET /api/sensors`
Sensor readings (distance, roll, pitch, flex values, temperature).

---

## Commands

### `POST /api/command`
Execute a robot command through the safety layer.

**Request:**
```json
{
    "action": "HELLO",
    "params": {},
    "source": "api"
}
```

**Response (200):**
```json
{
    "success": true,
    "action": "HELLO",
    "message": "Action 'HELLO' completed",
    "data": {"speech": "Hello everyone. I am CYNEXIS."},
    "duration_ms": 12
}
```

**Response (403) — rejected:**
```json
{
    "detail": "Unknown action 'HACK_MOTORS'. Only predefined actions are allowed."
}
```

### Valid Actions

| Action | Description | Safety Level |
|--------|-------------|:------------:|
| `HELLO` | Greet audience | LOW |
| `INTRODUCE_SELF` | Full introduction | LOW |
| `WAVE` | Wave gesture | MEDIUM |
| `NOD` | Nod gesture | MEDIUM |
| `STOP` | Stop all movement | CRITICAL |
| `FORWARD` | Move rover forward | MEDIUM |
| `BACKWARD` | Move rover backward | MEDIUM |
| `LEFT` | Turn rover left | MEDIUM |
| `RIGHT` | Turn rover right | MEDIUM |
| `ARM_UP` | Raise arm shoulder | HIGH |
| `ARM_DOWN` | Lower arm shoulder | HIGH |
| `GRIP_OPEN` | Open gripper | MEDIUM |
| `GRIP_CLOSE` | Close gripper | MEDIUM |
| `PHOTO` | Capture a photo | LOW |
| `START_RECORDING` | Start video recording | LOW |
| `STOP_RECORDING` | Stop video recording | LOW |
| `GET_STATUS` | Get robot status | LOW |
| `EMERGENCY_STOP` | Emergency stop all | CRITICAL |

---

## Camera

### `GET /api/camera`
Camera subsystem state.

### `GET /api/photos`
List recent photos. Query: `?limit=20`

### `POST /api/capture`
Take a photo. Returns filepath.

### `POST /api/recording/start`
Start video recording.

### `POST /api/recording/stop`
Stop video recording.

---

## WebSocket

### `ws://localhost:8000/ws/telemetry`
Real-time telemetry at ~2 Hz.

**Message format:**
```json
{
    "type": "telemetry",
    "mode": "NORMAL",
    "connection": "CONNECTED",
    "battery_pct": 100,
    "uptime_s": 42.3,
    "rover": {"speed": 0, "direction": "STOPPED", "is_moving": false},
    "arm": {"shoulder": 90.0, "elbow": 90.0, "wrist": 90.0},
    "gripper": {"position": 0.0, "is_gripping": false},
    "camera": {"active": true, "recording": false, "photos": 3},
    "ai": {"llm_loaded": true, "stt_loaded": true, "tts_loaded": true},
    "current_action": null,
    "errors": []
}
```
