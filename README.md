# CYNEXIS — Project README

> AI-Powered Gesture-Controlled Telepresence and Robotic Manipulation System
> _Connecting Human Intelligence with Machine Precision_

---

## Project Overview

CYNEXIS is a final-year engineering project that combines:

- **Gesture control** via a wearable smart glove
- **Real-time wireless communication** using ESP-NOW
- **AI-based object detection** with YOLOv8
- **Live video streaming** via OpenCV + FastAPI
- **4-DOF robotic arm** controlled by servo motors
- **Mobile robot platform** with differential drive

---

## Repository Structure

```
CYNEXIS/
├── Firmware/               # All ESP32 firmware (.ino files)
│   ├── Protocol/           # Shared packet structures & MAC registry
│   ├── ControlGlove/       # Control glove ESP32 firmware
│   ├── RobotESP32/         # Main robot ESP32 firmware
│   ├── StatusGlove/        # Status glove ESP32 firmware
│   ├── Libraries/          # External libraries (git submodules)
│   └── Shared/             # Shared constants & utilities
│
├── Backend/                # Python FastAPI server
│   ├── api/                # FastAPI routes and WebSocket handlers
│   └── serial_bridge/      # ESP32 serial communication bridge
│
├── Frontend/               # React dashboard
│   ├── src/                # React components and pages
│   └── public/             # Static assets
│
├── AI/                     # AI/Computer vision pipeline
│   ├── models/             # YOLOv8 model weights
│   ├── scripts/            # OpenCV, MediaPipe, YOLO scripts
│   └── datasets/           # Training datasets
│
├── Simulation/             # Wokwi simulation files
│   ├── Wokwi/ControlGlove/ # Control glove simulation
│   ├── Wokwi/RobotESP32/   # Robot simulation
│   └── Wokwi/StatusGlove/  # Status glove simulation
│
├── Schematics/             # KiCad circuit schematics
├── CAD Designs/            # Fusion 360 mechanical models
├── Documentation/          # Project documentation
│   ├── Pinouts/            # Pin mapping diagrams
│   └── Schematics/         # Circuit documentation
│
├── Tests/                  # Test scripts and results
│   ├── Unit/               # Unit tests
│   ├── Integration/        # Integration tests
│   └── Logs/               # Test result logs
│
├── Images/                 # Project photos
├── Videos/                 # Demo videos
├── Reports/                # IEEE-format reports
└── Research Papers/        # Reference papers
```

---

## Technology Stack

| Layer           | Technology                        |
| --------------- | --------------------------------- |
| Embedded        | ESP32, C++, Arduino IDE           |
| Communication   | ESP-NOW (2.4GHz)                  |
| AI/CV           | Python, OpenCV, MediaPipe, YOLOv8 |
| Backend         | FastAPI, WebSocket, pyserial      |
| Frontend        | React, JavaScript                 |
| Mechanical      | Fusion 360                        |
| Electrical      | KiCad                             |
| Simulation      | Wokwi                             |
| Version Control | Git, GitHub                       |

---

## Development Phases

| Phase | Goal                        | Status              |
| ----- | --------------------------- | ------------------- |
| 0     | Environment setup           | ✅ Complete         |
| 1     | ESP32 LED blink + serial    | ⏳ Pending hardware |
| 2     | Robot chassis assembly      | ⏳ Pending hardware |
| 3     | Motor driver test           | ⏳ Pending hardware |
| 4     | Control glove build         | ⏳ Pending hardware |
| 5     | Status glove build          | ⏳ Pending hardware |
| 6     | Robotic arm integration     | ⏳ Pending hardware |
| 7     | Computer vision integration | ⏳ Pending hardware |
| 8     | Final integration & testing | ⏳ Pending hardware |

---

## Quick Start

### 1. Flash MAC Address Finder

```cpp
#include <WiFi.h>
void setup() { Serial.begin(115200); WiFi.mode(WIFI_STA); Serial.println(WiFi.macAddress()); }
void loop() {}
```

Record the MAC of each ESP32 and update `Firmware/Protocol/cynexis_mac.h`.

### 2. Flash Firmware

- Open `Firmware/ControlGlove/control_glove.ino` in Arduino IDE
- Select board: **ESP32 Dev Module**
- Select correct COM port
- Upload

### 3. Start Backend

```bash
cd Backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start Frontend

```bash
cd Frontend
npm install
npm run dev
```

---

## Hardware Components

| Component            | Quantity | Purpose                            |
| -------------------- | -------- | ---------------------------------- |
| ESP32 Dev Module     | 3        | Control glove, Robot, Status glove |
| BTS7960 Motor Driver | 1        | Differential drive                 |
| PCA9685 Servo Driver | 1        | 4-DOF arm control                  |
| MG996R Servo Motor   | 4        | Robotic arm joints                 |
| DC Gear Motor (12V)  | 4        | Robot wheels                       |
| Flex Sensor          | 5        | Finger bend detection              |
| MPU6050 IMU          | 1        | Hand orientation                   |
| HC-SR04              | 1        | Obstacle detection                 |
| SSD1306 OLED         | 1        | Status display                     |
| 18650 Li-ion Cell    | 4        | Power (robot 3S + 2× glove)        |
| TP4056 Module        | 2        | Glove battery charging             |
| LM2596 Buck          | 2        | Voltage regulation                 |
| BMS 3S               | 1        | Battery protection                 |

---

## Team

| Name             | Role        |
| ---------------- | ----------- |
| MOhammed Ashik M | 73152313074 |
| Ravinder singh   | 73152313095 |
| Mogeswaran P     | 73152313072 |

**Guide:** —
**Department:** — Computer Science and Engineering (CSE)
**College:** — KSR College Of Engineering

---

_CYNEXIS — Final-Year Engineering Project | IEEE Publication Track_
