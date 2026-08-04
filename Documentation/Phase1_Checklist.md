# CYNEXIS — Phase 1 Preparation Checklist
> Complete every item before touching the hardware.
> Last updated: 2026-08-04

---

## PART 1 — Tools (have these ready before hardware arrives)

| # | Tool | Have it? |
|---|------|----------|
| 1 | Soldering iron | ☐ |
| 2 | Solder wire (60/40 or lead-free) | ☐ |
| 3 | Flux | ☐ |
| 4 | Multimeter | ☐ |
| 5 | Wire stripper | ☐ |
| 6 | Heat-shrink tubing | ☐ (in List A) |
| 7 | USB-A to Micro-USB or USB-C cable (for ESP32) | ☐ |
| 8 | Breadboard | ☐ (in List A) |
| 9 | Jumper wires | ☐ (in List A) |
| 10 | Screwdriver set (Phillips + flathead) | ☐ |
| 11 | Electrical tape | ☐ (in List A) |
| 12 | Power bank (5V, ≥2A) | ☐ |

---

## PART 2 — Software (verify before hardware arrives)

| # | Task | Status |
|---|------|--------|
| 1 | Arduino IDE 2.3.10 installed | ✅ |
| 2 | ESP32 board support (Espressif) installed | ✅ |
| 3 | Board selected: ESP32 Dev Module | ✅ |
| 4 | All 5 Adafruit libraries installed | ✅ |
| 5 | Python 3.12.10 venv active at d:\Cynexis\.venv | ✅ |
| 6 | All Python packages installed | ✅ |
| 7 | PlatformIO v3.3.4 installed | ✅ |
| 8 | Git configured + GitHub remote verified | ✅ |

---

## PART 3 — Firmware (ready to flash)

| # | File | Location | Status |
|---|------|----------|--------|
| 1 | phase1_test.ino | Firmware/Phase1/ | ✅ Ready |
| 2 | cynexis_protocol.h | Firmware/Protocol/ | ✅ Ready |
| 3 | cynexis_mac.h | Firmware/Protocol/ | ⚠️ MACs are placeholders — update after Step 5 |
| 4 | control_glove.ino | Firmware/ControlGlove/ | ✅ Ready |
| 5 | robot_esp32.ino | Firmware/RobotESP32/ | ✅ Ready |
| 6 | status_glove.ino | Firmware/StatusGlove/ | ✅ Ready |

---

## PART 4 — Phase 1 Procedure (execute in order)

### Step 1 — Power-on test
- [ ] Connect ESP32 #1 via USB
- [ ] Open Arduino IDE → Serial Monitor (115200 baud)
- [ ] Verify power LED is on
- [ ] Repeat for ESP32 #2 and #3

### Step 2 — Flash phase1_test.ino
- [ ] Open `Firmware/Phase1/phase1_test.ino`
- [ ] Select board: Tools → Board → esp32 → ESP32 Dev Module
- [ ] Select port: Tools → Port → (your COM port)
- [ ] Upload → verify "Done uploading"
- [ ] Serial Monitor → confirm output: MAC address + "Hello CYNEXIS"
- [ ] Repeat for all 3 ESP32 boards

### Step 3 — Record MAC addresses
- [ ] Write down MAC of ESP32 #1 (Control Glove)
- [ ] Write down MAC of ESP32 #2 (Robot)
- [ ] Write down MAC of ESP32 #3 (Status Glove)
- [ ] Open `Firmware/Protocol/cynexis_mac.h`
- [ ] Replace placeholder MACs with actual values
- [ ] Save + commit to GitHub

### Step 4 — Flash final firmware
- [ ] Flash `control_glove.ino` → Glove ESP32
- [ ] Flash `robot_esp32.ino` → Robot ESP32
- [ ] Flash `status_glove.ino` → Status ESP32

### Step 5 — Verify ESP-NOW link
- [ ] Power on all 3 ESP32s
- [ ] Open Serial Monitor on Robot ESP32
- [ ] Verify: "Packet received from glove"
- [ ] Verify: ACK sent back to glove
- [ ] **MILESTONE: ESP-NOW link established ✅**

### Step 6 — Connect MPU6050 (Control Glove)
- [ ] Wire MPU6050 to ESP32 (SDA→GPIO21, SCL→GPIO22, VCC→3.3V, GND→GND)
- [ ] Upload glove firmware
- [ ] Serial Monitor → confirm roll/pitch/yaw values updating

### Step 7 — Connect Flex Sensors (Control Glove)
- [ ] Wire flex sensor 1 (Thumb) → GPIO34 with 10kΩ voltage divider
- [ ] Wire flex sensor 2 (Index) → GPIO35
- [ ] Wire flex sensor 3 (Middle) → GPIO32
- [ ] Wire flex sensor 4 (Ring) → GPIO33
- [ ] Wire flex sensor 5 (Pinky) → GPIO25
- [ ] Serial Monitor → confirm ADC values change when fingers bend

### Step 8 — Calibrate the glove
- [ ] Record ADC value for each finger STRAIGHT (open hand)
- [ ] Record ADC value for each finger BENT (closed fist)
- [ ] Update threshold values in control_glove.ino
- [ ] Test gesture detection: OPEN / FIST / POINT

### Step 9 — Integration test
- [ ] All 3 ESP32s powered and linked
- [ ] Bend fingers → verify gesture data arrives at Robot ESP32
- [ ] Tilt glove → verify IMU data arrives at Robot ESP32
- [ ] Form FIST for 2s → verify EMERGENCY flag set
- [ ] **PHASE 1 COMPLETE ✅**

---

## PART 5 — What to Log in the Notebook After Each Step

After completing each step, add an entry to `CYNEXIS_Development_Notebook.md`:

```
Date | Step | Result | Notes
```

If anything fails, create an entry in `KNOWN_ISSUES.md` immediately.

---

*Phase 1 is complete when Step 9 passes. Do not start Phase 2 before Phase 1 is fully verified.*
