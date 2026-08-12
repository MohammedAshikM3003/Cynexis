"""
CYNEXIS Phase 6F — Faster-Whisper Real-Time STT Optimization Benchmark
Evaluates base.en vs tiny.en at 4, 6, and 8 threads with 10 iterations per test phrase.
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
settings.tts_play_local = False  # Fast evaluation without blocking on audio device
settings.ollama_num_thread = 6
settings.ollama_num_ctx = 1024
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

# 7 Required Benchmark Phrases with exact uppercase ActionName enum values
TEST_PHRASES = [
    {"text": "move forward", "type": "command", "expected_action": "FORWARD"},
    {"text": "move backward", "type": "command", "expected_action": "BACKWARD"},
    {"text": "turn left", "type": "command", "expected_action": "LEFT"},
    {"text": "turn right", "type": "command", "expected_action": "RIGHT"},
    {"text": "stop", "type": "command", "expected_action": "STOP"},
    {"text": "what is CYNEXIS?", "type": "conversation", "expected_action": None},
    {"text": "what can you do?", "type": "conversation", "expected_action": None},
]

MODELS = ["base.en", "tiny.en"]
THREAD_CONFIGS = [4, 6, 8]
NUM_RUNS = 10

async def generate_phrase_audio_clips(tts):
    """Pre-synthesize audio clips for all 7 test phrases to ensure consistent acoustic input."""
    print("\n[1] Pre-synthesizing acoustic audio clips for all 7 test phrases...")
    clips = {}
    for p in TEST_PHRASES:
        phrase = p["text"]
        print(f"  Synthesizing: '{phrase}'... ", end="", flush=True)
        audio = await tts.synthesize(phrase, voice="am_michael", speed=1.0)
        clips[phrase] = audio
        print(f"Done ({len(audio)} bytes).")
    return clips

async def run_stt_benchmark():
    print("=" * 80)
    print("  CYNEXIS Phase 6F — Faster-Whisper STT Benchmark Matrix")
    print(f"  Models: {MODELS} | Threads: {THREAD_CONFIGS} | Runs: {NUM_RUNS}x per phrase")
    print("=" * 80)

    await db.initialize()
    register_all_actions()

    # Load TTS for audio clip generation
    tts = KokoroTTSProvider()
    await tts.load()
    audio_clips = await generate_phrase_audio_clips(tts)

    # Load LLM for end-to-end TTFA measurement
    llm = OllamaLLMProvider()
    await llm.load()
    # Warm up LLM
    async for _ in llm.stream("Hi"):
        pass

    results_table = []

    for model_name in MODELS:
        for threads in THREAD_CONFIGS:
            print(f"\n" + "-" * 80)
            print(f"  Evaluating Model: '{model_name}' | CPU Threads: {threads}")
            print("-" * 80)

            settings.stt_whisper_model = model_name
            settings.stt_whisper_cpu_threads = threads
            settings.stt_whisper_beam_size = 1

            stt = WhisperSTTProvider(model_size=model_name, cpu_threads=threads)
            loaded = await stt.load()
            if not loaded:
                print(f"  [ERROR] Failed to load {model_name} with {threads} threads!")
                continue

            pipeline = VoicePipeline(
                stt=stt, tts=tts, llm=llm,
                intent=intent_engine, memory=MockMemoryProvider(),
                actions=registry, safety=safety,
                microphone=MockMicrophone()
            )

            all_stt_latencies = []
            all_ttfa_latencies = []
            exact_transcripts = 0
            correct_intents = 0
            total_evals = 0

            for p in TEST_PHRASES:
                phrase = p["text"]
                expected_act = p["expected_action"]
                is_cmd = p["type"] == "command"
                audio_bytes = audio_clips[phrase]

                phrase_stt_lats = []
                phrase_ttfa_lats = []
                phrase_exact = 0
                phrase_intent = 0

                print(f"  Phrase: '{phrase:<20}' -> ", end="", flush=True)

                for r in range(NUM_RUNS):
                    pipeline.stop_speech()
                    res = await pipeline.process_audio(audio_bytes, voice="am_michael", play_local=False)
                    
                    transcribed = (res.get("text") or "").strip().lower()
                    clean_orig = phrase.lower().strip("?.!,")
                    clean_trans = transcribed.strip("?.!,").replace("synexis", "cynexis")

                    # Check exact transcription match (or normalized punctuation match)
                    is_exact = clean_orig == clean_trans or clean_orig in clean_trans
                    if is_exact:
                        exact_transcripts += 1
                        phrase_exact += 1

                    # Check intent/action match
                    act = (res.get("action") or "").upper()
                    if is_cmd:
                        is_intent_correct = act == expected_act.upper()
                    else:
                        is_intent_correct = not res.get("is_command")
                    
                    if is_intent_correct:
                        correct_intents += 1
                        phrase_intent += 1

                    lat = res.get("latencies", {})
                    stt_lat = lat.get("stt_latency", 0.0)
                    ttfa_lat = lat.get("actual_ttfa", 0.0)
                    
                    phrase_stt_lats.append(stt_lat)
                    phrase_ttfa_lats.append(ttfa_lat)
                    all_stt_latencies.append(stt_lat)
                    all_ttfa_latencies.append(ttfa_lat)
                    total_evals += 1

                avg_p_stt = np.mean(phrase_stt_lats)
                print(f"STT: {avg_p_stt:.3f}s | Transcript: {phrase_exact}/{NUM_RUNS} | Intent: {phrase_intent}/{NUM_RUNS}")

            stt_arr = np.array(all_stt_latencies)
            ttfa_arr = np.array(all_ttfa_latencies)

            acc_pct = (exact_transcripts / total_evals) * 100.0
            cmd_acc_pct = (correct_intents / total_evals) * 100.0

            results_table.append({
                "model": model_name,
                "threads": threads,
                "stt_avg": float(np.mean(stt_arr)),
                "stt_min": float(np.min(stt_arr)),
                "stt_max": float(np.max(stt_arr)),
                "accuracy": acc_pct,
                "cmd_accuracy": cmd_acc_pct,
                "ttfa_avg": float(np.mean(ttfa_arr)),
                "ttfa_min": float(np.min(ttfa_arr)),
                "ttfa_max": float(np.max(ttfa_arr)),
            })

            pipeline.stop_speech()
            if hasattr(pipeline, "playback_task") and pipeline.playback_task and not pipeline.playback_task.done():
                pipeline.playback_task.cancel()
            await stt.unload()

    # Print Final Comparison Table
    print("\n" + "=" * 100)
    print("  FINAL MODEL & THREAD COMPARISON MATRIX (Across 10 runs per test phrase)")
    print("=" * 100)
    print("| Model | Threads | STT Avg | STT Min | STT Max | Accuracy | Cmd Acc | Actual TTFA Avg | Actual TTFA Min | Actual TTFA Max |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results_table:
        print(
            f"| {r['model']:<7} | {r['threads']:<7} | "
            f"{r['stt_avg']:>6.3f}s | {r['stt_min']:>6.3f}s | {r['stt_max']:>6.3f}s | "
            f"{r['accuracy']:>7.1f}% | {r['cmd_accuracy']:>6.1f}% | "
            f"{r['ttfa_avg']:>14.3f}s | {r['ttfa_min']:>14.3f}s | {r['ttfa_max']:>14.3f}s |"
        )
    print("=" * 100)

    # Determine winning configuration based on 100% command accuracy and lowest STT latency
    best_config = min(results_table, key=lambda x: (100 - x["cmd_accuracy"], x["stt_avg"]))
    print(f"\n>> Optimal STT Configuration: Model='{best_config['model']}', Threads={best_config['threads']} "
          f"(STT Avg={best_config['stt_avg']:.3f}s, Command Accuracy={best_config['cmd_accuracy']:.1f}%)")

    await db.close()

if __name__ == "__main__":
    asyncio.run(run_stt_benchmark())
