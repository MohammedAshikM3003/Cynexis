import serial
import sys
import time

if len(sys.argv) < 2:
    print("Usage: python monitor.py <COM_PORT> [BAUD_RATE]")
    sys.argv.append("COM7")  # Default to COM7 if none specified

port = sys.argv[1]
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

print(f"Connecting to {port} at {baud} baud...")
try:
    ser = serial.Serial(port, baud, timeout=1)
    print(f"Connected to {port} successfully. Press Ctrl+C to stop.\n")
    
    # Clear buffer
    ser.reset_input_buffer()
    
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)
        time.sleep(0.01)
except KeyboardInterrupt:
    print(f"\nMonitoring stopped for {port}.")
except Exception as e:
    print(f"\nError: {e}")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
