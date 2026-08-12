"""ONNX vs PyTorch Kokoro benchmark — side by side comparison."""
import time
import sys
sys.path.insert(0, "D:/Cynexis")

CHUNKS = {
    "tiny":   "Hello there!",
    "short":  "I am CYNEXIS, a robotic platform.",
    "medium": "I can recognize gestures, respond to voice commands, and navigate autonomously.",
}
VOICE = "am_michael"

def bench_pytorch():
    """Benchmark PyTorch KPipeline."""
    import numpy as np
    from kokoro import KPipeline

    t0 = time.monotonic()
    pipe = KPipeline(lang_code="a")
    t_init = time.monotonic() - t0

    # Warm voice
    gen = pipe("Hi.", voice=VOICE, speed=1.0, split_pattern=r"\n+")
    for _ in gen:
        pass

    results = {}
    for label, text in CHUNKS.items():
        t0 = time.monotonic()
        gen = pipe(text, voice=VOICE, speed=1.0, split_pattern=r"\n+")
        chunks = []
        for gs, ps, audio in gen:
            if audio is not None:
                chunks.append(audio)
        t_synth = time.monotonic() - t0
        if chunks:
            full = np.concatenate(chunks)
            dur = len(full) / 24000
        else:
            dur = 0
        results[label] = (t_synth, dur)

    return t_init, results

def bench_onnx():
    """Benchmark ONNX Kokoro."""
    from kokoro_onnx import Kokoro

    model_path = "D:/Cynexis/AI Models/Kokoro/kokoro-v1.0.fp16-gpu.onnx"
    voices_path = "D:/Cynexis/AI Models/Kokoro/voices-v1.0.bin"

    t0 = time.monotonic()
    kokoro = Kokoro(model_path, voices_path)
    t_init = time.monotonic() - t0

    # Warm voice
    kokoro.create("Hi.", voice=VOICE, speed=1.0, lang="en-us")

    results = {}
    for label, text in CHUNKS.items():
        t0 = time.monotonic()
        samples, sr = kokoro.create(text, voice=VOICE, speed=1.0, lang="en-us")
        t_synth = time.monotonic() - t0
        dur = len(samples) / sr
        results[label] = (t_synth, dur)

    return t_init, results

if __name__ == "__main__":
    print("=" * 60)
    print("  Kokoro: PyTorch vs ONNX benchmark")
    print("=" * 60)

    print("\n[PyTorch]")
    pt_init, pt_results = bench_pytorch()
    print(f"  Init: {pt_init:.3f}s")
    for label, (synth, dur) in pt_results.items():
        rtf = dur / synth if synth > 0 else 0
        print(f"  {label:8s}: synth={synth:.3f}s  audio={dur:.2f}s  RTF={rtf:.2f}x")

    print("\n[ONNX]")
    ox_init, ox_results = bench_onnx()
    print(f"  Init: {ox_init:.3f}s")
    for label, (synth, dur) in ox_results.items():
        rtf = dur / synth if synth > 0 else 0
        print(f"  {label:8s}: synth={synth:.3f}s  audio={dur:.2f}s  RTF={rtf:.2f}x")

    print("\n[Comparison]")
    print(f"  {'Chunk':<8} {'PT synth':>10} {'ONNX synth':>12} {'Speedup':>9}")
    print("  " + "-" * 42)
    for label in CHUNKS:
        pt_s = pt_results[label][0]
        ox_s = ox_results[label][0]
        speedup = pt_s / ox_s if ox_s > 0 else 0
        print(f"  {label:<8} {pt_s:>9.3f}s {ox_s:>11.3f}s {speedup:>8.2f}x")
    print()
