"""
CYNEXIS — Kokoro TTS Latency Deep Benchmark
Measures every stage of the Kokoro pipeline independently.

Stages:
  1. Model initialization time
  2. Voice loading/caching behavior
  3. Text/G2P processing time  
  4. Kokoro inference time (raw audio generation)
  5. WAV conversion time
  6. Playback queue/startup time
  7. Total TTS latency

Tests multiple chunk sizes and speed values.
"""

import sys
import time
import asyncio
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path("D:/Cynexis")))

VOICES = ["am_michael", "af_bella", "bm_lewis"]
SPEEDS = [1.0, 1.2, 1.4, 1.6]
CHUNKS = {
    "tiny":   "Hello there!",                                     # ~2 words
    "short":  "I am CYNEXIS, a robotic platform.",                # ~6 words
    "medium": "I can recognize gestures, respond to voice commands, and navigate autonomously.",  # ~11 words
    "long":   "As an AI-powered robotic platform, I combine gesture control, voice interaction, and autonomous navigation to provide a seamless telepresence experience for users.",  # ~27 words
}

async def benchmark():
    from core.config import settings
    from core.logger import setup_logging
    setup_logging()

    print("=" * 70)
    print("  CYNEXIS Kokoro TTS Deep Benchmark")
    print("=" * 70)

    # ── Stage 1: Model initialization ──────────────────────────────────
    print("\n[1] Model initialization...")
    t0 = time.monotonic()
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="a")
    t_init = time.monotonic() - t0
    print(f"    Kokoro pipeline init: {t_init:.3f}s")

    # ── Stage 2: Voice loading / caching ───────────────────────────────
    print("\n[2] Voice loading (first call per voice)...")
    for voice in VOICES:
        t0 = time.monotonic()
        gen = pipeline("Test.", voice=voice, speed=1.0, split_pattern=r"\n+")
        for gs, ps, audio in gen:
            pass  # consume generator
        t_voice = time.monotonic() - t0
        print(f"    {voice}: {t_voice:.3f}s (first call)")

    print("\n    Voice re-use (cached)...")
    for voice in VOICES:
        t0 = time.monotonic()
        gen = pipeline("Test.", voice=voice, speed=1.0, split_pattern=r"\n+")
        for gs, ps, audio in gen:
            pass
        t_voice = time.monotonic() - t0
        print(f"    {voice}: {t_voice:.3f}s (cached)")

    # ── Stage 3: Chunk size benchmark ──────────────────────────────────
    print("\n[3] Chunk size vs synthesis time (am_michael, speed=1.0)...")
    print(f"    {'Size':<8} {'Words':>5} {'Chars':>5} {'Synth':>7} {'Audio':>7} {'Ratio':>6}")
    print("    " + "-" * 50)
    
    import io
    import soundfile as sf
    SAMPLE_RATE = 24000

    for label, text in CHUNKS.items():
        words = len(text.split())
        chars = len(text)
        
        t0 = time.monotonic()
        gen = pipeline(text, voice="am_michael", speed=1.0, split_pattern=r"\n+")
        audio_chunks = []
        for gs, ps, audio in gen:
            if audio is not None:
                audio_chunks.append(audio)
        t_synth = time.monotonic() - t0
        
        if audio_chunks:
            full = np.concatenate(audio_chunks)
            audio_dur = len(full) / SAMPLE_RATE
        else:
            audio_dur = 0
        
        ratio = audio_dur / t_synth if t_synth > 0 else 0
        print(f"    {label:<8} {words:>5} {chars:>5} {t_synth:>6.3f}s {audio_dur:>6.2f}s {ratio:>5.1f}x")

    # ── Stage 4: Speed benchmark ───────────────────────────────────────
    test_text = "I can recognize gestures and respond to voice commands."
    print(f"\n[4] Speed values (am_michael, text='{test_text[:40]}...')...")
    print(f"    {'Speed':>5} {'Synth':>7} {'Audio':>7} {'Quality':>10}")
    print("    " + "-" * 40)

    for speed in SPEEDS:
        t0 = time.monotonic()
        gen = pipeline(test_text, voice="am_michael", speed=speed, split_pattern=r"\n+")
        audio_chunks = []
        for gs, ps, audio in gen:
            if audio is not None:
                audio_chunks.append(audio)
        t_synth = time.monotonic() - t0

        if audio_chunks:
            full = np.concatenate(audio_chunks)
            audio_dur = len(full) / SAMPLE_RATE
        else:
            audio_dur = 0

        print(f"    {speed:>5.1f} {t_synth:>6.3f}s {audio_dur:>6.2f}s {'normal' if speed <= 1.2 else 'fast'}")

    # ── Stage 5: WAV conversion overhead ───────────────────────────────
    print(f"\n[5] WAV conversion overhead...")
    # Generate audio first
    gen = pipeline(test_text, voice="am_michael", speed=1.0, split_pattern=r"\n+")
    audio_chunks = []
    for gs, ps, audio in gen:
        if audio is not None:
            audio_chunks.append(audio)
    full_audio = np.concatenate(audio_chunks)
    
    t0 = time.monotonic()
    for _ in range(10):
        buf = io.BytesIO()
        sf.write(buf, full_audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        _ = buf.getvalue()
    t_wav = (time.monotonic() - t0) / 10
    print(f"    WAV encode (avg of 10): {t_wav*1000:.1f}ms ({len(full_audio)} samples)")

    # ── Stage 6: Breakdown of full synthesize() call ───────────────────
    print(f"\n[6] Full synthesize() breakdown (am_michael, speed=1.0)...")
    from AI.TTS.kokoro import KokoroTTSProvider
    
    provider = KokoroTTSProvider()
    await provider.load()
    
    for label, text in [("tiny", CHUNKS["tiny"]), ("medium", CHUNKS["medium"])]:
        t0 = time.monotonic()
        wav_bytes = await provider.synthesize(text, voice="am_michael", speed=1.0)
        t_total = time.monotonic() - t0
        audio_dur = len(wav_bytes) / (SAMPLE_RATE * 2 + 44) if wav_bytes else 0  # approx
        print(f"    {label}: synthesize()={t_total:.3f}s, bytes={len(wav_bytes)}")

    # ── Stage 7: Concurrent LLM + TTS test ─────────────────────────────
    print(f"\n[7] Concurrent LLM + TTS test (does TTS block LLM?)...")
    
    # Synthesize alone
    t0 = time.monotonic()
    _ = await provider.synthesize(CHUNKS["medium"], voice="am_michael", speed=1.0)
    t_tts_alone = time.monotonic() - t0
    
    print(f"    TTS alone:      {t_tts_alone:.3f}s")
    print(f"    (LLM concurrent test requires live Ollama — see server log for contention)")

    # ── Stage 8: ONNX check ────────────────────────────────────────────
    print(f"\n[8] ONNX runtime check...")
    try:
        import onnxruntime as ort
        print(f"    onnxruntime available: v{ort.__version__}")
        print(f"    Providers: {ort.get_available_providers()}")
    except ImportError:
        print(f"    onnxruntime NOT installed")
    
    try:
        from kokoro_onnx import Kokoro as KokoroONNX
        print(f"    kokoro-onnx available")
    except ImportError:
        print(f"    kokoro-onnx NOT installed")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Model init:           {t_init:.3f}s")
    print(f"  WAV encode overhead:  {t_wav*1000:.1f}ms (negligible)")
    print(f"  Tiny chunk synth:     see table above")
    print(f"  Medium chunk synth:   see table above")
    print(f"  Voice caching:        second call much faster if voices cached")
    print(f"  ONNX:                 check output above")
    print()

asyncio.run(benchmark())
