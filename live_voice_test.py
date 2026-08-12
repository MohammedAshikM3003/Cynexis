"""
CYNEXIS — Real-Time Continuous Microphone Test
Runs a continuous live voice loop directly in your terminal:
Microphone (VAD) -> Faster-Whisper STT -> Intent Engine / Ollama LLM -> Kokoro TTS -> Speaker

Usage:
    python live_voice_test.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings
from core.logger import setup_logging
from Database.database import db
from AI.Actions.actions import register_all_actions
from AI.Actions.registry import registry
from Backend.Robot.Safety.safety import safety
from AI.Intent.engine import intent_engine
from AI.Memory.provider import MockMemoryProvider
from AI.TTS.kokoro import KokoroTTSProvider
from AI.TTS.voice_manager import voice_manager
from AI.STT.microphone import LocalMicrophone
from AI.STT.whisper import WhisperSTTProvider
from AI.LLM.ollama_provider import OllamaLLMProvider
from AI.LLM.provider import MockLLMProvider
from AI.pipeline import VoicePipeline


async def main():
    setup_logging()
    await db.initialize()
    register_all_actions()

    print("\n" + "=" * 65)
    print("  CYNEXIS — REAL-TIME CONTINUOUS MICROPHONE VOICE LAB")
    print("=" * 65)

    mic = LocalMicrophone()
    if not mic.is_available():
        print("[ERROR] Physical microphone hardware not detected.")
        return

    print("Loading Faster-Whisper STT model...")
    stt = WhisperSTTProvider()
    await stt.load()

    print("Loading Ollama LLM...")
    if getattr(settings, "llm_provider", "mock").lower() == "ollama":
        llm = OllamaLLMProvider()
    else:
        llm = MockLLMProvider()
    await llm.load()

    print("Loading Kokoro TTS...")
    tts = KokoroTTSProvider()
    await tts.load()

    memory = MockMemoryProvider()

    pipeline = VoicePipeline(
        stt=stt,
        tts=tts,
        llm=llm,
        intent=intent_engine,
        memory=memory,
        actions=registry,
        safety=safety,
        microphone=mic,
    )

    print("\n" + "-" * 65)
    print(f"System Ready! Active Voice: {voice_manager.get_current_voice()}")
    print("Instructions:")
    print("  - Press [Enter] to start speaking (or Ctrl+C to exit).")
    print("  - Speak your command or question clearly into your microphone.")
    print("  - Recording automatically stops when you stop speaking.")
    print("-" * 65 + "\n")

    while True:
        try:
            print("\n[READY] Press [Enter] to speak (or 'q' to quit)...", end="", flush=True)
            user_key = await asyncio.to_thread(input)
            if user_key.strip().lower() in ("q", "quit", "exit"):
                break

            print("\n🎤 >>> [LISTENING — Speak into your mic now...] <<<")
            t0 = time.time()
            res = await pipeline.process_audio(duration_s=4.0, play_local=True)

            print("\n" + "=" * 55)
            recognized = res.get("text", "").strip()
            if not recognized:
                print("  [No speech detected]")
                continue

            intent_label = res["action"] if res.get("is_command") else "CONVERSATIONAL_AI"
            print(f"  🗣️  You Said       : \"{recognized}\"")
            print(f"  🧠 Intent / Type  : {intent_label}")
            if res.get("is_command"):
                print(f"  ⚙️  Action Result  : {res.get('action_result', {})}")
            print(f"  🤖 CYNEXIS Reply  : \"{res.get('response', '')}\"")

            lat = res.get("latencies", {})
            print(f"  ⚡ Latencies      : STT: {lat.get('stt_s', 0)}s | Intent: {lat.get('intent_s', 0)}s | LLM: {lat.get('llm_or_action_s', 0)}s | TTS: {lat.get('tts_s', 0)}s | Total: {lat.get('total_s', 0)}s")
            print("=" * 55)
            print("🔊 Response played on speaker.")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting live voice test.")
            break
        except Exception as e:
            print(f"\n[Error during loop]: {e}")

    await db.close()
    print("\nCYNEXIS voice loop terminated.")


if __name__ == "__main__":
    asyncio.run(main())
