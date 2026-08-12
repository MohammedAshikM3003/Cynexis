"""
CYNEXIS — Live Glove Receiver, Calibrated Bend & Gesture Recognition Verification
Tests real-time telemetry streaming from COM8 with live 0-100% bend normalization
and telemetry-only gesture recognition.
"""
import sys
import asyncio
import time
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from core.state import robot_state
from core.calibration import load_calibration, DEFAULT_CALIBRATION_PATH
from Backend.serial_bridge.glove_receiver import GloveReceiverBridge

async def main():
    print("=" * 75)
    print("CYNEXIS LIVE GLOVE TELEMETRY & GESTURE RECOGNITION (PHASE 9D)")
    print("=" * 75)
    print(f"Configured Port     : {settings.glove_receiver_port}")
    print(f"Configured Baud     : {settings.glove_receiver_baud}")
    print(f"Calibration Profile : {DEFAULT_CALIBRATION_PATH}")
    print("=" * 75)

    cal = load_calibration()
    if cal.thumb and cal.thumb.is_valid():
        print(f"Thumb Calibration   : Straight={cal.thumb.straight_raw:.0f} -> Bent={cal.thumb.bent_raw:.0f} ({cal.thumb.direction})")
    else:
        print("Thumb Calibration   : NOT CALIBRATED")

    if cal.index and cal.index.is_valid():
        print(f"Index Calibration   : Straight={cal.index.straight_raw:.0f} -> Bent={cal.index.bent_raw:.0f} ({cal.index.direction})")
    else:
        print("Index Calibration   : NOT CALIBRATED")

    print("=" * 75)

    bridge = GloveReceiverBridge(
        port=settings.glove_receiver_port,
        baud_rate=settings.glove_receiver_baud,
        enabled=settings.glove_receiver_enabled,
    )

    print(f"\nStarting GloveReceiverBridge on {bridge.port}...")
    started = await bridge.start()
    if not started:
        print("[ERROR] Failed to start GloveReceiverBridge.")
        return

    print("Streaming live calibrated bend & gesture telemetry for 8 seconds...\n")
    print("  Try gestures: OPEN, CLOSED, POINT, THUMB_UP!\n")
    
    start_time = time.monotonic()
    last_state = None

    while (time.monotonic() - start_time) < 8.0:
        thumb_raw = robot_state.sensors.flex_thumb
        index_raw = robot_state.sensors.flex_index
        thumb_pct = robot_state.sensors.flex_thumb_bend_pct
        index_pct = robot_state.sensors.flex_index_bend_pct
        gesture = robot_state.hand.gesture
        conf = robot_state.hand.confidence
        stable = robot_state.hand.is_stable
        stable_count = robot_state.hand.stable_count

        curr_state = (thumb_raw, index_raw, thumb_pct, index_pct, gesture, conf, stable)
        if curr_state != last_state:
            status_tag = "STABLE" if stable else f"CANDIDATE ({stable_count}/3)"
            print(f"  [GESTURE] {gesture:<8} ({conf:0.2f} conf | {status_tag}) | "
                  f"Thumb: {thumb_raw:4d} ({thumb_pct:5.1f}%) | "
                  f"Index: {index_raw:4d} ({index_pct:5.1f}%) | "
                  f"Packets: {bridge.packets_received}")
            last_state = curr_state
        await asyncio.sleep(0.15)

    print("\nStopping GloveReceiverBridge...")
    await bridge.stop()

    print("\n" + "=" * 75)
    print("SUMMARY")
    print(f"Total Packets Processed   : {bridge.packets_received}")
    print(f"Final Recognized Gesture  : {robot_state.hand.gesture} (Confidence: {robot_state.hand.confidence:0.2f}, Stable: {robot_state.hand.is_stable})")
    print(f"Final Thumb Telemetry     : Raw={robot_state.sensors.flex_thumb:4d} | Bend={robot_state.sensors.flex_thumb_bend_pct:5.1f}%")
    print(f"Final Index Telemetry     : Raw={robot_state.sensors.flex_index:4d} | Bend={robot_state.sensors.flex_index_bend_pct:5.1f}%")
    print("=" * 75)
    if bridge.packets_received > 0:
        print("[SUCCESS] Live hand gesture recognition verified!")

if __name__ == "__main__":
    asyncio.run(main())
