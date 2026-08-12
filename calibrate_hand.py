import serial
import time
import statistics

PORT = "COM6"
BAUD = 115200
SAMPLES = 100

# Values outside this range are treated as invalid ADC glitches.
VALID_MIN = 1
VALID_MAX = 4095

POSITIONS = [
    ("THUMB FULLY OPEN / INDEX RELAXED",
     "Keep thumb fully OPEN and index RELAXED."),
    ("THUMB FULLY CLOSED / INDEX RELAXED",
     "Keep thumb fully CLOSED and index RELAXED."),
    ("THUMB RELAXED / INDEX FULLY OPEN",
     "Keep thumb RELAXED and index fully OPEN."),
    ("THUMB RELAXED / INDEX FULLY CLOSED",
     "Keep thumb RELAXED and index fully CLOSED."),
]


def read_sensor_line(ser):
    """Read one Thumb/Index line from the receiver."""
    raw = ser.readline().decode("utf-8", errors="ignore").strip()

    if not raw:
        return None

    # Expected:
    # Thumb: 123   Index: 456
    if "Thumb:" not in raw or "Index:" not in raw:
        return None

    try:
        thumb_part = raw.split("Thumb:", 1)[1]
        thumb_text, index_part = thumb_part.split("Index:", 1)

        thumb = int(thumb_text.strip())
        index = int(index_part.strip())

        if not (VALID_MIN <= thumb <= VALID_MAX):
            return None

        if not (VALID_MIN <= index <= VALID_MAX):
            return None

        return thumb, index

    except (ValueError, IndexError):
        return None


def collect_position(ser, name, instruction):
    print("\n" + "=" * 60)
    print(f"POSITION: {name}")
    print("=" * 60)
    print(instruction)
    print()
    print("DO NOT MOVE while samples are being collected.")
    print()
    print("Starting in:")

    for i in (3, 2, 1):
        print(i)
        time.sleep(1)

    # Important stabilization period
    print("\nSTABILIZING SENSOR...")
    time.sleep(1.5)

    # Clear old serial data
    ser.reset_input_buffer()

    thumb_values = []
    index_values = []

    print(f"\nCollecting {SAMPLES} stable samples...\n")

    while len(thumb_values) < SAMPLES:
        result = read_sensor_line(ser)

        if result is None:
            continue

        thumb, index = result

        thumb_values.append(thumb)
        index_values.append(index)

        n = len(thumb_values)

        print(
            f"{n:3d}/{SAMPLES} | "
            f"Thumb={thumb:4d} | "
            f"Index={index:4d}"
        )

    thumb_median = statistics.median(thumb_values)
    index_median = statistics.median(index_values)

    thumb_mean = statistics.mean(thumb_values)
    index_mean = statistics.mean(index_values)

    thumb_min = min(thumb_values)
    thumb_max = max(thumb_values)
    index_min = min(index_values)
    index_max = max(index_values)

    # Robust 10th/90th percentile range
    thumb_sorted = sorted(thumb_values)
    index_sorted = sorted(index_values)

    thumb_p10 = thumb_sorted[int(SAMPLES * 0.10)]
    thumb_p90 = thumb_sorted[int(SAMPLES * 0.90)]

    index_p10 = index_sorted[int(SAMPLES * 0.10)]
    index_p90 = index_sorted[int(SAMPLES * 0.90)]

    print("\nRESULT")
    print("-" * 60)

    print(
        f"Thumb : "
        f"min={thumb_min} "
        f"max={thumb_max} "
        f"avg={thumb_mean:.1f} "
        f"median={thumb_median:.1f} "
        f"P10={thumb_p10} "
        f"P90={thumb_p90}"
    )

    print(
        f"Index : "
        f"min={index_min} "
        f"max={index_max} "
        f"avg={index_mean:.1f} "
        f"median={index_median:.1f} "
        f"P10={index_p10} "
        f"P90={index_p90}"
    )

    return {
        "name": name,
        "thumb": {
            "min": thumb_min,
            "max": thumb_max,
            "mean": thumb_mean,
            "median": thumb_median,
            "p10": thumb_p10,
            "p90": thumb_p90,
        },
        "index": {
            "min": index_min,
            "max": index_max,
            "mean": index_mean,
            "median": index_median,
            "p10": index_p10,
            "p90": index_p90,
        },
    }


def main():
    print("=" * 60)
    print("       CYNEXIS HAND SENSOR CALIBRATION")
    print("=" * 60)

    print(f"\nConnecting to {PORT}...")

    try:
        ser = serial.Serial(
            PORT,
            BAUD,
            timeout=1
        )
    except Exception as e:
        print(f"\nERROR: Could not connect to {PORT}")
        print(e)
        return

    print(f"Connected to {PORT}")
    print("Keep the receiver ESP32 connected.")
    print("Motors MUST remain disabled.")

    # Allow ESP32 serial stream to stabilize
    time.sleep(2)
    ser.reset_input_buffer()

    results = []

    try:
        for name, instruction in POSITIONS:
            result = collect_position(
                ser,
                name,
                instruction
            )

            results.append(result)

            print("\nPosition complete.")
            print("Prepare for the next position.")
            time.sleep(2)

    finally:
        ser.close()

    print("\n")
    print("=" * 60)
    print("             CALIBRATION SUMMARY")
    print("=" * 60)

    for result in results:
        print(f"\n{result['name']}")

        t = result["thumb"]
        i = result["index"]

        print(
            f"  Thumb: "
            f"{t['min']} - {t['max']} "
            f"(median {t['median']:.1f}, "
            f"P10-P90 {t['p10']}-{t['p90']})"
        )

        print(
            f"  Index: "
            f"{i['min']} - {i['max']} "
            f"(median {i['median']:.1f}, "
            f"P10-P90 {i['p10']}-{i['p90']})"
        )

    print("\n" + "=" * 60)
    print("CALIBRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()