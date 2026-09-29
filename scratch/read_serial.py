import serial
import time

try:
    s = serial.Serial('COM5', 115200, timeout=1)
    time.sleep(0.2)
    s.dtr = False
    s.rts = True
    time.sleep(0.1)
    s.rts = False
    start = time.time()
    while time.time() - start < 7:
        if s.in_waiting:
            line = s.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)
    s.close()
except Exception as e:
    print(f"Error: {e}")
