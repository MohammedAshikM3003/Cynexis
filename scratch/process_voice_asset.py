import soundfile as sf
import numpy as np
import os

# 1. Load generated SAPI5 WAV file
input_path = r"d:\Cynexis\scratch\cynexis_online_sapi.wav"
data, orig_sr = sf.read(input_path)

# Convert to mono if stereo
if len(data.shape) > 1:
    data = np.mean(data, axis=1)

# Trim trailing/leading silence (samples below 0.01 threshold)
threshold = 0.01
nonzero_indices = np.where(np.abs(data) > threshold)[0]
if len(nonzero_indices) > 0:
    start_idx = max(0, nonzero_indices[0] - int(orig_sr * 0.05)) # 50ms pad before
    end_idx = min(len(data), nonzero_indices[-1] + int(orig_sr * 0.1)) # 100ms pad after
    data = data[start_idx:end_idx]

# 2. Resample to 48000 Hz target rate using numpy linear interpolation
target_sr = 48000
if orig_sr != target_sr:
    orig_length = len(data)
    target_length = int(orig_length * (target_sr / orig_sr))
    orig_indices = np.linspace(0, orig_length - 1, orig_length)
    target_indices = np.linspace(0, orig_length - 1, target_length)
    data = np.interp(target_indices, orig_indices, data)

# 3. Peak normalization to 75% max amplitude (-2.5 dB) for zero distortion
peak = np.max(np.abs(data))
if peak > 0:
    data = (data / peak) * 0.75

# 4. Apply 10ms smooth fade-in and 20ms smooth fade-out to prevent pops
fade_in_len = int(target_sr * 0.01)
fade_out_len = int(target_sr * 0.02)

if len(data) > fade_in_len + fade_out_len:
    fade_in = np.linspace(0.0, 1.0, fade_in_len)
    fade_out = np.linspace(1.0, 0.0, fade_out_len)
    data[:fade_in_len] *= fade_in
    data[-fade_out_len:] *= fade_out

# 5. Convert to int16 PCM format
pcm16 = np.int16(data * 32767.0)

# Calculate statistics
sample_count = len(pcm16)
duration_sec = sample_count / target_sr
min_val = int(np.min(pcm16))
max_val = int(np.max(pcm16))
is_clipping = (min_val <= -32768) or (max_val >= 32767)

# 6. Generate C/C++ Header file
header_path = r"d:\Cynexis\Firmware\robot_esp32\cynexis_voice_sample.h"

with open(header_path, "w") as f:
    f.write("/*\n")
    f.write(" * CYNEXIS — Embedded Voice PCM Asset Header\n")
    f.write(" * Phrase     : \"CYNEXIS online.\"\n")
    f.write(f" * Format     : 48000 Hz, 16-bit Signed PCM, Mono\n")
    f.write(f" * Duration   : {duration_sec:.2f} seconds ({sample_count} samples)\n")
    f.write(f" * Min/Max    : [{min_val}, {max_val}] (Peak 75% / No Clipping)\n")
    f.write(" */\n\n")
    f.write("#ifndef CYNEXIS_VOICE_SAMPLE_H\n")
    f.write("#define CYNEXIS_VOICE_SAMPLE_H\n\n")
    f.write("#include <Arduino.h>\n")
    f.write("#include <pgmspace.h>\n\n")
    f.write(f"const size_t VOICE_SAMPLE_MONO_SAMPLES = {sample_count};\n")
    f.write(f"const float VOICE_SAMPLE_DURATION_SEC = {duration_sec:.2f}f;\n\n")
    f.write("const int16_t voice_sample_mono[] PROGMEM = {\n")

    # Format 12 integers per line for clean C array layout
    for i in range(0, sample_count, 12):
        chunk = pcm16[i:i+12]
        line_str = "    " + ", ".join(f"{x:6d}" for x in chunk)
        if i + 12 < sample_count:
            line_str += ","
        f.write(line_str + "\n")

    f.write("};\n\n")
    f.write("#endif // CYNEXIS_VOICE_SAMPLE_H\n")

file_size_bytes = os.path.getsize(header_path)

print("=== VOICE ASSET VERIFICATION REPORT ===")
print(f"Header File Path: {header_path}")
print(f"Phrase           : \"CYNEXIS online.\"")
print(f"Sample Rate      : {target_sr} Hz")
print(f"Bit Depth        : 16-bit Signed PCM")
print(f"Channels         : 1 (Mono)")
print(f"Sample Count     : {sample_count}")
print(f"Duration         : {duration_sec:.2f} seconds")
print(f"Minimum Value    : {min_val}")
print(f"Maximum Value    : {max_val}")
print(f"Clipping Present : {'YES' if is_clipping else 'NO'}")
print(f"Header File Size : {file_size_bytes} bytes ({file_size_bytes / 1024:.2f} KB)")
print("=======================================")
