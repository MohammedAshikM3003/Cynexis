# CYNEXIS — Phase 1 Control Glove Wiring Guide
> Version: 1.0 | Date: 2026-08-04
> This is the complete wiring reference for building the control glove on a breadboard.

---

## 1. PIN MAPPING TABLE

| Signal | ESP32 GPIO | ADC Channel | Direction | Notes |
|--------|-----------|-------------|-----------|-------|
| Flex Thumb | GPIO34 | ADC1_CH6 | Input only | No pull-up possible |
| Flex Index | GPIO35 | ADC1_CH7 | Input only | No pull-up possible |
| Flex Middle | GPIO32 | ADC1_CH4 | Input/Output | Used as ADC input |
| Flex Ring | GPIO33 | ADC1_CH5 | Input/Output | Used as ADC input |
| Flex Pinky | **GPIO39** | ADC1_CH3 | Input only (VP) | No pull-up possible |
| MPU6050 SDA | GPIO21 | — | Input/Output | I2C data |
| MPU6050 SCL | GPIO22 | — | Input/Output | I2C clock |
| Battery sense | GPIO36 | ADC1_CH0 | Input only (VP) | Via 100kΩ divider |
| Status LED | GPIO2 | — | Output | Onboard LED |

> **GPIO34, 35, 36, 39 are input-only.** They cannot be used as outputs and have no internal pull-up resistors.

---

## 2. FLEX SENSOR VOLTAGE DIVIDER CIRCUIT

Each flex sensor needs a 10kΩ pull-down resistor to form a voltage divider.

```
3.3V ──────┬──────────────
           │
      [Flex Sensor]     ← resistance changes: ~10kΩ (straight) to ~110kΩ (bent)
           │
           ├────────── GPIO (ADC input)
           │
       [10kΩ Res]
           │
          GND
```

**Voltage output:**
| State | Flex R | Voltage at GPIO |
|-------|--------|----------------|
| Straight | ~10kΩ | ~1.65V (ADC ~2048) |
| Fully bent | ~110kΩ | ~3.03V (ADC ~3775) |

**Wire this 5 times** — one circuit per finger.

---

## 3. BREADBOARD WIRING TABLE

### Power Rails
| From | To | Wire Color |
|------|----|-----------|
| ESP32 3V3 | Breadboard + rail (top) | Red |
| ESP32 GND | Breadboard - rail (top) | Black |
| ESP32 GND | Breadboard - rail (bottom) | Black |

### Flex Sensor 1 — Thumb
| From | To | Wire Color |
|------|----|-----------|
| Breadboard + rail | Flex sensor pin 1 | Red |
| Flex sensor pin 2 | Breadboard row A1 | Orange |
| Breadboard row A1 | ESP32 GPIO34 | Orange |
| Breadboard row A1 | 10kΩ resistor pin 1 | Orange |
| 10kΩ resistor pin 2 | Breadboard - rail | Black |

### Flex Sensor 2 — Index
| From | To | Wire Color |
|------|----|-----------|
| Breadboard + rail | Flex sensor pin 1 | Red |
| Flex sensor pin 2 | Breadboard row B1 | Orange |
| Breadboard row B1 | ESP32 GPIO35 | Orange |
| Breadboard row B1 | 10kΩ resistor pin 1 | Orange |
| 10kΩ resistor pin 2 | Breadboard - rail | Black |

### Flex Sensor 3 — Middle
| From | To | Wire Color |
|------|----|-----------|
| Breadboard + rail | Flex sensor pin 1 | Red |
| Flex sensor pin 2 | Breadboard row C1 | Orange |
| Breadboard row C1 | ESP32 GPIO32 | Orange |
| Breadboard row C1 | 10kΩ resistor pin 1 | Orange |
| 10kΩ resistor pin 2 | Breadboard - rail | Black |

### Flex Sensor 4 — Ring
| From | To | Wire Color |
|------|----|-----------|
| Breadboard + rail | Flex sensor pin 1 | Red |
| Flex sensor pin 2 | Breadboard row D1 | Orange |
| Breadboard row D1 | ESP32 GPIO33 | Orange |
| Breadboard row D1 | 10kΩ resistor pin 1 | Orange |
| 10kΩ resistor pin 2 | Breadboard - rail | Black |

### Flex Sensor 5 — Pinky
| From | To | Wire Color |
|------|----|-----------|
| Breadboard + rail | Flex sensor pin 1 | Red |
| Flex sensor pin 2 | Breadboard row E1 | Orange |
| Breadboard row E1 | **ESP32 GPIO39** | Orange |
| Breadboard row E1 | 10kΩ resistor pin 1 | Orange |
| 10kΩ resistor pin 2 | Breadboard - rail | Black |

### MPU6050
| MPU6050 Pin | ESP32 Pin | Wire Color |
|-------------|----------|-----------|
| VCC | 3.3V (breadboard + rail) | Red |
| GND | GND (breadboard - rail) | Black |
| SDA | GPIO21 | Blue |
| SCL | GPIO22 | Yellow |
| INT | Not connected | — |
| AD0 | GND (sets I2C addr to 0x68) | Black |

### Status LED
| From | To | Wire Color |
|------|----|-----------|
| ESP32 GPIO2 | 220Ω resistor pin 1 | Green |
| 220Ω resistor pin 2 | LED anode (long leg) | Green |
| LED cathode (short leg) | GND (breadboard - rail) | Black |

---

## 4. POWER SECTION (Battery)

```
18650 Cell
    │ (+)
   [TP4056 IN+]
   [TP4056 IN-] ── Cell (-)
    │
   [TP4056 OUT+]
    │
  [SPST Switch]
    │
  ESP32 VIN   ← Powers entire ESP32 + sensors (3.3V regulated internally)
   [TP4056 OUT-] ── ESP32 GND
```

> TP4056 output: ~4.1V fully charged. ESP32 VIN handles 3.6V–5.5V. ✅

---

## 5. I2C ADDRESS

| Device | I2C Address | AD0 Pin |
|--------|------------|---------|
| MPU6050 | **0x68** | Tied to GND |

If a second MPU6050 is needed later, tie AD0 to 3.3V → address becomes 0x69.

---

## 6. TEST POINTS

After wiring, verify these with a multimeter before powering on:

| Test | Expected |
|------|---------|
| 3.3V rail to GND | 3.3V ±0.1V |
| GPIO34 to GND (finger straight) | ~1.6V |
| GPIO34 to GND (finger bent) | ~2.8–3.0V |
| MPU6050 SDA to GND (idle) | ~3.3V (pulled up) |
| MPU6050 SCL to GND (idle) | ~3.3V (pulled up) |
| LED anode to GND | 1.9–2.2V when on |

---

## 7. GPIO DECISION LOG

| GPIO | Original | Changed To | Date | Reason |
|------|---------|------------|------|--------|
| Flex Pinky | GPIO25 | **GPIO39** | 2026-08-04 | GPIO39 (VP) keeps all flex sensors on ADC1 bank, avoids ADC1/ADC2 conflict if Wi-Fi is enabled |

> **Note:** GPIO25 is on ADC2. When Wi-Fi or ESP-NOW is active, ADC2 pins become unreliable. GPIO39 is on ADC1, which is stable regardless of Wi-Fi state. This was the correct decision.

---

*Build this circuit, run control_glove_sim.ino in Wokwi first, then replicate on breadboard.*
