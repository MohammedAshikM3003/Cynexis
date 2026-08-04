# CYNEXIS v1.0 — Hardware Shopping Guide
> **This is the ONLY hardware document to follow.**
> Architecture locked. No voice control. No hologram. No MongoDB. No MQTT.
> Last updated: 2026-08-03

---

## What You Are Building

```
[Control Glove]  ──ESP-NOW──►  [Robot ESP32]  ──USB──►  [Laptop]
  5 flex sensors                4x DC motors              OpenCV
  MPU6050 IMU                   4x MG996R servos          YOLOv8
  ESP32                         BTS7960                   MediaPipe
  3.7V battery                  PCA9685
                                HC-SR04
                ◄──ESP-NOW──  [Status Glove]
                                SSD1306 OLED
                                Vibration motor
                                ESP32
```

---

## LIST A — Buy Tomorrow
> Purpose: Test ESP32 nodes, flex sensors, IMU, OLED, battery system.
> Hardware arrives, flash, verify, done. No motors needed yet.

### Controllers
| # | Component | Qty | Unit Price (Rs.) | Total (Rs.) |
|---|-----------|-----|-----------------|-------------|
| 1 | ESP32 Dev Module (38-pin WROOM-32) | 3 | 400 | 1,200 |

### Sensor Modules
| # | Component | Qty | Unit Price (Rs.) | Total (Rs.) |
|---|-----------|-----|-----------------|-------------|
| 2 | MPU6050 IMU module | 1 | 150 | 150 |
| 3 | SSD1306 OLED 0.96" I2C | 1 | 250 | 250 |
| 4 | Flex Sensor 2.2" | 5 + 1 spare | 350 | ~2,100 |
| 5 | Vibration motor (3V coin-type) | 1 | 50 | 50 |

### Power Modules
| # | Component | Qty | Unit Price (Rs.) | Total (Rs.) |
|---|-----------|-----|-----------------|-------------|
| 6 | 18650 Li-ion cell (2500-3500 mAh) | 6-8 | ~333 | ~2,000-2,700 |
| 7 | TP4056 Type-C charging module | 2 | 40 | 80 |
| 8 | Power switch SPST >= 5A | 3 | 30 | 90 |

> **Battery holders — DO NOT BUY YET.**
> Confirm mechanical design first:
> - Robot: 3-cell holder
> - Control glove: single-cell holder
> - Status glove: single-cell holder
> Buy after you decide the exact configuration.

### Prototyping Components
| # | Component | Qty | Unit Price (Rs.) | Total (Rs.) |
|---|-----------|-----|-----------------|-------------|
| 9 | Breadboard (full size) | 2 | 150 | 300 |
| 10 | Jumper wires (M-M, M-F, F-F sets) | 3 sets | 150 | 450 |
| 11 | Resistor kit (assorted, incl. 10k) | 1 kit | 150 | 150 |
| 12 | Capacitor kit (assorted) | 1 kit | 200 | 200 |
| 13 | LED pack (assorted) | 1 pack | 100 | 100 |
| 14 | 2N2222 NPN transistor | 4 | 8 | 30 |
| 15 | Male header pins | 2 packs | 30 | 60 |
| 16 | Female header pins | 2 packs | 30 | 60 |
| 17 | Heat-shrink tubing (assorted) | 1 pack | 80 | 80 |
| 18 | Electrical tape | 1 roll | 30 | 30 |
| 19 | Zip ties | 1 pack | 50 | 50 |

### Mechanical
| # | Component | Qty | Unit Price (Rs.) | Total (Rs.) |
|---|-----------|-----|-----------------|-------------|
| 20 | Cotton glove (Size L) | 2 | 50 | 100 |

### LIST A TOTAL: Rs. ~7,300 – 8,000
> (Depends on how many 18650 cells and whether you find the spare flex sensor)

What you can test with List A:
- All 3 ESP32 nodes power on
- ESP-NOW communication (glove to robot)
- Flex sensor ADC readings (5 fingers)
- MPU6050 roll / pitch / yaw
- SSD1306 OLED display
- Vibration motor feedback
- Battery charging via TP4056
- MAC addresses recorded — update cynexis_mac.h

---

## LIST B — Buy Next Week
> Purpose: Add motor driver, servo driver, power management.
> Only buy after List A tests pass.

| # | Component | Qty | Unit Price | Total |
|---|-----------|-----|------------|-------|
| 1 | BTS7960 Motor Driver (43A) | 1 | 350 | 350 |
| 2 | PCA9685 16-ch Servo Driver (I2C) | 1 | 200 | 200 |
| 3 | LM2596 Adjustable Buck Converter | 2 | 80 | 160 |
| 4 | HC-SR04 Ultrasonic Sensor | 1 | 80 | 80 |
| 5 | XT60 Connector pair (M+F) | 2 | 50 | 100 |
| 6 | BMS 3S 10A | 1 | 100 | 100 |
| 7 | 1N4007 Diode | 10 | 5 | 50 |
| 8 | TVS Diode 15V DO-15 | 2 | 10 | 20 |
| 9 | 10A Fuse + inline blade holder | 1 | 50 | 50 |
| 10 | Heatsink (small) | 2 | 40 | 80 |
| 11 | E-stop button (NC momentary, red) | 1 | 60 | 60 |

### LIST B TOTAL: Rs. 1,250

What you can test with List B:
- Motor driver wired and spinning DC motors
- Servo driver controlling arm joints
- HC-SR04 obstacle detection
- Full power system (BMS + fuse + XT60)
- E-stop cuts all motors within 100ms

---

## LIST C — Buy Later
> Purpose: Final robot body and vision.
> Only buy after motor control is working.

| # | Component | Qty | Unit Price | Total |
|---|-----------|-----|------------|-------|
| 1 | Aluminium 4WD Robot Chassis Kit | 1 | 1,200 | 1,200 |
| 2 | DC Gear Motor 12V (150-300 RPM) | 4 | 200 | 800 |
| 3 | MG996R Servo Motor | 4 | 250 | 1,000 |
| 4 | 4-DOF Aluminium Arm Kit | 1 | 800 | 800 |
| 5 | USB Webcam (720p minimum, 30fps) | 1 | 600 | 600 |

### LIST C TOTAL: Rs. 4,400

---

## Grand Total

| Stage | Buy When | Cost |
|-------|----------|------|
| List A | Tomorrow | Rs. 7,200 |
| List B | Next week (after A tests pass) | Rs. 1,250 |
| List C | Later (after motor control works) | Rs. 4,400 |
| GRAND TOTAL | | Rs. 12,850 |

---

## Where to Buy

| Store | Best For |
|-------|----------|
| robu.in | ESP32, motors, 18650 cells, chassis |
| robocraze.com | Flex sensors, PCA9685, servos |
| flyrobo.in | Flex sensors (often cheapest) |
| quartzcomponents.com | Resistors, diodes, capacitors, transistors |
| Amazon / Flipkart | Webcam, cotton gloves, battery holders |

---

## Important Notes

1. Flex sensors — specify 2.2 inch, NOT 4.5 inch
2. ESP32 — get the 38-pin version (WROOM-32), NOT the 30-pin version
3. 18650 cells — buy genuine (Samsung 25R/35E or Panasonic). Avoid no-brand cells
4. TP4056 — charges individual 3.7V cells only. For the full 3S robot pack you need a 12.6V balance charger separately
5. BTS7960 — always attach the heatsink BEFORE running motors

---

## Removed from This Project (Do Not Add Back)

| Feature | Status |
|---------|--------|
| Voice control | Removed in v1.0 |
| Holographic module | Removed in v1.0 |
| MongoDB | Removed in v1.0 |
| MQTT | Removed in v1.0 |
| TensorFlow | Replaced by YOLOv8 + MediaPipe |

> Architecture is locked. Do not change unless there is a critical reason.

---

*CYNEXIS v1.0 — Buy List A tomorrow. That is all.*
