import serial
import json
import time

PORT = "COM6"
BAUD = 115200

print(f"Opening {PORT}...")

ser = serial.Serial(PORT, BAUD, timeout=1)

print("CONNECTED")
print("Waiting for HAND_DATA...")
print("-" * 50)

packets = 0
start = time.time()

try:
    while time.time() - start < 30:
        line = ser.readline()

        if not line:
            continue

        text = line.decode("utf-8", errors="ignore").strip()

        if not text:
            continue

        try:
            data = json.loads(text)

            if data.get("type") == "HAND_DATA":
                packets += 1

                print(
                    f"HAND_DATA #{packets} | "
                    f"Thumb={data.get('thumb')} | "
                    f"Index={data.get('index')}"
                )

        except json.JSONDecodeError:
            # Ignore ESP32 boot/debug messages
            pass

finally:
    ser.close()

print("-" * 50)
print(f"Packets received: {packets}")
print("TEST COMPLETE")
