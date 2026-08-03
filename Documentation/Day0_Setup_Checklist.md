# CYNEXIS — Software Installation Checklist
> Day 0 | 2026-08-03 | Complete before hardware arrives

---

## STATUS KEY

| Symbol | Meaning |
|--------|---------|
| ✅ | Installed and verified |
| ⚙️ | Installed, not yet configured |
| ⏳ | Not yet installed |
| ❌ | Failed — see notes |

---

## SECTION A — DESKTOP APPLICATIONS

| # | Software | Version | Purpose | Status | Download |
|---|----------|---------|---------|--------|----------|
| 1 | VS Code | 1.130+ | Main editor | ✅ Installed | code.visualstudio.com |
| 2 | Arduino IDE | 2.x | ESP32 flashing | ⏳ | arduino.cc/en/software |
| 3 | Python | 3.12 recommended | AI + backend | ⚙️ 3.8.10 (upgrade recommended) | python.org |
| 4 | Git | 2.x | Version control | ✅ 2.53.0 | git-scm.com |
| 5 | GitHub Desktop | latest | Repo UI | ⏳ | desktop.github.com |
| 6 | KiCad | 8.x | Circuit design | ⏳ | kicad.org |
| 7 | Fusion 360 | latest | CAD / mechanical | ⏳ | autodesk.com/fusion |
| 8 | Wokwi | (browser) | Simulation | ✅ wokwi.com | No install needed |
| 9 | Postman | latest | API testing | ⏳ | postman.com |

---

## SECTION B — VS CODE EXTENSIONS

| # | Extension | Purpose | Status |
|---|-----------|---------|--------|
| 1 | Python (ms-python.python) | Python IntelliSense | ✅ Installed |
| 2 | C/C++ (ms-vscode.cpptools) | C++ IntelliSense for Arduino | ✅ Installed |
| 3 | GitLens (eamodio.gitlens) | Git history & blame | ✅ Installed |
| 4 | Error Lens | Inline error display | ✅ Installed |
| 5 | Prettier | Code formatting | ✅ Installed |
| 6 | Code Runner | Run snippets | ✅ Installed |
| 7 | Indent Rainbow | Indent visualization | ✅ Installed |
| 8 | Better Comments | Color-coded comments | ✅ Installed |
| 9 | Code Spell Checker | Spell check in code | ✅ Installed |
| 10 | PlatformIO (manual) | Advanced ESP32 toolchain | ⏳ Install manually |
| 11 | CodeGeeX (manual) | AI coding assistant | ⏳ Install manually |
| 12 | CMake Tools | CMake support | ⏳ Install manually |

**Manual installs:** Open VS Code → Ctrl+Shift+X → search and install PlatformIO and CodeGeeX.

---

## SECTION C — ARDUINO IDE SETUP

After installing Arduino IDE 2.x, add ESP32 board support:

1. Open Arduino IDE → **File → Preferences**
2. In "Additional board manager URLs" add:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Go to **Tools → Board → Boards Manager**
4. Search `esp32` → Install **esp32 by Espressif Systems**
5. Select board: **Tools → Board → esp32 → ESP32 Dev Module**

**Libraries to install** (Tools → Manage Libraries):
| Library | Version | Used In |
|---------|---------|---------|
| Adafruit MPU6050 | latest | Control Glove |
| Adafruit Unified Sensor | latest | Required by MPU6050 |
| Adafruit SSD1306 | latest | Status Glove |
| Adafruit GFX Library | latest | Required by SSD1306 |
| Adafruit PWM Servo Driver | latest | Robot (PCA9685) |

---

## SECTION D — PYTHON PACKAGES

All packages installed successfully ✅

| Package | Version | Status |
|---------|---------|--------|
| numpy | latest | ✅ |
| opencv-python | 5.0.0.93 | ✅ |
| mediapipe | 1.0.0 | ✅ |
| ultralytics (YOLOv8) | 8.4.115 | ✅ |
| pyserial | 3.5 | ✅ |
| fastapi | latest | ✅ |
| uvicorn[standard] | latest | ✅ |
| websockets | 13.1 | ✅ |
| matplotlib | 3.7.5 | ✅ |
| pandas | latest | ✅ |
| torch | 2.4.1 | ✅ (auto-installed by ultralytics) |

> ⚠️ **Note:** Python 3.8.10 is installed. Python 3.12 is recommended for better performance with newer libraries. Upgrade when convenient — do not break the current working install.

---

## SECTION E — GIT & GITHUB

| Task | Status |
|------|--------|
| Git installed (2.53.0) | ✅ |
| `git init` run in d:\Cynexis | ✅ |
| Initial commit (39 files) | ✅ |
| Remote origin set to MohammedAshikM3003/Cynexis | ✅ |
| `git push -u origin main` | ⏳ (may need GitHub auth) |
| GitHub Desktop installed | ⏳ |

**If push fails** (authentication required):
```bash
# Option A: Use GitHub CLI
winget install GitHub.cli
gh auth login

# Option B: Generate a Personal Access Token
# GitHub.com -> Settings -> Developer Settings -> Personal Access Tokens
# Use token as password when prompted
```

---

## SECTION F — WOKWI SIMULATION

| File | Location | Status |
|------|----------|--------|
| `phase1_test.ino` | Simulation/Wokwi/ControlGlove/ | ✅ Ready |
| `diagram.json` | Simulation/Wokwi/ControlGlove/ | ✅ Ready |
| `wokwi.toml` | Simulation/Wokwi/ControlGlove/ | ✅ Ready |

**To simulate:**
1. Go to **wokwi.com**
2. Click **New Project → ESP32**
3. Copy the contents of `phase1_test.ino` into the editor
4. Click ▶ **Start Simulation**
5. Expected: LED blinks, Serial Monitor prints MAC + system info

---

## SECTION G — TODAY'S SUMMARY (Day 0 Completion)

| Task | Status |
|------|--------|
| Python packages installed | ✅ |
| VS Code extensions installed | ✅ |
| Project folder structure created | ✅ |
| ESP-NOW protocol designed | ✅ |
| Control Glove firmware written | ✅ |
| Robot ESP32 firmware written | ✅ |
| Status Glove firmware written | ✅ |
| Development notebook created | ✅ |
| Master system prompt v1.1 complete | ✅ |
| Wokwi simulation prepared | ✅ |
| .gitignore created | ✅ |
| Git init + initial commit | ✅ |
| GitHub remote configured | ✅ |
| README.md complete | ✅ |
| Arduino IDE setup | ⏳ Manual |
| Arduino libraries installed | ⏳ After Arduino IDE |
| GitHub push authenticated | ⏳ Needs auth |
| GitHub Desktop installed | ⏳ Optional |
| KiCad installed | ⏳ Needed later |
| Fusion 360 installed | ⏳ Needed later |
| Postman installed | ⏳ Needed later |

---

## WHAT'S NEXT (Day 1 — Hardware Arrives)

```
1. Flash phase1_test.ino to all 3 ESP32 nodes
2. Record MAC addresses → update cynexis_mac.h
3. Flash control_glove.ino to Glove ESP32
4. Flash robot_esp32.ino to Robot ESP32
5. Open Serial Monitor → verify "Robot ready" message
6. MILESTONE: LED on robot blinks when glove sends packet
```

---

*CYNEXIS — Day 0 Complete. Environment ready. Hardware incoming.* 🚀
