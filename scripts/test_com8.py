"""
CYNEXIS - COM8 Serial Verification Test
Safely reads and verifies incoming HAND_DATA JSON packets from COM8.
"""
import sys
import time
import json
import serial

PORT = "COM8"
BAUD = 115200
TIMEOUT_SEC = 10
TARGET_PACKETS = 5

def main():
    print(f"Connecting to {PORT} at {BAUD} baud...")
    try:
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD,
            timeout=1.0,
            rtscts=False,
            dsrdtr=False
        )
    except Exception as e:
        print(f"[ERROR] Failed to open {PORT}: {e}")
        sys.exit(1)

    print(f"[OK] {PORT} opened successfully. Listening for HAND_DATA packets (timeout: {TIMEOUT_SEC}s)...")
    
    start_time = time.time()
    valid_packets = 0
    raw_lines_received = 0

    try:
        while (time.time() - start_time) < TIMEOUT_SEC and valid_packets < TARGET_PACKETS:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            
            raw_lines_received += 1
            print(f"  [RAW] {line}")

            try:
                data = json.loads(line)
                if isinstance(data, dict) and data.get("type") == "HAND_DATA":
                    valid_packets += 1
                    thumb = data.get("thumb")
                    index = data.get("index")
                    print(f"  --> [VALID {valid_packets}/{TARGET_PACKETS}] HAND_DATA: thumb={thumb}, index={index}")
            except json.JSONDecodeError:
                pass

    finally:
        ser.close()
        print(f"Closed {PORT}.")

    print("\n--- Summary ---")
    print(f"Total raw lines: {raw_lines_received}")
    print(f"Valid HAND_DATA packets: {valid_packets}/{TARGET_PACKETS}")
    
    if valid_packets >= TARGET_PACKETS:
        print("[SUCCESS] COM8 stream verified!")
    elif valid_packets > 0:
        print("[PARTIAL] Received some HAND_DATA packets, but less than target.")
    else:
        print("[WARNING] No valid HAND_DATA packets received within timeout.")

if __name__ == "__main__":
    main()
