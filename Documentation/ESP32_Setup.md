# CYNEXIS — ESP32 Setup Guide

## Prerequisites

- 2x ESP32 DevKit boards (any 30-pin or 38-pin variant)
  - **Board 1:** Gateway (connects via USB to laptop)
  - **Board 2:** Robot (controls motors/servos)
- Arduino IDE 2.x or PlatformIO
- USB cable (data-capable, not charge-only)

## Step 1: Find MAC Addresses

Upload this sketch to **each** ESP32:

```cpp
#include <WiFi.h>
void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_STA);
    Serial.println(WiFi.macAddress());
}
void loop() {}
```

Record the MAC addresses:
- Gateway ESP32: `XX:XX:XX:XX:XX:XX`
- Robot ESP32: `YY:YY:YY:YY:YY:YY`

## Step 2: Update MAC Addresses

### Gateway firmware
Edit `Firmware/ESP32/gateway/config.h`:
```cpp
static const uint8_t MAC_ROBOT[6] = {
    0xYY, 0xYY, 0xYY, 0xYY, 0xYY, 0xYY  // Robot ESP32 MAC
};
```

### Robot firmware
Edit `Firmware/Protocol/cynexis_mac.h`:
```cpp
static const uint8_t MAC_ROBOT[6] = {
    0xYY, 0xYY, 0xYY, 0xYY, 0xYY, 0xYY  // Robot ESP32 MAC
};
static const uint8_t MAC_GLOVE_CONTROL[6] = {
    0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX  // Gateway ESP32 MAC (acts as glove)
};
```

## Step 3: Install Arduino Libraries

| Library | Install via |
|---------|-------------|
| ArduinoJson (v7+) | Arduino Library Manager |
| Adafruit PWM Servo Driver | Arduino Library Manager |
| esp_now.h | Built-in (ESP32 core) |
| WiFi.h | Built-in (ESP32 core) |

## Step 4: Flash Gateway Firmware

1. Open `Firmware/ESP32/gateway/gateway.ino` in Arduino IDE
2. Select your ESP32 board
3. Select the correct COM port
4. Upload

The gateway will print on serial:
```
{"type":"STATUS","id":"boot","data":{"message":"CYNEXIS Gateway booting..."}}
{"type":"STATUS","id":"boot","data":{"message":"CYNEXIS Gateway ready"}}
```

## Step 5: Flash Robot Firmware

1. Open `Firmware/RobotESP32/robot_esp32.ino` in Arduino IDE
2. Select your ESP32 board
3. Upload
4. Do NOT connect motor power yet

## Step 6: Configure Python Side

Edit `D:\Cynexis\.env`:
```env
MOCK_MODE=false
ESP32_SERIAL_PORT=COM5          # Your gateway COM port
ESP32_BAUD_RATE=115200
HARDWARE_MOTORS_ENABLED=false   # Keep disabled until verified
```

Find your COM port:
- **Windows:** Device Manager → Ports (COM & LPT)
- **Linux:** `ls /dev/ttyUSB*`
- **macOS:** `ls /dev/cu.usbserial*`

## Step 7: First Communication Test

```bash
python main.py
```

Expected log output:
```
SerialBridge started
Heartbeat loop started
```

The system will send PING every second. Expected flow:
```
Laptop → PING → Gateway → PONG → Laptop
```

### Manual serial test (without Python server)

Open a serial monitor (115200 baud) and send:
```json
{"v":1,"type":"PING","id":"test-001","ts":0,"cs":"00000000"}
```

Expected response:
```json
{"v":1,"type":"PONG","id":"test-001","ts":12345,"cs":"00000000"}
```

## Step 8: Verify Communication

Run the CYNEXIS server and check:
```bash
curl http://localhost:8000/api/status
```

The `esp32` field should show:
```json
{
    "connected": true,
    "latency_ms": 5.2,
    "packets_sent": 10,
    "packets_acked": 10,
    "motors_enabled": false
}
```

## Step 9: Enable Motors (After Verification)

Only after confirming PING/PONG works:

1. Connect motor power supply (12V battery)
2. Edit `.env`:
   ```env
   HARDWARE_MOTORS_ENABLED=true
   ```
3. Restart the server
4. Test with `STOP` first, then gentle `FORWARD` at low speed

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `SerialTransport connection failed` | Check COM port, cable, drivers |
| `Heartbeat timeout` | Gateway not responding — check USB, reflash firmware |
| `PONG received but no motor movement` | `HARDWARE_MOTORS_ENABLED=false` — enable in `.env` |
| `ESP-NOW not connected` | Check MAC addresses match in both firmwares |
| `Robot stops randomly` | Watchdog timeout — check ESP-NOW signal, reduce distance |
| `Permission denied on serial port` | Run as admin (Windows) or add user to `dialout` group (Linux) |

## COM Port Configuration

The ESP32 serial port is configurable via:
1. `.env` file: `ESP32_SERIAL_PORT=COM5`
2. Environment variable: `set ESP32_SERIAL_PORT=COM5`

Do NOT hard-code COM ports in Python code.
