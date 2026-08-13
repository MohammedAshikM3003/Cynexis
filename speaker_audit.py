"""
CYNEXIS — Final Speaker-Only TTFA Audit Script
Traces request-level stages, runs direct audio and TTS benchmarks.
"""

import sys
import os
import time
import asyncio
import io
import numpy as np
import soundfile as sf
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force real modes and providers
from core.config import settings
settings.mock_mode = False
settings.llm_provider = "ollama"
settings.stt_provider = "whisper"
settings.tts_provider = "kokoro"
settings.tts_play_local = True
settings.tts_speed = 1.0

from Database.database import db
from AI.Actions.actions import register_all_actions
from AI.Actions.registry import registry
from Backend.Robot.Safety.safety import safety
from AI.Intent.engine import intent_engine
from AI.Memory.provider import MockMemoryProvider
from AI.LLM.ollama_provider import OllamaLLMProvider
from AI.TTS.kokoro import KokoroTTSProvider
from AI.STT.whisper import WhisperSTTProvider
from AI.STT.microphone import MockMicrophone
from AI.pipeline import VoicePipeline

# Global dictionary to track timestamps of currently executing query
events = {}
current_query = ""

# Track chunks
chunks_info = []

def record_event(name):
    if name not in events:
        events[name] = time.time()

async def run_special_tests(pipeline):
    print("\n" + "=" * 60)
    print("SPECIAL TEST 1: DIRECT AUDIO-OUTPUT BENCHMARK")
    print("=" * 60)
    # Generate 1 second of 24kHz sine wave (beep) to make a real but short WAV
    sr = 24000
    t = np.linspace(0, 1.0, sr, False)
    # 440Hz sine wave
    sine = np.sin(440 * 2 * np.pi * t) * 0.5
    
    # Write to WAV bytes in memory
    wav_io = io.BytesIO()
    sf.write(wav_io, sine, sr, format="WAV", subtype="PCM_16")
    wav_bytes = wav_io.getvalue()

    print(f"Generated WAV buffer size: {len(wav_bytes)} bytes")
    
    t_queue_put = time.time()
    t_play_start = None
    t_play_active = None
    t_play_end = None

    # Patch playback sync methods for this direct test
    original_play_sync = pipeline.tts.audio_output._play_sync
    def patched_play_sync(audio_data, sample_rate):
        nonlocal t_play_start, t_play_active, t_play_end
        t_play_start = time.time()
        import sounddevice as sd
        data, fs = sf.read(io.BytesIO(audio_data), dtype="float32")
        t_play_active = time.time()
        sd.play(data, samplerate=fs, device=pipeline.tts.audio_output.device)
        sd.wait()
        t_play_end = time.time()
        return True

    pipeline.tts.audio_output._play_sync = patched_play_sync

    print("Sending directly to LocalAudioOutput...")
    await pipeline.tts.audio_output.play(wav_bytes, sample_rate=sr)

    print(f"AUDIO_QUEUE_PUT:     {t_queue_put:.4f} (relative: 0.000s)")
    if t_play_start:
        print(f"PLAY_SYNC_START:     {t_play_start:.4f} (relative: {t_play_start - t_queue_put:.4f}s)")
    if t_play_active:
        print(f"PLAY_SYNC_ACTIVE:    {t_play_active:.4f} (relative: {t_play_active - t_queue_put:.4f}s) -> PortAudio start delay: {t_play_active - t_play_start:.4f}s")
    if t_play_end:
        print(f"PLAY_SYNC_END:       {t_play_end:.4f} (relative: {t_play_end - t_queue_put:.4f}s) -> Playback duration: {t_play_end - t_play_active:.4f}s")
        print(f"Total Dispatch Latency (Put -> Active): {t_play_active - t_queue_put:.4f}s")

    # Restore play_sync
    pipeline.tts.audio_output._play_sync = original_play_sync

    print("\n" + "=" * 60)
    print("SPECIAL TEST 2: KOKORO SYNTHESIS BENCHMARK (Warm Model)")
    print("=" * 60)
    test_phrases = [
        "Hello.",
        "What is the answer?",
        "What is today's date?",
        "What is YouTube?"
    ]
    for phrase in test_phrases:
        t0 = time.time()
        wav = await pipeline.tts.synthesize(phrase, voice="am_michael", speed=1.0)
        t_end = time.time()
        duration_s = len(wav) / (2 * 24000) # WAV PCM_16 bytes duration
        print(f"Phrase: '{phrase}'")
        print(f"  Synthesis duration: {t_end - t0:.4f}s")
        print(f"  Audio duration:     {duration_s:.4f}s")
        print(f"  Real-time Factor:   {(t_end - t0) / duration_s:.2f}x")

async def main():
    print("Initializing components...")
    await db.initialize()
    register_all_actions()

    llm = OllamaLLMProvider()
    await llm.load()

    tts = KokoroTTSProvider()
    await tts.load()

    stt = WhisperSTTProvider()
    await stt.load()

    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent_engine, memory=MockMemoryProvider(),
        actions=registry, safety=safety,
        microphone=MockMicrophone()
    )

    # ── Prewarming ──
    print("\nPrewarming LLM, TTS, STT to avoid initial loading penalty...")
    async for _ in pipeline.llm.stream("Warmup."):
         pass
    warmup_audio = await pipeline.tts.synthesize("Warmup.", voice="am_michael", speed=1.0)
    await pipeline.stt.transcribe(warmup_audio)
    await pipeline.playback_queue.join()
    print("Prewarming complete.")

    # ── Special Tests ──
    await run_special_tests(pipeline)

    # ── Monkey-Patching for detailed query tracing ──
    original_transcribe = pipeline.stt.transcribe
    async def patched_transcribe(audio_data):
        record_event("STT_START")
        res = await original_transcribe(audio_data)
        record_event("STT_END")
        return res
    pipeline.stt.transcribe = patched_transcribe

    original_route_and_resolve = pipeline.router.route_and_resolve
    async def patched_route_and_resolve(text):
        record_event("ROUTER_START")
        res = await original_route_and_resolve(text)
        record_event("ROUTER_END")
        events["ROUTE_SELECTED"] = res.route.value
        return res
    pipeline.router.route_and_resolve = patched_route_and_resolve

    from AI.Router.tools.calculator_tool import SafeCalculatorTool
    original_calc_process = SafeCalculatorTool.process
    def patched_calc_process(query):
        record_event("TOOL_START")
        res = original_calc_process(query)
        record_event("TOOL_END")
        return res
    SafeCalculatorTool.process = patched_calc_process

    original_llm_stream = pipeline.llm.stream
    async def patched_llm_stream(prompt, context=""):
        record_event("LLM_START")
        first_token_recorded = False
        async for token in original_llm_stream(prompt, context):
            if not first_token_recorded:
                record_event("LLM_FIRST_TOKEN")
                first_token_recorded = True
            yield token
        record_event("LLM_END")
    pipeline.llm.stream = patched_llm_stream

    original_chunker = pipeline._sentence_chunker
    async def patched_chunker(token_stream, tracker=None):
        first_chunk_recorded = False
        async for chunk in original_chunker(token_stream, tracker):
            if not first_chunk_recorded:
                record_event("CHUNKER_FIRST_CHUNK")
                first_chunk_recorded = True
            yield chunk
    pipeline._sentence_chunker = patched_chunker

    original_synthesize = pipeline.tts.synthesize
    async def patched_synthesize(text, voice=None, speed=1.0):
        t_start = time.time()
        record_event("TTS_START")
        res = await original_synthesize(text, voice, speed)
        record_event("TTS_END")
        t_end = time.time()
        
        # Audio length (WAV header has 44 bytes, 2 bytes per sample at 24kHz)
        audio_dur = (len(res) - 44) / (2 * 24000) if res else 0.0
        chunks_info.append({
            "text": text,
            "char_count": len(text),
            "synthesis_duration": t_end - t_start,
            "audio_duration": audio_dur
        })
        return res
    pipeline.tts.synthesize = patched_synthesize

    original_put = pipeline.playback_queue.put
    async def patched_put(item):
        record_event("AUDIO_QUEUE_PUT")
        await original_put(item)
    pipeline.playback_queue.put = patched_put

    original_play = pipeline.tts.audio_output.play
    async def patched_play(audio_data, sample_rate=24000):
        record_event("AUDIO_PLAYBACK_START")
        res = await original_play(audio_data, sample_rate)
        return res
    pipeline.tts.audio_output.play = patched_play

    # ── Execute Queries ──
    queries = [
        "What is 25 plus 37?",
        "What is today's date?",
        "Hello",
        "What is YouTube?",
        "What is the weather today?",
    ]

    for q in queries:
        events.clear()
        chunks_info.clear()
        print("\n" + "=" * 60)
        print(f"Executing Query: '{q}'")
        print("=" * 60)

        # Synthesize dummy spoken query for STT transcription
        query_wav = await pipeline.tts.synthesize(q)
        
        # Start audit timeline
        events["REQUEST_START"] = time.time()
        
        result = await pipeline.process_audio(query_wav, play_local=True)
        await pipeline.playback_queue.join()
        record_event("REQUEST_END")

        # Print detailed timeline trace
        t_start = events.get("REQUEST_START")
        def r(key):
            if key in events:
                return f"{events[key] - t_start:.4f}s"
            return "N/A"

        print(f"\nTimeline for '{q}':")
        print(f"  REQUEST_START:        {t_start:.4f} (relative: 0.0000s)")
        print(f"  STT_START:            {r('STT_START')}")
        print(f"  STT_END:              {r('STT_END')}")
        print(f"  ROUTER_START:         {r('ROUTER_START')}")
        print(f"  ROUTER_END:           {r('ROUTER_END')} (route: {events.get('ROUTE_SELECTED', 'UNKNOWN')})")
        
        if "TOOL_START" in events:
            print(f"  TOOL_START:           {r('TOOL_START')}")
            print(f"  TOOL_END:             {r('TOOL_END')}")
            
        if "LLM_START" in events:
            print(f"  LLM_START:            {r('LLM_START')}")
            print(f"  LLM_FIRST_TOKEN:      {r('LLM_FIRST_TOKEN')}")
            print(f"  LLM_END:              {r('LLM_END')}")
            
        if "CHUNKER_FIRST_CHUNK" in events:
            print(f"  CHUNKER_FIRST_CHUNK:  {r('CHUNKER_FIRST_CHUNK')}")
            
        print(f"  TTS_START:            {r('TTS_START')}")
        print(f"  TTS_END:              {r('TTS_END')}")
        print(f"  AUDIO_QUEUE_PUT:      {r('AUDIO_QUEUE_PUT')}")
        print(f"  AUDIO_PLAYBACK_START: {r('AUDIO_PLAYBACK_START')}")
        print(f"  REQUEST_END:          {r('REQUEST_END')}")
        
        # Calculate TTFA
        if "AUDIO_PLAYBACK_START" in events and t_start:
            ttfa = events["AUDIO_PLAYBACK_START"] - t_start
            print(f"\n  Calculated TTFA (Speaker Start - Request Start): {ttfa:.4f}s")

        print("\n  Chunks Synthesized:")
        for idx, chunk in enumerate(chunks_info):
            print(f"    Chunk {idx}:")
            print(f"      Text: '{chunk['text']}'")
            print(f"      Chars: {chunk['char_count']}")
            print(f"      TTS Synthesis duration: {chunk['synthesis_duration']:.4f}s")
            print(f"      Audio duration:         {chunk['audio_duration']:.4f}s")

if __name__ == "__main__":
    asyncio.run(main())
