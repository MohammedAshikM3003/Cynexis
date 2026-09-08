# CYNEXIS — Development Notebook
> Started: 2026-08-03
> Engineer: Mohammed Ashik M
> Project: AI-Powered Gesture-Controlled Robotic System

---

## HOW TO USE THIS NOTEBOOK

- Log every change, test, error, and fix here.
- Date every entry.
- Never delete old entries — mark them RESOLVED or OBSOLETE.
- This notebook is the primary reference for the final report.

---

## SECTION 1 — ARCHITECTURE

### 1.1 System Block Diagram

```
[Control Glove] --(ESP-NOW)--> [Robot ESP32] --(USB/Wi-Fi)--> [Laptop]
                                     |                              |
                               [BTS7960]                     [FastAPI]
                               [PCA9685]                     [OpenCV]
                               [HC-SR04]                     [YOLOv8]
                               [Voltage]                     [React]
                                     |
                              (ESP-NOW)
                                     |
                              [Status Glove]
```

### 1.2 Communication Flow

```
Glove Packet (50Hz, 24 bytes)  →  Robot ESP32
ACK Packet   (50Hz,  8 bytes)  ←  Robot ESP32
Status Packet(10Hz, 20 bytes)  →  Status Glove
```

### 1.3 Power Architecture

```
3S Li-ion (11.1V nominal)
├── BTS7960 Motor Driver (direct 12V)
├── LM2596 Buck #1: 12V → 7.5V → PCA9685 → Servos
└── LM2596 Buck #2: 12V → 5V  → ESP32 + HC-SR04 + Fan
```

---

## SECTION 2 — COMPONENTS

### 2.1 Bill of Materials

| ID | Component | Qty | Specs | Status |
|----|-----------|-----|-------|--------|
| C01 | ESP32 Dev Module | 3 | 38-pin WROOM-32 | ⏳ Ordered |
| C02 | BTS7960 Motor Driver | 1 | 43A peak, 12V | ⏳ Ordered |
| C03 | PCA9685 Servo Driver | 1 | 16-ch, I2C, 50Hz | ⏳ Ordered |
| C04 | MG996R Servo Motor | 4 | 10kg-cm, 4.8-7.2V | ⏳ Ordered |
| C05 | DC Gear Motor 12V | 4 | 150-300 RPM, metal gear | ⏳ Ordered |
| C06 | Flex Sensor 2.2" | 5 | Resistance: 10k-110k Ω | ⏳ Ordered |
| C07 | MPU6050 IMU | 1 | I2C, 3.3V | ⏳ Ordered |
| C08 | HC-SR04 | 1 | 2cm-400cm, 5V | ⏳ Ordered |
| C09 | SSD1306 OLED 0.96" | 1 | 128×64, I2C, 3.3V | ⏳ Ordered |
| C10 | 18650 Li-ion Cell | 5 | 2500-3500 mAh each | ⏳ Ordered |
| C11 | TP4056 Type-C Module | 2 | 1A charge, w/ protection | ⏳ Ordered |
| C12 | LM2596 Buck Converter | 2 | Adjustable, 3A | ⏳ Ordered |
| C13 | BMS 3S | 1 | 10A, overcharge protection | ⏳ Ordered |
| C14 | XT60 Connector | 2 | Male + Female pair | ⏳ Ordered |
| C15 | Cotton Glove | 2 | Size L | ⏳ Ordered |
| C16 | Aluminium Chassis | 1 | 4WD robot kit | ⏳ Ordered |
| C17 | Aluminium Arm Kit | 1 | 4-DOF compatible | ⏳ Ordered |
| C18 | Vibration Motor | 1 | 3V coin-type | ⏳ Ordered |
| C19 | Passive Buzzer | 1 | 3.3V (OPTIONAL) | ⏳ Optional |
| C20 | USB Webcam | 1 | ≥720p, ≥30fps | ⏳ Needed |
| C21 | Fuse (10A) + holder | 1 | Inline, blade type | ⏳ Ordered |
| C22 | TVS Diode | 2 | 15V, DO-15 | ⏳ Ordered |
| C23 | 1N4007 Diode | 10 | Flyback protection | ⏳ Ordered |
| C24 | 1000µF Capacitor | 4 | 25V electrolytic | ⏳ Ordered |
| C25 | 470µF Capacitor | 4 | 16V electrolytic | ⏳ Ordered |
| C26 | 10kΩ Resistor | 10 | 0.25W | ⏳ Ordered |
| C27 | 2N2222 Transistor | 4 | NPN, TO-92 | ⏳ Ordered |
| C28 | E-stop Button | 1 | NC momentary, red | ⏳ Ordered |
| C29 | Power Switch | 3 | SPST, rated ≥5A | ⏳ Ordered |
| C30 | Heatsink | 2 | For BTS7960 + LM2596 | ⏳ Ordered |

---

## SECTION 3 — PIN MAPPINGS

### 3.1 Control Glove ESP32

| GPIO | Function | Component | Notes |
|------|----------|-----------|-------|
| 34 | ADC Input | Flex sensor (Thumb) | Input-only pin |
| 35 | ADC Input | Flex sensor (Index) | Input-only pin |
| 32 | ADC Input | Flex sensor (Middle) | |
| 33 | ADC Input | Flex sensor (Ring) | |
| 36 | ADC Input | Flex sensor (Pinky) | Labeled as SVP (moved from GPIO 25 due to Wi-Fi conflict) |
| 21 | SDA (I2C) | MPU6050 | |
| 22 | SCL (I2C) | MPU6050 | |
| 39 | ADC Input | Battery voltage sense | Labeled as SVN (moved from GPIO 36 to make room for Pinky) |
| 2  | Digital Out | Status LED (onboard) | Built-in |
| 3V3 | Power | MPU6050 VCC | |
| GND | Ground | All GND | Common ground |

### 3.2 Robot ESP32

| GPIO | Function | Component | Notes |
|------|----------|-----------|-------|
| 26 | PWM Out | BTS7960 L_RPWM | Left fwd |
| 27 | PWM Out | BTS7960 L_LPWM | Left rev |
| 14 | Digital Out | BTS7960 L_EN | Left enable |
| 12 | PWM Out | BTS7960 R_RPWM | Right fwd |
| 13 | PWM Out | BTS7960 R_LPWM | Right rev |
| 15 | Digital Out | BTS7960 R_EN | Right enable |
| 21 | SDA (I2C) | PCA9685 | |
| 22 | SCL (I2C) | PCA9685 | |
| 5  | Digital Out | HC-SR04 TRIG | |
| 18 | Digital In | HC-SR04 ECHO | Use voltage divider! 5V→3.3V |
| 36 | ADC Input | Battery voltage | Input-only (VP) |
| 4  | Digital In | E-stop button | INPUT_PULLUP, NC to GND |
| 2  | Digital Out | Status LED | Built-in |

### 3.3 Status Glove ESP32

| GPIO | Function | Component | Notes |
|------|----------|-----------|-------|
| 21 | SDA (I2C) | SSD1306 OLED | |
| 22 | SCL (I2C) | SSD1306 OLED | |
| 26 | Digital Out | Vibration motor | Via 2N2222 NPN |
| 27 | PWM Out | Buzzer (optional) | Via 100Ω resistor |
| 36 | ADC Input | Battery voltage | Input-only |
| 2  | Digital Out | Status LED | Built-in |

### 3.4 PCA9685 Servo Channels

| Channel | Joint | Servo | Range |
|---------|-------|-------|-------|
| 0 | Base rotation | MG996R | 0–180° |
| 1 | Shoulder | MG996R | 0–180° |
| 2 | Elbow | MG996R | 0–180° |
| 3 | Gripper | MG996R | 0° closed → 180° open |

---

## SECTION 4 — CIRCUIT DIAGRAMS

### 4.1 Flex Sensor Circuit (per finger)

```
3.3V ──┬─── [Flex Sensor] ──┬─── GPIO (ADC)
       │                    │
      N/A               [10kΩ R]
                            │
                           GND
```
- The flex sensor resistance increases when bent (10kΩ → 110kΩ)
- Voltage divider converts resistance change to voltage
- ADC reads voltage: straight = ~2.0V, bent = ~3.0V

### 4.2 HC-SR04 Echo Level Shifter (5V → 3.3V)

```
HC-SR04 ECHO (5V) ──[1kΩ]──┬── ESP32 GPIO 18
                             │
                           [2kΩ]
                             │
                            GND
```
- Output = 5V × 2/(1+2) = 3.33V ✓ (within ESP32 tolerance)

### 4.3 Vibration Motor Drive Circuit

```
ESP32 GPIO ──[100Ω]── 2N2222 BASE
                      2N2222 COLLECTOR ── Vibration Motor ── 3.3V
                      2N2222 EMITTER  ── GND
                      [1N4007 diode across motor, cathode to 3.3V]
```

### 4.4 Power Distribution

```
3S Battery Pack (11.1V)
        │
       [BMS]
        │
       [10A Fuse]
        │
   [Main Switch]
        │
        ├──────── [BTS7960] ──── 4× DC Motors (12V direct)
        │
        ├── [LM2596 #1] ─── 7.5V ─── [PCA9685 V+] ─── 4× MG996R
        │
        └── [LM2596 #2] ─── 5V  ─── [ESP32 VIN]
                                 ├── [HC-SR04 VCC]
                                 ├── [PCA9685 VCC]
                                 └── [Cooling Fan]
```

---

## SECTION 5 — FIRMWARE LOG

### 2026-08-17 | 3-Node Topology Configured

| File | Version | Status |
|------|---------|--------|
| cynexis_mac.h | 1.2 | ✅ Programmed physical Robot MAC `04:B2:47:82:38:FC`. |
| control_glove.ino | 1.2 | ✅ Re-pointed `receiverMAC` to the physical Robot ESP32 MAC address. |
| status_glove.ino | 1.2 | ✅ Replaced glove packet parsing with RobotToStatusPacket parsing to display robot state, subsystems, and error codes. |

### 2026-08-16 | Phase 3, 4 Integration (Robot ESP32 setup)

| File | Version | Status |
|------|---------|--------|
| robot_esp32.ino | 1.1 | ✅ Updated includes, conditionalized callback for Core 2.x/3.x, and implemented dynamic Control Glove peer registration. |
| cynexis_mac.h | 1.1 | ✅ Saved Status Glove MAC address as `28:05:A5:E2:85:B8`. |

### 2026-08-14 | Phase 2, 3, 4 Integration Complete

| File | Version | Status |
|------|---------|--------|
| control_glove.ino | 1.1 | ✅ Updated Pinky pin to GPIO 36 (SVP / ADC1) to fix Wi-Fi driver conflict. |
| status_glove.ino | 1.1 | ✅ Added temporary calibration structs, `getBendPercentage`, `getFingerState`, and configurable `classifyGesture`. |
| monitor.py | 1.0 | ✅ Created custom Python monitor tool for stable serial debugging. |

### 2026-08-03 | Initial firmware created

| File | Version | Status |
|------|---------|--------|
| cynexis_protocol.h | 1.0 | ✅ Created |
| cynexis_mac.h | 1.0 | ✅ Created — MACs need updating |
| control_glove.ino | 1.0 | ✅ Created |
| robot_esp32.ino | 1.0 | ✅ Created |
| status_glove.ino | 1.0 | ✅ Created |

**IMPORTANT:** Before first flash, update MAC addresses in `cynexis_mac.h`

### Pending firmware tasks
- [ ] Calibrate flex sensor thresholds (after permanent glove assembly)
- [ ] Tune servo SERVO_MIN_PULSE / SERVO_MAX_PULSE values
- [ ] Tune gesture detection thresholds
- [ ] Tune IMU tilt angles for motor control
- [ ] Implement Madgwick filter for yaw (replaces naive gyro integration)
- [ ] Add EEPROM storage for calibration values

---

## SECTION 6 — ERROR LOG

| Date | Error | Cause | Fix | Status |
|------|-------|-------|-----|--------|
| 2026-08-14 | Pinky sensor stuck at 0 | ESP32 shares ADC2 with Wi-Fi/ESP-NOW subsystem. Calling analogRead() on GPIO 25 (ADC2) fails when Wi-Fi is enabled. | Moved Pinky sensor to GPIO 36 (SVP / ADC1 pin) which is independent of Wi-Fi. | RESOLVED |

---

## SECTION 7 — TEST RESULTS

### Phase 1 Tests (verified)

| Test ID | Description | Expected | Actual | Pass/Fail |
|---------|-------------|----------|--------|-----------|
| T1.01 | ESP32 LED blink | LED blinks 1Hz | LED blinks successfully | PASS |
| T1.02 | Serial monitor output | "Hello CYNEXIS" printed | Header and details printed successfully | PASS |
| T1.03 | ESP-NOW link | Glove packet received by robot | Packets received by status glove | PASS |
| T1.04 | MAC address read | 6-byte MAC printed | MAC address printed correctly | PASS |

### Phase 3 Tests (motor driver - pending physical base setup)

| Test ID | Description | Expected | Actual | Pass/Fail |
|---------|-------------|----------|--------|-----------|
| T3.01 | Motor forward | All 4 wheels spin forward | — | — |
| T3.02 | Motor reverse | All 4 wheels spin reverse | — | — |
| T3.03 | Motor left turn | Left stop, right forward | — | — |
| T3.04 | Motor right turn | Right stop, left forward | — | — |
| T3.05 | E-stop cut | All motors stop within 100ms | — | — |
| T3.06 | Current draw | ≤2.5A average at no load | — | — |
| T3.07 | BTS7960 temp | <60°C after 5min run | — | — |

### Phase 4 Tests (control glove - verified on breadboard)

| Test ID | Description | Expected | Actual | Pass/Fail |
|---------|-------------|----------|--------|-----------|
| T4.01 | Flex raw read | ADC ~2000 open, ~3500 closed | Readings range ~200 to ~1100 (breadboard configuration) | PASS |
| T4.02 | IMU roll/pitch | ±90° range correct | Pending physical IMU assembly | PENDING |
| T4.03 | ESP-NOW packet TX | 50 packets/sec at robot | Verified ~50 Hz update rate | PASS |
| T4.04 | Gesture FIST | All fingers bent → FIST detected | OPEN HAND and PARTIAL states mapped and verified | PASS |
| T4.05 | E-stop gesture | 2-second fist → emergency flag | Pending final gesture dictionary integration | PENDING |

---

## SECTION 8 — POWER MEASUREMENTS

| Component | Measured V | Measured A | Measured W | Notes |
|-----------|-----------|-----------|-----------|-------|
| 4× DC Motors (idle) | — | — | — | |
| 4× DC Motors (loaded) | — | — | — | |
| 4× MG996R (idle) | — | — | — | |
| 4× MG996R (loaded) | — | — | — | |
| ESP32 (active Wi-Fi) | — | — | — | |
| HC-SR04 | — | — | — | |
| Total system | — | — | — | |
| Battery runtime | — | — | — | minutes |

---

## SECTION 9 — DECISIONS & RATIONALE

| Decision | Reason | Alternative Rejected | Date |
|----------|--------|---------------------|------|
| ESP-NOW over Wi-Fi TCP | <1ms latency, no router needed | Wi-Fi TCP: router-dependent, 5-50ms | 2026-08-03 |
| BTS7960 over L298N | 43A peak, no heatsink overheating | L298N: 2A max, gets very hot | 2026-08-03 |
| PCA9685 over direct PWM | Frees ESP32 pins, hardware PWM | Direct PWM: wastes GPIO, jitter | 2026-08-03 |
| USB camera (V1) | Simplicity, zero extra cost | Raspberry Pi cam: +$35, added complexity | 2026-08-03 |
| Buzzer optional | OLED+vibration sufficient for V1 | Keep: only adds value for critical alert | 2026-08-03 |

---

## SECTION 10 — WOKWI SIMULATION PLAN

### Simulations to build (after hardware arrives for comparison)

| Simulation | File | Status |
|-----------|------|--------|
| Control Glove (flex + IMU + ESP-NOW) | Simulation/Wokwi/ControlGlove/ | ⏳ |
| Robot ESP32 (motors + servos + watchdog) | Simulation/Wokwi/RobotESP32/ | ⏳ |
| Status Glove (OLED + vibration) | Simulation/Wokwi/StatusGlove/ | ⏳ |

---

*Last updated: 2026-08-03*
*CYNEXIS Development Notebook — Keep this file updated daily.*
