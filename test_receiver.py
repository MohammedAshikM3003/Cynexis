import serial
import json
import time

PORT = "COM7"
BAUD = 115200

print("Opening", PORT)

ser = serial.Serial(PORT, BAUD, timeout=1)

print("CONNECTED:", ser.is_open)
print("Listening for CYNEXIS HAND_DATA for 10 seconds...")
print("-" * 50)

start = time.time()
count = 0

while time.time() - start < 10:
    line = ser.readline().decode("utf-8", errors="ignore").strip()

    if not line:
        continue

    print("RAW:", line)

    try:
        packet = json.loads(line)

        if packet.get("type") == "HAND_DATA":
            count += 1

            print(
                f"  ? HAND_DATA #{count} | "
                f"Thumb={packet.get('thumb')} | "
                f"Index={packet.get('index')}"
            )

    except json.JSONDecodeError:
        pass

ser.close()

print("-" * 50)
print("Packets received:", count)
print("TEST COMPLETE")
