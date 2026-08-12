# CYNEXIS — ESP32 Communication Protocol

## Overview

CYNEXIS uses a two-layer communication architecture:

```
Laptop (Python)
    │
    │ USB Serial (JSON-over-serial, newline-delimited)
    │
Gateway ESP32
    │
    │ ESP-NOW (binary packets, cynexis_protocol.h)
    │
Robot ESP32
    │
    │ GPIO / I2C / PWM
    │
Motors • Servos • Sensors
```

**Layer 1 (this document):** Laptop ↔ Gateway — JSON over USB serial  
**Layer 2 (see `Protocol/cynexis_protocol.h`):** Gateway ↔ Robot — binary ESP-NOW

## Protocol Version

Current version: **1**

The `v` field must be present in every message. Messages with mismatched versions are rejected.

## Wire Format

- **Encoding:** UTF-8 JSON
- **Delimiter:** Newline (`\n`) — one message per line
- **Max size:** 512 bytes per message
- **Baud rate:** 115200 (configurable)

## Message Structure

Every message contains these required fields:

| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Protocol version (currently `1`) |
| `type` | string | Message type (see below) |
| `id` | string | Unique message ID (`cmd-000001` format) |
| `ts` | int | Timestamp in milliseconds since epoch |
| `cs` | string | SHA-256 checksum (first 8 hex chars) |

### Optional Fields

| Field | Type | Present In |
|-------|------|------------|
| `cmd` | string | COMMAND |
| `params` | object | COMMAND (when parameters needed) |
| `status` | string | ACK |
| `code` | string | NAK, ERROR |
| `data` | object | TELEMETRY, STATUS, ERROR |

## Message Types

### COMMAND (Laptop → Gateway)

Execute a robot command.

```json
{"v":1,"type":"COMMAND","id":"cmd-000001","ts":1723276800000,"cmd":"FORWARD","params":{"speed":150},"cs":"abcd1234"}
```

### ACK (Gateway → Laptop)

Command accepted and executed.

```json
{"v":1,"type":"ACK","id":"cmd-000001","ts":1723276800010,"status":"EXECUTED","cs":"ef567890"}
```

Status values: `EXECUTED`, `ACCEPTED`, `QUEUED`, `MOTORS_DISABLED`

### NAK (Gateway → Laptop)

Command rejected.

```json
{"v":1,"type":"NAK","id":"cmd-000001","ts":1723276800010,"code":"INVALID_COMMAND","cs":"12345678"}
```

Error codes: `INVALID_COMMAND`, `INVALID_PARAMS`, `INVALID_CHECKSUM`, `INVALID_VERSION`, `TIMEOUT`, `HARDWARE_FAULT`, `MOTORS_DISABLED`, `BUSY`, `UNKNOWN`

### PING (Laptop → Gateway)

Heartbeat request.

```json
{"v":1,"type":"PING","id":"cmd-000002","ts":1723276801000,"cs":"aabbccdd"}
```

### PONG (Gateway → Laptop)

Heartbeat response. Uses the same `id` as the PING.

```json
{"v":1,"type":"PONG","id":"cmd-000002","ts":1723276801005,"cs":"eeff0011"}
```

### TELEMETRY (Gateway → Laptop)

Periodic sensor data from the robot ESP32.

```json
{"v":1,"type":"TELEMETRY","id":"telem","ts":1723276802000,"data":{"battery_pct":85,"temperature_c":32.5,"rssi":-45,"state":1,"motor_cmd":0,"error_code":0},"cs":"22334455"}
```

### ERROR (Gateway → Laptop)

Error report.

```json
{"v":1,"type":"ERROR","id":"err","ts":1723276803000,"code":"HARDWARE_FAULT","data":{"message":"PCA9685 not responding"},"cs":"66778899"}
```

### STATUS (Bidirectional)

Status request/response.

```json
{"v":1,"type":"STATUS","id":"cmd-000003","ts":1723276804000,"data":{"firmware_version":"1.0.0","uptime_ms":120000,"motors_enabled":false},"cs":"aabb1122"}
```

## Command Whitelist

Only these commands are accepted. All others are rejected with `INVALID_COMMAND`.

| Category | Commands |
|----------|----------|
| Rover Movement | `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP` |
| System | `PING`, `STATUS`, `EMERGENCY_STOP` |
| Camera | `PHOTO`, `START_RECORDING`, `STOP_RECORDING` |
| Arm | `ARM_HOME`, `BASE`, `SHOULDER`, `ELBOW`, `WRIST` |
| Gripper | `GRIP_OPEN`, `GRIP_CLOSE` |

**NOT allowed:** Arbitrary GPIO commands, servo commands, shell commands.

## Command Parameters

| Command | Parameters | Example |
|---------|-----------|---------|
| `FORWARD` | `speed` (0-255) | `{"speed": 150}` |
| `BACKWARD` | `speed` (0-255) | `{"speed": 150}` |
| `LEFT` | `speed` (0-255) | `{"speed": 120}` |
| `RIGHT` | `speed` (0-255) | `{"speed": 120}` |
| `STOP` | none | — |
| `EMERGENCY_STOP` | none | — |
| `BASE` | `angle` (0-180) | `{"angle": 90}` |
| `SHOULDER` | `angle` (0-180) | `{"angle": 45}` |
| `ELBOW` | `angle` (0-180) | `{"angle": 135}` |
| `WRIST` | `angle` (0-180) | `{"angle": 90}` |
| `ARM_HOME` | none | — |
| `GRIP_OPEN` | none | — |
| `GRIP_CLOSE` | none | — |

## Checksum

Checksum is computed as the first 8 hex characters of SHA-256 over the JSON payload **without** the `cs` field.

```python
# Python side
payload = json.dumps(fields_without_cs, separators=(",", ":"), sort_keys=True)
checksum = hashlib.sha256(payload.encode()).hexdigest()[:8]
```

The ESP32 gateway firmware uses a simplified checksum (`"00000000"`) for outgoing messages due to embedded constraints. The Python side accepts this.

## Acknowledgement Flow

```
Laptop          Gateway         Robot ESP32
  │                │                │
  │─ COMMAND ─────>│                │
  │                │─ ESP-NOW ────>│
  │                │<─ ESP-NOW ACK─│
  │<─── ACK ──────│                │
  │                │                │
```

### Timeout and Retry

| Parameter | Default | Description |
|-----------|---------|-------------|
| `COMMAND_TIMEOUT_S` | 2.0 | Seconds to wait for ACK |
| `MAX_RETRIES` | 3 | Retry attempts before failure |
| `HEARTBEAT_INTERVAL_S` | 1.0 | Seconds between PINGs |
| `HEARTBEAT_TIMEOUT_S` | 3.0 | Seconds to wait for PONG |

If no ACK after all retries → command returns `"status": "TIMEOUT"`.

## Duplicate Detection

The laptop maintains a bounded set of recently seen message IDs (default: 1000). Duplicate messages are silently discarded.

## Emergency Stop

`EMERGENCY_STOP` has the highest priority:

1. **Bypasses normal command queue** — sent immediately
2. **Always forwarded** regardless of motor-disabled mode
3. **Local state updated** even if no ACK received
4. **Stops all motion** — rover, arm, gripper released

## Motor-Disabled Mode

When `HARDWARE_MOTORS_ENABLED=false`:

- Movement commands (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`) are acknowledged with `"status": "MOTORS_DISABLED"` but NOT forwarded to robot
- `STOP` and `EMERGENCY_STOP` are ALWAYS forwarded
- `PING`, `STATUS` work normally
- Arm and gripper commands are blocked

This allows communication testing before motor power is enabled.

## Heartbeat

```
Every HEARTBEAT_INTERVAL_S:
  Laptop ─── PING ──→ Gateway
  Laptop ←── PONG ──← Gateway

If no PONG within HEARTBEAT_TIMEOUT_S:
  → Connection marked as lost
  → Robot state set to safe (speed=0, stopped)
  → Reconnect attempted on next heartbeat cycle
```

## Telemetry Fields

| Field | Type | Description |
|-------|------|-------------|
| `battery_pct` | int | Robot battery 0-100% |
| `temperature_c` | float | Temperature in °C |
| `rssi` | int | ESP-NOW signal strength (dBm) |
| `state` | int | Robot state (0=INIT, 1=IDLE, 2=MANUAL, 4=EMERGENCY) |
| `motor_cmd` | int | Current motor command flag |
| `error_code` | int | Error code (0=none) |
| `motors_enabled` | bool | Whether motors are enabled |
| `firmware_version` | string | Gateway firmware version |
| `uptime_ms` | int | Gateway uptime in milliseconds |
| `arm.base` | int | Base servo angle |
| `arm.shoulder` | int | Shoulder servo angle |
| `arm.elbow` | int | Elbow servo angle |
| `arm.gripper` | int | Gripper servo angle |
