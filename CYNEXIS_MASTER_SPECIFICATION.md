# CYNEXIS — Master Specification v2.0
> **Single Source of Truth. Do not contradict this document.**
> Version: 2.0 | Date: 2026-08-04 | Engineer: Mohammed Ashik M

---

## 1. PROJECT IDENTITY

| Field | Value |
|-------|-------|
| **Name** | CYNEXIS |
| **Tagline** | Connecting Human Intelligence with Machine Precision |
| **Version** | 1.0 (build) / 2.0 (specification) |
| **Type** | AI-Powered Gesture-Controlled Robotic Platform |
| **Status** | Phase 0 Complete — Phase 1 Starting |

---

## 2. WHAT WAS REMOVED (V1 → V2)

These features existed in the old concept. They are **permanently removed**.

| Feature | Reason |
|---------|--------|
| Voice control (V1) | Replaced by INMP441 + AI assistant in status glove |
| Holographic module | Out of scope |
| MongoDB | Replaced by SQLite + ChromaDB |
| MQTT | Replaced by ESP-NOW + Wi-Fi |
| TensorFlow | Replaced by PyTorch + YOLOv8 |

> **Rule:** Do not re-add any of these without a critical engineering justification.

---

## 3. SYSTEM ARCHITECTURE

```
                    LAPTOP AI CORE
                          │
              OpenCV + YOLO + MediaPipe
              PyTorch + FastAPI + ChromaDB
                          │
                        Wi-Fi
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
  CONTROL GLOVE                       ROBOT ESP32
        │                                   │
     ESP-NOW                           BTS7960
        │                              PCA9685
  5x Flex sensors                    4x DC motors
  MPU6050 IMU                        4x DS3218 servos
  ESP32                              HC-SR04
                                     Voltage sensor
                                     E-stop
        └─────────────────┬─────────────────┘
                          │ ESP-NOW
                    STATUS GLOVE
                          │
                    CYNEXIS OS
                          │
              3.5" Capacitive touchscreen
              INMP441 microphone
              MAX98357A + speaker
              Vibration motor
              ESP32
```

---

## 4. BILL OF MATERIALS (v2.0 OFFICIAL)

### 4.1 Control Glove

| ID | Component | Qty | Specs |
|----|-----------|-----|-------|
| CG01 | ESP32 Dev Module | 1 | 38-pin WROOM-32 |
| CG02 | Flex Sensor 2.2" | 5 | 10k-110k Ω |
| CG03 | MPU6050 IMU | 1 | I2C, 3.3V |
| CG04 | 18650 Li-ion Cell | 1-2 | 2500-3500 mAh |
| CG05 | TP4056 Type-C Module | 1 | 1A, with protection |
| CG06 | Power Switch SPST | 1 | ≥5A rated |
| CG07 | Cotton Glove | 1 | Size L |

### 4.2 Status Glove

| ID | Component | Qty | Specs |
|----|-----------|-----|-------|
| SG01 | ESP32 Dev Module | 1 | 38-pin WROOM-32 |
| SG02 | 3.5" Capacitive Touchscreen | 1 | ILI9488 or similar, SPI |
| SG03 | INMP441 Microphone | 1 | I2S, 3.3V |
| SG04 | MAX98357A Amplifier | 1 | I2S, 3W |
| SG05 | Speaker | 1 | 3W, 4Ω or 8Ω |
| SG06 | Vibration Motor | 1 | 3V coin-type |
| SG07 | 2N2222 Transistor | 1 | NPN, TO-92 (for motor drive) |
| SG08 | 18650 Li-ion Cell | 1-2 | 2500-3500 mAh |
| SG09 | TP4056 Type-C Module | 1 | 1A, with protection |
| SG10 | Power Switch SPST | 1 | ≥5A rated |
| SG11 | Cotton Glove | 1 | Size L |

### 4.3 Robot Platform

| ID | Component | Qty | Specs |
|----|-----------|-----|-------|
| RB01 | ESP32 Dev Module | 1 | 38-pin WROOM-32 |
| RB02 | BTS7960 Motor Driver | 1 | 43A peak, 12V |
| RB03 | PCA9685 Servo Driver | 1 | 16-ch, I2C, 50Hz |
| RB04 | DC Gear Motor 12V | 4 | 150-300 RPM, metal gear |
| RB05 | DS3218 Servo Motor | 4 | 20kg-cm, 270° |
| RB06 | HC-SR04 Ultrasonic | 1 | 2-400cm |
| RB07 | Aluminium 4WD Chassis | 1 | Full kit |
| RB08 | 4-DOF Aluminium Arm | 1 | Compatible with DS3218 |
| RB09 | 18650 Li-ion Cell | 3 | 3S pack, 2500-3500 mAh |
| RB10 | BMS 3S | 1 | 10A, overcharge protection |
| RB11 | LM2596 Buck Converter | 2 | Adjustable, 3A |
| RB12 | XT60 Connector | 2 | Male + Female pair |
| RB13 | 10A Fuse + Holder | 1 | Inline blade type |
| RB14 | E-stop Button | 1 | NC momentary, red |
| RB15 | Power Switch | 1 | SPST ≥5A |
| RB16 | Heatsink | 2 | For BTS7960 + LM2596 |
| RB17 | TVS Diode 15V | 2 | DO-15 |
| RB18 | 1N4007 Diode | 10 | Flyback protection |
| RB19 | 1000µF 25V Capacitor | 4 | Electrolytic |
| RB20 | 470µF 16V Capacitor | 4 | Electrolytic |

### 4.4 Vision System

| ID | Component | Qty | Specs |
|----|-----------|-----|-------|
| VS01 | USB Webcam | 1 | 1080p, autofocus, ≥30fps |

### 4.5 Prototyping (shared)

| ID | Component | Qty |
|----|-----------|-----|
| PR01 | Breadboard (full size) | 2 |
| PR02 | Jumper wire sets (M-M, M-F, F-F) | 3 sets |
| PR03 | Resistor kit (assorted, incl. 10kΩ) | 1 kit |
| PR04 | Capacitor kit (assorted) | 1 kit |
| PR05 | LED pack | 1 pack |
| PR06 | 2N2222 NPN transistor | 4 |
| PR07 | Male header pins | 2 packs |
| PR08 | Female header pins | 2 packs |
| PR09 | Heat-shrink tubing | 1 pack |
| PR10 | Electrical tape | 1 roll |
| PR11 | Zip ties | 1 pack |

> **Note on MG996R vs DS3218:** Architecture upgraded from MG996R (10kg-cm) to DS3218 (20kg-cm, 270°) for the robotic arm. DS3218 provides stronger hold and wider angle range.

---

## 5. CYNEXIS OS

### 5.1 Overview

CYNEXIS OS is a full graphical interface running on the status glove's 3.5" touchscreen. It is implemented using **LVGL** (Light and Versatile Graphics Library).

### 5.2 Screens

| Screen | Function |
|--------|----------|
| Boot screen | Animated CYNEXIS startup logo |
| Diagnostics | Real-time sensor health, battery, signal |
| AI Assistant | Voice + text AI interaction |
| Gesture Monitor | Live finger and IMU data display |
| Communication | ESP-NOW / Wi-Fi link status |
| Settings | Brightness, volume, thresholds |
| Camera | Live feed from robot camera |
| Arm Control | Manual servo position control |
| Battery Monitor | Voltage, current, runtime estimate |
| Sensor Monitor | All sensor values in real time |
| Audio Interface | Waveform, voice input, speaker |
| Notifications | Alerts, warnings, system messages |

### 5.3 UI Features

- Animated icons
- Dark mode
- Sliding menus
- Touch control (capacitive)
- Real-time telemetry overlay
- Waveform display
- Voice feedback via speaker

### 5.4 Implementation

- Library: **LVGL v9.x**
- Design tool: **Figma** (mockups)
- Target: ESP32 with ILI9488 3.5" display
- Communication to robot: ESP-NOW (status updates)
- Communication to laptop: Wi-Fi (AI assistant)

---

## 6. SOFTWARE STACK

### 6.1 Embedded

| Tool | Purpose |
|------|---------|
| Arduino IDE 2.3.10 | Flashing, library management |
| PlatformIO v3.3.4 | Advanced build system |
| ESP-IDF | Low-level ESP32 APIs |
| FreeRTOS | Task scheduling on ESP32 |
| LVGL v9.x | CYNEXIS OS UI framework |

### 6.2 AI / Vision

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.12.10 | Runtime (venv at d:\Cynexis\.venv) |
| PyTorch | 2.13.0 | AI/ML framework |
| OpenCV | 5.0.0.93 | Computer vision |
| MediaPipe | 1.0.0 | Hand/pose tracking |
| Ultralytics (YOLOv8) | 8.4.115 | Object detection |
| DeepSORT | latest | Object tracking |

### 6.3 Backend

| Tool | Version | Purpose |
|------|---------|---------|
| FastAPI | 0.141.1 | REST API server |
| Uvicorn | 0.52.1 | ASGI server |
| WebSockets | 17.0.1 | Real-time data |

### 6.4 Frontend

| Tool | Purpose |
|------|---------|
| React | Web dashboard |
| Figma | UI design and mockups |

### 6.5 Database / Memory

| System | Purpose |
|--------|---------|
| SQLite | Short-term memory, session context |
| ChromaDB | Long-term vector memory, retrieval |

---

## 7. COMMUNICATION ARCHITECTURE

| Link | Protocol | Speed | Notes |
|------|----------|-------|-------|
| Control glove → Robot | ESP-NOW | ~50 Hz | <1ms latency, no router needed |
| Robot → Status glove | ESP-NOW | ~10 Hz | Status + ACK |
| Robot → Laptop | Wi-Fi | As needed | Telemetry + camera |
| Laptop → Robot | Wi-Fi | As needed | AI commands |

---

## 8. DEVELOPMENT PHASES

| Phase | Name | Key Deliverables |
|-------|------|-----------------|
| 0 | Environment Setup | ✅ Complete |
| 1 | Control Glove | Flex + IMU + ESP-NOW TX |
| 2 | Status Glove | OLED/Touch + CYNEXIS OS boot |
| 3 | Robot Base | Motors + BTS7960 + ESP-NOW RX |
| 4 | Robotic Arm | DS3218 servos + PCA9685 |
| 5 | Vision System | Camera + OpenCV + YOLOv8 |
| 6 | Audio System | INMP441 + MAX98357A + voice |
| 7 | CYNEXIS OS | Full LVGL UI on touchscreen |
| 8 | Full Integration | All systems unified + testing |

---

## 9. POWER ARCHITECTURE

### Robot (3S Li-ion, 11.1V)

```
3S Battery Pack (11.1V)
        │
      [BMS 10A]
        │
     [10A Fuse]
        │
   [Main Switch]
        │
        ├── [BTS7960] ──── 4× DC Motors (12V direct)
        │
        ├── [LM2596 #1] ── 7.5V ── [PCA9685 V+] ── 4× DS3218 servos
        │
        └── [LM2596 #2] ── 5V ─── [ESP32 VIN]
                                ├── [HC-SR04]
                                └── [PCA9685 VCC]
```

### Gloves (Single cell, 3.7V)

```
18650 Cell → [TP4056] → ESP32 + sensors
```

---

## 10. FOUR DOCUMENTS RULE

When any change is made to the project, update **only these four files**:

| File | Purpose |
|------|---------|
| `CYNEXIS_MASTER_SPECIFICATION.md` | Single source of truth (this file) |
| `CYNEXIS_Development_Notebook.md` | Daily log, errors, decisions |
| `Hardware_Shopping_Guide.md` | Phased BOM with prices |
| `CHANGELOG.md` | Version history of all changes |

---

## 11. AI TOOL WORKFLOW

| Tool | Use For |
|------|---------|
| **Antigravity IDE** | All code editing, git, terminal |
| **ChatGPT** | Brainstorming, architecture reviews, planning |
| **Claude** | Long code generation, firmware, large file analysis |
| **GitHub** | Version control at github.com/MohammedAshikM3003/Cynexis |

---

## 12. ARCHITECTURE RULES

1. **Never change the architecture without a critical reason and explanation**
2. **Always estimate cost, power, risks, and reliability for any new component**
3. **Always think from the perspective of all engineering disciplines**
4. **Removed features stay removed unless there is a critical reason**
5. **Build phase by phase — do not skip phases**
6. **Test each phase before proceeding to the next**

---

*CYNEXIS Master Specification v2.0 — Architecture frozen. Build starts now.*
