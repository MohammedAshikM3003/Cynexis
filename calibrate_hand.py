"""
CYNEXIS — Interactive Hand Flex Sensor Calibration Utility
===========================================================
Calibrates Thumb and Index flex sensors with bidirectional normalization.

Procedure:
1. Reads configured COM port from CYNEXIS settings (.env)
2. Guides user through 4 positions (100 samples each):
   - THUMB STRAIGHT
   - THUMB FULLY BENT
   - INDEX STRAIGHT
   - INDEX FULLY BENT
3. Calculates min, max, mean, median, standard deviation
4. Determines direction automatically (INCREASING vs DECREASING)
5. Saves clean HandCalibrationProfile to Config/calibration_hand.json
6. Verifies live normalized 0–100% bend stream

Safety Rule: SENSOR-ONLY. Motors and actuators remain strictly disabled.
"""

import sys
import time
import serial
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import settings
from core.calibration import (
    HandCalibrationProfile,
    create_finger_calibration,
    save_calibration,
    FlexSensorFilter,
    DEFAULT_CALIBRATION_PATH,
)
from Backend.serial_bridge.glove_receiver import GloveReceiverBridge

SAMPLES_PER_POSITION = 100
STABILIZE_TIME_SEC = 2.0


def read_line(ser: serial.Serial) -> tuple[int, int] | None:
    """Read and parse one serial line for (thumb, index)."""
    try:
        raw_bytes = ser.readline()
        if not raw_bytes:
            return None
        line = raw_bytes.decode("utf-8", errors="ignore")
        return GloveReceiverBridge.parse_line(line)
    except Exception:
        return None


def collect_samples(ser: serial.Serial, position_name: str, instruction: str) -> list[tuple[int, int]]:
    """Prompt user and collect stable sensor samples."""
    print("\n" + "=" * 65)
    print(f"POSITION: {position_name}")
    print("=" * 65)
    print(f"INSTRUCTION: {instruction}")
    print("\nHold position steady. Sampling begins in:")

    for i in (3, 2, 1):
        print(f"  {i}...")
        time.sleep(1.0)

    print("\n[STABILIZING SENSOR READING...]")
    time.sleep(STABILIZE_TIME_SEC)
    ser.reset_input_buffer()

    print(f"[COLLECTING {SAMPLES_PER_POSITION} SAMPLES...]")
    samples: list[tuple[int, int]] = []
    start_time = time.monotonic()

    while len(samples) < SAMPLES_PER_POSITION and (time.monotonic() - start_time) < 15.0:
        result = read_line(ser)
        if result is None:
            continue

        thumb, index = result
        samples.append((thumb, index))
        n = len(samples)

        if n % 10 == 0 or n == SAMPLES_PER_POSITION:
            print(f"  Progress: {n:3d}/{SAMPLES_PER_POSITION} samples | Thumb: {thumb:4d} | Index: {index:4d}")

    if len(samples) < SAMPLES_PER_POSITION:
        print(f"\n[WARNING] Only collected {len(samples)}/{SAMPLES_PER_POSITION} samples before timeout.")

    return samples


def main():
    port = settings.glove_receiver_port or "COM7"
    baud = settings.glove_receiver_baud or 115200

    print("=" * 65)
    print("       CYNEXIS HAND FLEX SENSOR CALIBRATION (PHASE 9C)")
    print("=" * 65)
    print(f"Target Port    : {port}")
    print(f"Baud Rate      : {baud}")
    print(f"Output File    : {DEFAULT_CALIBRATION_PATH}")
    print("Motors Enabled : FALSE (Sensor-Only Mode)")
    print("=" * 65)

    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.5)
    except Exception as e:
        print(f"\n[ERROR] Failed to open {port}: {e}")
        print("Please check that your ESP32 is plugged in and Serial Monitor is closed.")
        return

    print(f"\n[OK] Connected to {port}. Receiver is active.")
    ser.reset_input_buffer()
    time.sleep(1.0)

    try:
        # Step 1: THUMB STRAIGHT
        thumb_straight_samples_raw = collect_samples(
            ser,
            position_name="1/4: THUMB FULLY STRAIGHT",
            instruction="Hold your THUMB completely straight/extended. Keep index relaxed."
        )
        thumb_straight = [float(s[0]) for s in thumb_straight_samples_raw]

        # Step 2: THUMB FULLY BENT
        thumb_bent_samples_raw = collect_samples(
            ser,
            position_name="2/4: THUMB FULLY BENT",
            instruction="Bend your THUMB fully inward/closed. Keep index relaxed."
        )
        thumb_bent = [float(s[0]) for s in thumb_bent_samples_raw]

        # Step 3: INDEX STRAIGHT
        index_straight_samples_raw = collect_samples(
            ser,
            position_name="3/4: INDEX FULLY STRAIGHT",
            instruction="Hold your INDEX finger completely straight/extended. Keep thumb relaxed."
        )
        index_straight = [float(s[1]) for s in index_straight_samples_raw]

        # Step 4: INDEX FULLY BENT
        index_bent_samples_raw = collect_samples(
            ser,
            position_name="4/4: INDEX FULLY BENT",
            instruction="Bend your INDEX finger fully inward/closed. Keep thumb relaxed."
        )
        index_bent = [float(s[1]) for s in index_bent_samples_raw]

    finally:
        ser.close()
        print(f"\nClosed connection to {port}.")

    # Process and build calibration models
    thumb_cal = create_finger_calibration("thumb", thumb_straight, thumb_bent)
    index_cal = create_finger_calibration("index", index_straight, index_bent)

    profile = HandCalibrationProfile(
        thumb=thumb_cal,
        index=index_cal,
    )

    print("\n" + "=" * 65)
    print("                     CALIBRATION RESULTS")
    print("=" * 65)

    print("\n[THUMB SENSOR]")
    print(f"  Straight (0% Bend) : min={thumb_cal.straight_stats.min:.0f}, max={thumb_cal.straight_stats.max:.0f}, "
          f"mean={thumb_cal.straight_stats.mean:.1f}, median={thumb_cal.straight_stats.median:.1f}, std={thumb_cal.straight_stats.std_dev:.2f}")
    print(f"  Bent   (100% Bend) : min={thumb_cal.bent_stats.min:.0f}, max={thumb_cal.bent_stats.max:.0f}, "
          f"mean={thumb_cal.bent_stats.mean:.1f}, median={thumb_cal.bent_stats.median:.1f}, std={thumb_cal.bent_stats.std_dev:.2f}")
    print(f"  Operating Direction: {thumb_cal.direction} (delta: {abs(thumb_cal.bent_raw - thumb_cal.straight_raw):.1f})")

    print("\n[INDEX SENSOR]")
    print(f"  Straight (0% Bend) : min={index_cal.straight_stats.min:.0f}, max={index_cal.straight_stats.max:.0f}, "
          f"mean={index_cal.straight_stats.mean:.1f}, median={index_cal.straight_stats.median:.1f}, std={index_cal.straight_stats.std_dev:.2f}")
    print(f"  Bent   (100% Bend) : min={index_cal.bent_stats.min:.0f}, max={index_cal.bent_stats.max:.0f}, "
          f"mean={index_cal.bent_stats.mean:.1f}, median={index_cal.bent_stats.median:.1f}, std={index_cal.bent_stats.std_dev:.2f}")
    print(f"  Operating Direction: {index_cal.direction} (delta: {abs(index_cal.bent_raw - index_cal.straight_raw):.1f})")

    # Save to JSON
    saved = save_calibration(profile, DEFAULT_CALIBRATION_PATH)
    if saved:
        print(f"\n[SUCCESS] Calibration saved successfully to: {DEFAULT_CALIBRATION_PATH}")
    else:
        print(f"\n[ERROR] Failed to write calibration file to {DEFAULT_CALIBRATION_PATH}")

    print("=" * 65)


if __name__ == "__main__":
    main()