# CYNEXIS — Hardware Integration Guide

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LAPTOP (Python)                       │
│                                                          │
│  FastAPI Server                                          │
│      │                                                   │
│  Safety Layer                                            │
│      │                                                   │
│  Action Registry                                         │
│      │                                                   │
│  ESP32 Controllers (Rover / Arm / Gripper)               │
│      │                                                   │
│  SerialBridge (ACK, retry, heartbeat, watchdog)          │
│      │                                                   │
│  Transport (Serial / Mock)                               │
│      │                                                   │
│  USB Serial (/dev/ttyUSB0 or COMx)                       │
└──────┼───────────────────────────────────────────────────┘
       │
       │ JSON-over-serial (115200 baud, newline-delimited)
       │
┌──────┼───────────────────────────────────────────────────┐
│  GATEWAY ESP32                                           │
│      │                                                   │
│  JSON Parser (ArduinoJson)                               │
│      │                                                   │
│  Command Translator (JSON → binary packet)               │
│      │                                                   │
│  ESP-NOW Sender                                          │
└──────┼───────────────────────────────────────────────────┘
       │
       │ ESP-NOW (binary packets, 250kbps, channel 1)
       │
┌──────┼───────────────────────────────────────────────────┐
│  ROBOT ESP32                                             │
│      │                                                   │
│  ESP-NOW Receiver                                        │
│      │                                                   │
│  Command Executor                                        │
│      │                                                   │
│  ┌───┴────────────────────────────────────────┐          │
│  │ BTS7960 Motor Driver (left + right wheels) │          │
│  │ PCA9685 Servo Driver (arm + gripper)       │          │
│  │ HC-SR04 Ultrasonic Sensor                  │          │
│  │ Battery Voltage Sensor                     │          │
│  │ Emergency Stop Button                      │          │
│  └────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

## ESP32 Board Roles

| Board | Role | Firmware | Connection |
|-------|------|----------|------------|
| **Gateway ESP32** | Serial→ESP-NOW bridge | `Firmware/ESP32/gateway/gateway.ino` | USB to laptop |
| **Robot ESP32** | Motor/servo/sensor control | `Firmware/RobotESP32/robot_esp32.ino` | ESP-NOW from gateway |
| **Control Glove ESP32** | Gesture input | `Firmware/ControlGlove/` | ESP-NOW to robot |
| **Status Glove ESP32** | Telemetry display | `Firmware/StatusGlove/` | ESP-NOW from robot |

> **Note:** Board assignments are configurable. Update MAC addresses in `Protocol/cynexis_mac.h` and `ESP32/gateway/config.h` when changing boards.

## Communication Flow

### Command Execution
```
1. User sends POST /api/command {"action": "FORWARD"}
2. Safety layer validates
3. Action handler calls rover_controller.forward(150)
4. ESP32RoverController calls bridge.send_command("FORWARD", {"speed": 150})
5. Bridge serializes to JSON, sends via SerialTransport
6. Gateway ESP32 parses JSON, translates to GloveToRobotPacket
7. Gateway sends binary packet via ESP-NOW
8. Robot ESP32 receives, executes motor command
9. Robot sends ACK back via ESP-NOW
10. Gateway forwards ACK as JSON to laptop
11. Bridge receives ACK, updates robot_state
12. API returns success
```

### State Update Rule
**Robot state is only updated after receiving ACK from ESP32.**

If no ACK → state remains unchanged → API can report failure to caller.

## Motor-Disabled Mode

For first-time hardware testing, motors are disabled by default:

```env
HARDWARE_MOTORS_ENABLED=false
```

In this mode:
- All commands are acknowledged
- Commands are NOT forwarded to motor hardware
- `STOP` and `EMERGENCY_STOP` are always forwarded
- Communication can be fully tested without motor power

Enable motors only after verifying serial communication works:
```env
HARDWARE_MOTORS_ENABLED=true
```

## Safety Layers

```
Layer 1: API Safety Check (action whitelist, battery, mode)
    │
Layer 2: Protocol Whitelist (only known commands)
    │
Layer 3: Motor-Disabled Mode (no motor output until enabled)
    │
Layer 4: Gateway Validation (rejects unknown JSON commands)
    │
Layer 5: Robot Firmware (watchdog, e-stop, obstacle detection)
    │
Layer 6: Physical E-Stop Button (NC to GND on Robot ESP32)
```

## Fail-Safe Behavior

| Scenario | Action |
|----------|--------|
| Serial disconnected | Bridge marks disconnected, rover state → STOPPED |
| No PONG from gateway | Bridge marks disconnected, auto-reconnect on next cycle |
| No movement command for 5s | Movement watchdog sends auto-STOP |
| Gateway loses robot ESP-NOW | Gateway reports error via serial |
| Robot loses gateway ESP-NOW | Robot firmware watchdog stops motors (500ms timeout) |
| Battery critical (<15%) | Robot enters EMERGENCY, all motors stop |
| Obstacle detected (<20cm) | Robot stops forward movement |
