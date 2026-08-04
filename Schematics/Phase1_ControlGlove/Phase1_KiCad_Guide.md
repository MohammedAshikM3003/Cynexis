# CYNEXIS Phase 1 — KiCad Schematic Guide
> Project: CYNEXIS_Phase1_ControlGlove
> KiCad version: 10.0.5
> Purpose: Professional control glove schematic for review and hardware assembly

---

## DIRECTORY STRUCTURE

```
Schematics/Phase1_ControlGlove/
├── CYNEXIS_Phase1_ControlGlove.kicad_pro   ← KiCad creates this
├── CYNEXIS_Phase1_ControlGlove.kicad_sch   ← KiCad creates this
├── Symbols/                                 ← Custom symbols (ESP32 if needed)
├── Footprints/                              ← Custom footprints (Phase 2+)
└── Output/
    ├── CYNEXIS_Phase1_ControlGlove.pdf      ← Export here
    └── CYNEXIS_Phase1_ControlGlove_ERC.txt ← ERC report here
```

---

## STEP 1 — Create the KiCad Project

1. Open **KiCad 10.0.5**
2. Click **File → New Project**
3. Navigate to: `d:\Cynexis\Schematics\Phase1_ControlGlove\`
4. Project name: `CYNEXIS_Phase1_ControlGlove`
5. Click **Save**
6. KiCad creates `.kicad_pro` and `.kicad_sch` automatically
7. Double-click **Schematic Editor** to open it

---

## STEP 2 — Schematic Page Setup

1. In Schematic Editor: **File → Page Settings**
2. Set:
   - Paper size: **A3** (large enough for all components)
   - Title: `CYNEXIS Phase 1 - Control Glove`
   - Date: `2026-08-04`
   - Revision: `1.0`
   - Company: `CYNEXIS`
3. Click **OK**

---

## STEP 3 — Add Symbols (Press `A` to open Symbol Chooser)

Add these symbols in this order. Press `A`, search, place, press `Escape` between each.

### 3.1 — ESP32 DevKit V1

- Press `A`
- Search: `ESP32`
- Look for: **ESP32-WROOM-32** (in `RF_Module` library)
- If not found, search: `Connector_Generic` and use a 38-pin connector as placeholder
- Place in the **centre** of the schematic
- Right-click → **Properties** → Set Reference: `U1`, Value: `ESP32-WROOM-32`

### 3.2 — MPU6050

- Press `A`
- Search: `MPU6050`
- Library: **Sensor_Motion**
- Place **above-left** of ESP32
- Reference: `U2`, Value: `MPU6050`

### 3.3 — Flex Sensors (×5) — Use Resistor as Symbol

> Flex sensors have no standard KiCad symbol. Use a resistor symbol with a custom value.

- Press `A` → Search: `R`
- Library: **Device** → **R** (standard resistor)
- Place 5 resistors **to the right** of ESP32, stacked vertically
- Set values:
  - R1: `FLEX_THUMB` (10k-110k Ω)
  - R2: `FLEX_INDEX`
  - R3: `FLEX_MIDDLE`
  - R4: `FLEX_RING`
  - R5: `FLEX_PINKY`

### 3.4 — Pull-down Resistors (×5, 10kΩ each)

- Press `A` → Search: `R` → Library: **Device → R**
- Place one 10kΩ resistor below each flex sensor symbol
- Set values: `10k` each
- References: R6 through R10

### 3.5 — Status LED

- Press `A` → Search: `LED`
- Library: **Device → LED**
- Place **below** ESP32
- Reference: `D1`, Value: `LED_GREEN`

### 3.6 — LED Current Limiting Resistor

- Press `A` → Search: `R` → Library: **Device → R**
- Value: `220`
- Reference: `R11`
- Place between GPIO2 and LED anode

### 3.7 — TP4056 Module

- Press `A` → Search: `TP4056`
- If not found: Search `Conn_01x04` (4-pin connector) as placeholder
- Reference: `U3`, Value: `TP4056_TypeC`

### 3.8 — 18650 Battery

- Press `A` → Search: `Battery`
- Library: **Device → Battery**
- Reference: `BT1`, Value: `18650_3.7V`

### 3.9 — Power Switch

- Press `A` → Search: `SW_SPST`
- Library: **Switch → SW_SPST**
- Reference: `SW1`, Value: `SPST_5A`

### 3.10 — Power Symbols (add these everywhere needed)

- Press `P` (Power symbol)
- Add `+3.3V` → place near ESP32 3V3 pin and MPU6050 VCC
- Add `GND` → place near all GND pins
- Add `+BATT` → place at battery positive output

---

## STEP 4 — Connect Components (Press `W` to draw wire)

### 4.1 — MPU6050 Connections

| MPU6050 Pin | Wire to | Net Label |
|-------------|---------|-----------|
| VCC | Power symbol +3.3V | — |
| GND | Power symbol GND | — |
| SDA | ESP32 GPIO21 | SDA |
| SCL | ESP32 GPIO22 | SCL |
| AD0 | Power symbol GND | — |
| INT | Leave unconnected (add × marker) | — |

### 4.2 — Flex Sensor Voltage Dividers

For each finger:
```
+3.3V
  │
[Flex Rx]  ← variable resistor symbol
  │
  ├──── Net Label: FLEX_THUMB (or INDEX etc.)
  │
[10kΩ pull-down]
  │
GND
```

Connect each junction point to ESP32:
| Net Label | ESP32 GPIO |
|-----------|------------|
| FLEX_THUMB | GPIO34 |
| FLEX_INDEX | GPIO35 |
| FLEX_MIDDLE | GPIO32 |
| FLEX_RING | GPIO33 |
| FLEX_PINKY | GPIO39 |

### 4.3 — LED Circuit

```
ESP32 GPIO2 ── R11 (220Ω) ── D1 Anode
                              D1 Cathode ── GND
```

### 4.4 — Power Chain

```
BT1(+) ── SW1 ── TP4056 IN+
BT1(-) ── TP4056 IN-
TP4056 OUT+ ── ESP32 VIN
TP4056 OUT- ── GND
```

---

## STEP 5 — Add Net Labels (Press `L`)

Add these net labels at the junction points. Labels with the same name are connected automatically without drawing wire across the schematic.

| Label | Place at |
|-------|---------|
| `FLEX_THUMB` | Junction between flex sensor and ESP32 GPIO34 |
| `FLEX_INDEX` | Junction between flex sensor and ESP32 GPIO35 |
| `FLEX_MIDDLE` | Junction between flex sensor and ESP32 GPIO32 |
| `FLEX_RING` | Junction between flex sensor and ESP32 GPIO33 |
| `FLEX_PINKY` | Junction between flex sensor and ESP32 GPIO39 |
| `SDA` | MPU6050 SDA ↔ ESP32 GPIO21 |
| `SCL` | MPU6050 SCL ↔ ESP32 GPIO22 |

> **Tip:** Using net labels instead of long wires makes the schematic much cleaner. You do NOT need to draw a physical wire from GPIO39 all the way to the flex sensor if you use matching labels on both ends.

---

## STEP 6 — Add No-Connect Markers (Press `Q`)

Add × markers on unused ESP32 pins. This prevents ERC errors.

Common unused pins to mark:
- ESP32: GPIO0, GPIO1 (TX), GPIO3 (RX), GPIO4, GPIO5, GPIO12-GPIO19 (unused ones), EN, etc.

---

## STEP 7 — Add Text Annotations

Press `T` to add text boxes:

- Top of schematic: `CYNEXIS v1.0 — Phase 1 Control Glove`
- Near flex sensors: `10kΩ pull-down voltage divider. ADC range: ~1.6V (straight) to ~3.0V (bent)`
- Near power: `3.7V Li-ion → TP4056 → ESP32 VIN (3.6V-5.5V range)`
- Near MPU6050: `I2C addr: 0x68 (AD0=GND)`

---

## STEP 8 — Run ERC (Electrical Rule Check)

1. **Inspect → Electrical Rules Checker**
2. Click **Run ERC**
3. Fix any **Errors** (red) before proceeding
4. **Warnings** (yellow) — review but can be acceptable
5. Common ERC errors:
   - `Pin unconnected` → add No-Connect marker (`Q`)
   - `Power pin not driven` → add PWR_FLAG symbol near power symbols
   - `Wire not connected` → click the dangling wire end and connect or trim

---

## STEP 9 — Export PDF

1. **File → Export → PDF**
2. Save to: `d:\Cynexis\Schematics\Phase1_ControlGlove\Output\CYNEXIS_Phase1_ControlGlove.pdf`
3. Settings:
   - Scale: Fit page
   - Black and white: No (keep colors)
   - Output file: as above

---

## STEP 10 — Save and Commit to GitHub

1. **File → Save** (Ctrl+S) in KiCad
2. Back in Antigravity IDE terminal:

```
git add Schematics/
git commit -m "schematic: Phase1 KiCad control glove schematic v1.0"
git push origin main
```

---

## IMPORTANT NOTES

| Note | Detail |
|------|--------|
| **ESP32 symbol** | If KiCad doesn't have ESP32-WROOM-32 in its library, use `Connector_Generic:Conn_01x38` as a placeholder. The schematic is for documentation, not manufacturing yet. |
| **Flex sensor symbol** | No standard symbol exists. Using `Device:R` with a custom value is the correct professional approach. |
| **No PCB yet** | Ignore all Footprint warnings. PCB design is Phase 5+. |
| **ERC PWR_FLAG** | If you get "Power pin not driven" errors, press `P` and add `PWR_FLAG` symbol connected to +3.3V and GND nets. |

---

*Complete this schematic before buying hardware. It will confirm your wiring plan before you solder anything.*
