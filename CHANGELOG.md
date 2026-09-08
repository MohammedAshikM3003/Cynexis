# CHANGELOG — CYNEXIS

All notable changes to this project will be documented here.
Format: `[YYYY-MM-DD] | Type | Description`
Types: ADDED | CHANGED | REMOVED | FIXED | ARCHITECTURE | HARDWARE | SOFTWARE

---

## [2026-08-17] — Phase 3/4: Robot Integration & 3-Node Topology

### ADDED
- HARDWARE: Integrated new physical Robot ESP32 board with MAC address `04:B2:47:82:38:FC`.
- SOFTWARE: Upgraded `status_glove.ino` to parse and log the official `RobotToStatusPacket` telemetry sent by the Robot ESP32, displaying operating state, battery levels, RSSI, error codes, and servo/subsystem health.

### CHANGED
- CONFIG: Configured `MAC_ROBOT` to `04:B2:47:82:38:FC` in the shared and local copies of `cynexis_mac.h`.
- CONFIG: Redirected `receiverMAC` in `control_glove.ino` to route packets to the new physical Robot ESP32 MAC address.

---

## [2026-08-16] — Phase 3/4: Robot Integration

### ADDED
- SOFTWARE: Dynamic Control Glove MAC registration implemented on Robot ESP32 (`robot_esp32.ino`). The robot dynamically registers peer credentials upon first received packet and transmits AckPackets back without needing hardcoded values.
- SOFTWARE: Local copies of `cynexis_protocol.h` and `cynexis_mac.h` added to the `RobotESP32/` directory for flat compilation compatibility.

### FIXED
- SOFTWARE: Upgraded `on_data_recv` in `robot_esp32.ino` to be version-agnostic across ESP32 Arduino Core 2.x and 3.x using preprocessor conditional blocks.
- CONFIG: Shared Status Glove MAC address hardcoded as `28:05:A5:E2:85:B8` in `cynexis_mac.h`.

---

## [2026-08-14] — Phase 2/3/4: Glove Integration

### FIXED
- HARDWARE/SOFTWARE: Pinky flex sensor moved from GPIO 25 (ADC2) to GPIO 36 (SVP / ADC1) on the Control Glove to resolve the ESP32 Wi-Fi hardware lock conflict. Pinky sensor now reads successfully.
- SOFTWARE: Receiver (`status_glove.ino`) print layout restructured to print clean debug lines matching expected output formatting.

### ADDED
- SOFTWARE: Bi-directional analog-to-percentage mapping (`getBendPercentage`) and state classifier (`getFingerState`) implemented on Receiver.
- SOFTWARE: Configurable, non-locking Gesture Recognition engine (`classifyGesture`) implemented in receiver firmware. Supports OPEN HAND, FIST, POINT, THUMBS UP, PEACE SIGN, and PARTIAL states.
- SOFTWARE: Custom Python `monitor.py` script added to project root to allow stable serial port monitoring without Arduino IDE interface crashes.

### CHANGED
- HARDWARE: Control Glove Pinky pin changed to GPIO 36 (SVP).

---

## [2026-08-04] — Specification v2.1

### FIXED
- Version header corrected to v2.1 (was mismatched with changelog)
- Duplicate section numbering fixed: 10/11/10/11/12 → 10/11/12/13/14/15/16

### ADDED
- RB21: INA219 Current/Voltage Sensor (I2C — current, power, battery runtime)
- Section 12: System State Machine — 7 exclusive states (NORMAL, IDLE, MANUAL, AI, SAFE, EMERGENCY, SHUTDOWN)
- Section 13: Communication Packet Definition — Control packet 24 bytes @50Hz, Status packet 20 bytes @10Hz
- EMERGENCY rule: hardware reset only, cannot be cleared by software

### FROZEN
- Specification frozen for build. No more major features until Phase 4.

---

## [2026-08-04] — Specification v2.0


### ARCHITECTURE
- Locked CYNEXIS v2.0 architecture — no further changes without critical justification
- Created `CYNEXIS_MASTER_SPECIFICATION.md` as single source of truth
- Defined Four Documents Rule (Spec + Notebook + Hardware Guide + Changelog)
- Defined AI tool workflow: Antigravity IDE / ChatGPT / Claude / GitHub

### ADDED
- CYNEXIS OS concept — full LVGL graphical interface on status glove
- 3.5" capacitive touchscreen (ILI9488) to status glove BOM
- INMP441 microphone to status glove BOM
- MAX98357A amplifier + speaker to status glove BOM
- DS3218 servos (upgraded from MG996R) to robot arm BOM
- ChromaDB long-term vector memory to software stack
- SQLite short-term memory to software stack
- DeepSORT object tracking to vision stack
- 12 CYNEXIS OS screens defined (boot, diagnostics, AI, gesture, etc.)

### CHANGED
- Status glove: SSD1306 OLED (0.96") → 3.5" capacitive touchscreen
- Servo spec: MG996R (10kg-cm) → DS3218 (20kg-cm, 270°)
- Master system prompt updated to V2.0 (Architect Edition)
- Hardware_Shopping_Guide.md updated with user corrections

### REMOVED
- Voice control (old V1 concept)
- Holographic module
- MongoDB
- MQTT
- TensorFlow (replaced by PyTorch + YOLOv8)

---

## [2026-08-03] — Day 0 Complete

### ENVIRONMENT
- Antigravity IDE: Active (replaces VS Code)
- Python 3.12.10 virtual environment created at d:\Cynexis\.venv
- All Python packages installed: numpy 2.5.1, torch 2.13.0, opencv 5.0.0.93, mediapipe 1.0.0, ultralytics 8.4.115, fastapi 0.141.1, uvicorn 0.52.1, websockets 17.0.1, matplotlib 3.11.1, pandas 3.0.5, pyserial 3.5
- pip upgraded to 26.2

### SOFTWARE INSTALLED
- Arduino IDE 2.3.10
- KiCad 10.0.5
- PlatformIO IDE v3.3.4 (Antigravity IDE extension)
- Git 2.53.0
- Postman

### ARDUINO CONFIGURED
- ESP32 board support added (Espressif Systems package)
- 5 Adafruit libraries installed: MPU6050, Unified Sensor, SSD1306, GFX, PWM Servo Driver

### FIRMWARE CREATED
- cynexis_protocol.h v1.0
- cynexis_mac.h v1.0 (MACs placeholder — update after hardware arrives)
- control_glove.ino v1.0
- robot_esp32.ino v1.0
- status_glove.ino v1.0

### GIT
- Repository initialized at d:\Cynexis
- Remote: github.com/MohammedAshikM3003/Cynexis
- Initial commit: 39 files
- GitHub push verified (main branch)

### DOCUMENTATION CREATED
- CYNEXIS_Development_Notebook.md
- CYNEXIS_MASTER_SYSTEM_PROMPT.md v1.1
- Day0_Setup_Checklist.md (all items complete)
- Hardware_Shopping_Guide.md (phased shopping list)

---

*Add new entries at the top, under a new date heading.*
