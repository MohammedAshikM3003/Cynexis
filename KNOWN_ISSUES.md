# CYNEXIS — Known Issues Log
> Add every problem here the moment it appears. Never delete entries. Mark them RESOLVED.
> Template below — copy it for each new issue.

---

## TEMPLATE (copy this for each new issue)

```
---
**Date:**
**ID:** ISSUE-XXX
**Component:**
**Phase:**
**Problem:**
**Possible Cause:**
**Attempted Solutions:**
  - [ ]
**Final Solution:**
**Status:** OPEN / IN PROGRESS / RESOLVED
---
```

---

## OPEN ISSUES

*None yet.*

---

## RESOLVED ISSUES

**Date:** 2026-08-14
**ID:** ISSUE-001
**Component:** Control Glove / ESP32 Hardware
**Phase:** Phase 2/3/4
**Problem:** Pinky flex sensor reading was stuck at 0.
**Possible Cause:** Connected to GPIO 25 (ADC2). The ESP32's ADC2 controller is shared with and disabled by the Wi-Fi/ESP-NOW radio driver when wireless transmission is active.
**Attempted Solutions:**
  - Tested various analog attenuation settings.
  - Verified physical breadboard connections.
**Final Solution:** Physically moved the Pinky wire to GPIO 36 (SVP / ADC1), which is independent of the Wi-Fi controller, and updated the pin define in the sketch.
**Status:** RESOLVED

---

## ISSUE INDEX

| ID | Date | Component | Problem (brief) | Status |
|----|------|-----------|-----------------|--------|
| ISSUE-001 | 2026-08-14 | Control Glove | Pinky flex stuck at 0 due to Wi-Fi ADC2 lock | RESOLVED |

---

*Update this file every time a problem is found. Never skip it. This is your debugging history.*
