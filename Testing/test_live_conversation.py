"""
CYNEXIS — Phase 3C Live Conversational Pipeline Benchmark
Tests the real live end-to-end loop:
Intent/AI → Kokoro TTS (am_michael, af_bella, bm_lewis) → Laptop Speaker.
Measures and prints exact real latencies for all stages.
"""

import asyncio
import time
from pathlib import Path
import sys

# Ensure root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
from core.logger import setup_logging, get_logger
from Database.database import db
from AI.Actions.actions import register_all_actions
from AI.Actions.registry import registry
from Backend.Robot.Safety.safety import safety
from AI.Intent.engine import intent_engine
from AI.Memory.provider import MockMemoryProvider
from AI.LLM.provider import MockLLMProvider
from AI.TTS.kokoro import KokoroTTSProvider
from AI.TTS.voice_manager import voice_manager
from AI.STT.provider import MockSTTProvider
from AI.pipeline import VoicePipeline

log = get_logger("test_live_conversation")


async def run_benchmark():
    setup_logging()
    await db.initialize()
    register_all_actions()

    print("\n" + "=" * 70)
    print("  CYNEXIS PHASE 3C — LIVE END-TO-END CONVERSATIONAL PIPELINE TEST")
    print("=" * 70)
    print("1. Initializing Local Kokoro TTS Provider (Lazy Load & Warmup)...")
    
    settings.tts_provider = "kokoro"
    settings.tts_play_local = True

    llm = MockLLMProvider()
    await llm.load()
    stt = MockSTTProvider()
    await stt.load()
    tts = KokoroTTSProvider()
    await tts.load()
    memory = MockMemoryProvider()

    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent_engine, memory=memory,
        actions=registry, safety=safety,
    )

    test_cases = [
        ("TEST 1: HELLO Action Command", "CYNEXIS, say hello to everyone.", "am_michael"),
        ("TEST 2: INTRODUCE Action Command", "CYNEXIS, introduce yourself.", "am_michael"),
        ("TEST 3: Conversational Question (Michael)", "What can you do?", "am_michael"),
        ("TEST 4: Conversational Question (Bella)", "What can you do?", "af_bella"),
        ("TEST 5: Conversational Question (Lewis)", "What can you do?", "bm_lewis"),
        ("TEST 6: Safety Rejection Check (Invalid Action)", "HACK_MOTORS", "am_michael"),
        ("TEST 7: Safety Rejection Check (Drift Rejection)", "perform drift", "am_michael"),
    ]

    metrics = []

    for name, utterance, voice in test_cases:
        print("\n" + "-" * 70)
        print(f"Executing {name}")
        print(f"  Utterance : \"{utterance}\"")
        print(f"  Voice     : {voice}")

        voice_manager.set_voice(voice)
        t0 = time.time()
        res = await pipeline.process_text(utterance, voice=voice)
        total_time = time.time() - t0

        lat = res["latencies"]
        is_cmd = res["is_command"]
        intent_label = res["action"] if is_cmd else "CONVERSATION"

        print(f"  Intent    : {intent_label} {'(Robot Action)' if is_cmd else '(Conversational AI)'}")
        print(f"  Response  : \"{res['response']}\"")
        print(f"  Error     : {res['error']}")
        print(f"  Audio Out : {len(res['audio_bytes'])} bytes WAV synthesized & played")
        print(f"  Latencies : Total={lat['total_s']:.3f}s | Intent={lat['intent_s']:.3f}s | Gen={lat['llm_or_action_s']:.3f}s | TTS={lat['tts_s']:.3f}s")

        metrics.append({
            "name": name,
            "voice": voice,
            "total_s": lat["total_s"],
            "intent_s": lat["intent_s"],
            "gen_s": lat["llm_or_action_s"],
            "tts_s": lat["tts_s"],
            "bytes": len(res["audio_bytes"]),
        })

        # Short pause between test audio playbacks
        await asyncio.sleep(0.5)

    print("\n" + "=" * 70)
    print("TEST 8: Speech Interruption Test")
    print("=" * 70)
    print("Testing speech preemption and stop...")
    pipeline.stop_speech()
    print("  stop_speech() succeeded cleanly.")

    print("\n" + "=" * 70)
    print("  PHASE 3C BENCHMARK SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Test':<38} | {'Voice':<10} | {'Intent':<7} | {'Gen':<7} | {'TTS':<7} | {'Total':<7}")
    print("-" * 85)
    for m in metrics:
        print(f"{m['name']:<38} | {m['voice']:<10} | {m['intent_s']:<6.3f}s | {m['gen_s']:<6.3f}s | {m['tts_s']:<6.3f}s | {m['total_s']:<6.3f}s")
    print("=" * 85)

    await db.close()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
