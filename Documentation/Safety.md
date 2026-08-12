# CYNEXIS — Safety Documentation

## Safety Architecture

CYNEXIS implements defense-in-depth with six safety layers:

```
Layer 1: API Safety Check
    ↓
Layer 2: Protocol Command Whitelist
    ↓
Layer 3: Motor-Disabled Mode
    ↓
Layer 4: Gateway Firmware Validation
    ↓
Layer 5: Robot Firmware Safety (watchdog, e-stop, obstacle)
    ↓
Layer 6: Physical Emergency Stop Button
```

## Critical Safety Rule

> **Voice → LLM → direct motor control is NEVER allowed.**
>
> All hardware actions MUST pass through predefined commands in the ActionName whitelist.
> The LLM can only select from predefined actions — it cannot invent new GPIO commands.

## Emergency Stop

Emergency stop has the **highest priority** in the system.

### Trigger Sources
1. **Software:** `POST /api/command {"action": "EMERGENCY_STOP"}`
2. **Serial Bridge:** `bridge.emergency_stop()` — bypasses normal queue
3. **ESP-NOW:** `GESTURE_EMERGENCY_STOP` (0xFF) from control glove
4. **Physical button:** NC momentary switch on Robot ESP32 (GPIO 4)

### What Happens
1. All motors immediately stop (PWM → 0)
2. Gripper opens (release anything held)
3. Arm holds current position (servos stay energized)
4. Robot enters `STATE_EMERGENCY`
5. Movement commands are blocked until mode is reset

### Communication Loss Emergency
If the robot ESP32 loses ESP-NOW contact for >500ms:
- All motors stop
- Robot enters emergency state
- Status LED blinks rapidly

## Motor-Disabled Mode

**Default state: DISABLED**

```env
HARDWARE_MOTORS_ENABLED=false
```

When disabled:
- Movement commands are acknowledged (`"status": "MOTORS_DISABLED"`)
- Commands are NOT forwarded to motor hardware
- `STOP` and `EMERGENCY_STOP` are ALWAYS forwarded
- Serial communication (PING/PONG) works normally

**Enable ONLY after:**
1. Serial communication verified (PING → PONG works)
2. ESP-NOW link verified (gateway → robot connected)
3. Motor power supply verified (correct voltage, no shorts)
4. Physical e-stop button tested

## Timeout Protection

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `COMMAND_TIMEOUT_S` | 2.0s | Max wait for ACK from ESP32 |
| `HEARTBEAT_INTERVAL_S` | 1.0s | PING frequency |
| `HEARTBEAT_TIMEOUT_S` | 3.0s | Max wait for PONG |
| `MOVEMENT_TIMEOUT_MS` | 5000ms | Auto-stop if no new movement command |
| `COMMS_WATCHDOG_MS` | 500ms | Robot ESP32 ESP-NOW timeout |
| `WATCHDOG_TIMEOUT_S` | 5s | Robot ESP32 software watchdog |

### Movement Watchdog
If the rover is moving and no new movement command arrives within 5 seconds, the system automatically sends `STOP`. This prevents runaway movement if the control source disconnects.

## Speed Limits

| Parameter | Value |
|-----------|-------|
| Max rover speed | 255 (PWM) |
| Default rover speed | 150 (PWM) |
| Min motor speed (stiction) | 80 (PWM) |
| Max servo angle | 270° (DS3218) |
| Min servo angle | 0° |

All speed values are clamped at the action handler level AND at the controller level (defense-in-depth).

## Battery Protection

| Threshold | Action |
|-----------|--------|
| ≤30% | Warning logged |
| ≤15% | Movement blocked, system enters SAFE mode |
| ≤10% | System enters SHUTDOWN |

## Obstacle Detection

The HC-SR04 ultrasonic sensor on the Robot ESP32 automatically stops forward movement when an obstacle is detected within 20cm.

## API Safety Checks

The `SafetyGuard` validates every command before execution:

1. **Action whitelist:** Only `ActionName` enum values are accepted
2. **Mode check:** Movement blocked in `EMERGENCY`, `SHUTDOWN` modes
3. **Battery check:** Movement blocked below critical threshold
4. **Concurrent movement:** Arm commands blocked while rover is moving
5. **Speed limits:** Out-of-range values return 403
6. **Servo limits:** Out-of-range angles return 403

## State Update Rule

> **Robot state is only updated after receiving ACK from the ESP32.**

This means:
- If a command times out, the state reflects the LAST confirmed state
- The API can accurately report whether a command was actually executed
- No false state updates from unconfirmed commands
