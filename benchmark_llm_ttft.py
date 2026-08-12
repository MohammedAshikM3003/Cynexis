"""
CYNEXIS Phase 6H — LLM TTFT Diagnostic Benchmark
Measures isolated TTFT across:
  A: Ollama Standalone (4, 6, 8 threads | 512 vs 1024 ctx)
  B: LLM inside pipeline immediately after Whisper STT
  C: LLM under concurrent Kokoro TTS activity
  D: LLM with 5-turn Conversation History
  E: LLM with Minimal Context / System Prompt
"""

import sys
import os
import time
import asyncio
import numpy as np
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
settings.mock_mode = False
settings.llm_provider = "ollama"
settings.stt_provider = "whisper"
settings.tts_provider = "kokoro"
settings.tts_play_local = False
settings.stt_whisper_model = "base.en"
settings.stt_whisper_cpu_threads = 4
settings.stt_whisper_beam_size = 1
settings.tts_onnx_intra_threads = 6

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
from AI.personality import get_system_prompt

TEST_QUERY = "What is CYNEXIS?"
NUM_RUNS = 5

async def measure_standalone_ollama(llm, threads=6, num_ctx=1024, system_prompt=None, history=None):
    """Directly measure TTFT using OllamaLLMProvider with specific options."""
    settings.ollama_num_thread = threads
    settings.ollama_num_ctx = num_ctx
    
    prompt = TEST_QUERY
    context = ""
    if system_prompt:
        context += f"System: {system_prompt}\n"
    if history:
        for h in history:
            context += f"{h['role']}: {h['content']}\n"
            
    ttfts = []
    for _ in range(NUM_RUNS):
        t0 = time.time()
        ttft = None
        async for token in llm.stream(prompt, context=context):
            if ttft is None and token.strip():
                ttft = time.time() - t0
                break
        if ttft:
            ttfts.append(ttft)
        await asyncio.sleep(0.05)
    return float(np.mean(ttfts)), float(np.min(ttfts)), float(np.max(ttfts))

async def run_diagnostics():
    print("=" * 80)
    print("  CYNEXIS Phase 6H — LLM TTFT Diagnostic Matrix (5 runs each)")
    print("=" * 80)

    await db.initialize()
    register_all_actions()

    # Load components
    print("\n[1] Initializing and Prewarming Pipeline Components...")
    llm = OllamaLLMProvider()
    await llm.load()
    
    tts = KokoroTTSProvider()
    await tts.load()
    
    stt = WhisperSTTProvider(model_size="base.en", cpu_threads=4)
    await stt.load()

    # Prewarm LLM
    async for _ in llm.stream("Warmup."):
        pass

    # Pre-synthesize query audio for STT tests
    query_audio = await tts.synthesize(TEST_QUERY, voice="am_michael", speed=1.0)

    # -------------------------------------------------------------------------
    # Test A: Standalone Ollama Thread & Context Parameter Sweep
    # -------------------------------------------------------------------------
    print("\n[Test A] Standalone Ollama TTFT (No STT/TTS overhead):")
    for threads in [4, 6, 8]:
        for ctx in [512, 1024]:
            avg_t, min_t, max_t = await measure_standalone_ollama(llm, threads=threads, num_ctx=ctx)
            print(f"  Threads: {threads} | Ctx: {ctx:>4} -> TTFT: {avg_t:.3f}s (Min: {min_t:.3f}s, Max: {max_t:.3f}s)")

    # -------------------------------------------------------------------------
    # Test B: LLM inside Pipeline Immediately After STT
    # -------------------------------------------------------------------------
    print("\n[Test B] LLM Inside Pipeline Immediately After Whisper STT:")
    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent_engine, memory=MockMemoryProvider(),
        actions=registry, safety=safety,
        microphone=MockMicrophone()
    )

    b_ttfts = []
    for i in range(NUM_RUNS):
        pipeline.stop_speech()
        res = await pipeline.process_audio(query_audio, voice="am_michael", play_local=False)
        ttft = res.get("latencies", {}).get("llm_ttft", 0.0)
        if ttft > 0.01:
            b_ttfts.append(ttft)
    print(f"  Post-STT Pipeline TTFT -> Avg: {np.mean(b_ttfts):.3f}s (Min: {np.min(b_ttfts):.3f}s, Max: {np.max(b_ttfts):.3f}s)")

    # -------------------------------------------------------------------------
    # Test C: LLM Under Concurrent Kokoro TTS Activity
    # -------------------------------------------------------------------------
    print("\n[Test C] LLM TTFT Under Concurrent Kokoro TTS Activity:")
    c_ttfts = []
    for _ in range(NUM_RUNS):
        # Fire background TTS loop
        bg_synth_task = asyncio.create_task(tts.synthesize("Kokoro background synthesis activity benchmark.", voice="am_michael", speed=1.0))
        await asyncio.sleep(0.01) # let TTS start
        
        t0 = time.time()
        ttft = None
        async for token in llm.stream(TEST_QUERY):
            if ttft is None and token.strip():
                ttft = time.time() - t0
                break
        await bg_synth_task
        if ttft:
            c_ttfts.append(ttft)
    print(f"  Concurrent-TTS TTFT    -> Avg: {np.mean(c_ttfts):.3f}s (Min: {np.min(c_ttfts):.3f}s, Max: {np.max(c_ttfts):.3f}s)")

    # -------------------------------------------------------------------------
    # Test D: LLM With 5-Turn Conversation History
    # -------------------------------------------------------------------------
    print("\n[Test D] LLM TTFT With 5-Turn Conversation History:")
    history_5 = [
        {"role": "user", "content": "Hello CYNEXIS."},
        {"role": "assistant", "content": "Hello! How can I help you today?"},
        {"role": "user", "content": "Where are you located?"},
        {"role": "assistant", "content": "I am operating in the robotics lab."},
        {"role": "user", "content": "What sensors do you have?"},
    ]
    avg_d, min_d, max_d = await measure_standalone_ollama(llm, threads=6, num_ctx=1024, history=history_5)
    print(f"  5-Turn History TTFT    -> Avg: {avg_d:.3f}s (Min: {min_d:.3f}s, Max: {max_d:.3f}s)")

    # -------------------------------------------------------------------------
    # Test E: LLM With Minimal Context (Short 1-Sentence System Prompt)
    # -------------------------------------------------------------------------
    print("\n[Test E] LLM TTFT With Minimal System Prompt:")
    minimal_sys = "You are CYNEXIS, a robot. Be brief (1 sentence)."
    avg_e, min_e, max_e = await measure_standalone_ollama(llm, threads=6, num_ctx=1024, system_prompt=minimal_sys)
    print(f"  Minimal Prompt TTFT    -> Avg: {avg_e:.3f}s (Min: {min_e:.3f}s, Max: {max_e:.3f}s)")

    print("\n" + "=" * 80)
    print("  DIAGNOSTIC SUMMARY & BOTTLENECK ANALYSIS")
    print("=" * 80)
    print(f"  A (Standalone Base 6T/1024Ctx): {avg_t:.3f}s")
    print(f"  B (Pipeline Post-STT)        : {np.mean(b_ttfts):.3f}s")
    print(f"  C (Concurrent TTS Active)    : {np.mean(c_ttfts):.3f}s")
    print(f"  D (5-Turn History Context)   : {avg_d:.3f}s")
    print(f"  E (Minimal System Prompt)    : {avg_e:.3f}s")
    print("=" * 80)

    await db.close()

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
