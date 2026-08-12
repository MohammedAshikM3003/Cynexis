"""
CYNEXIS — Main Entry Point
Initializes all subsystems and starts the FastAPI server or CLI testing tools.

Usage:
    python main.py                      # Default server (mode from .env)
    python main.py --mock               # Force mock mode server
    python main.py --port 9000          # Custom port server
    python main.py --conversation-test  # Interactive terminal text conversational loop
    python main.py --voice-test         # Microphone + STT + AI + Kokoro TTS live test
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def run_cli_conversation_test():
    """Interactive terminal conversation testing loop."""
    from core.config import settings
    from core.logger import setup_logging
    from Database.database import db
    from AI.Actions.actions import register_all_actions
    from AI.Actions.registry import registry
    from Backend.Robot.Safety.safety import safety
    from AI.Intent.engine import intent_engine
    from AI.Memory.provider import MockMemoryProvider
    from AI.LLM.provider import MockLLMProvider
    from AI.TTS.kokoro import KokoroTTSProvider
    from AI.TTS.voice_manager import voice_manager
    from AI.pipeline import VoicePipeline

    setup_logging()
    await db.initialize()
    register_all_actions()

    print("\n" + "=" * 60)
    print("  CYNEXIS — CONVERSATIONAL PIPELINE TEST MODE")
    print("=" * 60)
    print("Loading Kokoro TTS model (this may take a few seconds on first load)...")

    if getattr(settings, "llm_provider", "mock").lower() == "ollama":
        from AI.LLM.ollama_provider import OllamaLLMProvider
        llm = OllamaLLMProvider()
    else:
        llm = MockLLMProvider()
    await llm.load()
    if getattr(settings, "stt_provider", "mock").lower() == "whisper":
        from AI.STT.whisper import WhisperSTTProvider
        stt = WhisperSTTProvider()
    else:
        from AI.STT.provider import MockSTTProvider
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

    current_voice = voice_manager.get_current_voice()
    print(f"Kokoro TTS Ready. Active Voice: {current_voice}")
    print("\nCommands:")
    print("  Type any question or command (e.g. 'say hello', 'What can you do?')")
    print("  /voice michael | /voice bella | /voice lewis  -> Switch active voice")
    print("  /stop                                         -> Interrupt active speech")
    print("  quit or exit                                  -> Exit test mode")
    print("-" * 60 + "\n")

    while True:
        try:
            user_input = input(f"[CYNEXIS ({voice_manager.get_current_voice()})]> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting conversation test.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Exiting conversation test.")
            break

        if user_input.lower().startswith("/voice"):
            parts = user_input.split()
            if len(parts) > 1:
                target_v = parts[1].strip()
                # Map short names if typed
                alias_map = {"michael": "am_michael", "bella": "af_bella", "lewis": "bm_lewis"}
                target_v = alias_map.get(target_v.lower(), target_v)
                if voice_manager.set_voice(target_v):
                    print(f"--> Voice switched to: {target_v}")
                else:
                    print(f"--> Invalid voice. Options: {voice_manager.list_available_voices()}")
            continue

        if user_input.lower() == "/stop":
            pipeline.stop_speech()
            print("--> Speech interrupted.")
            continue

        print("\n[Processing pipeline...]")
        res = await pipeline.process_text(user_input)

        intent_label = res["action"] if res["is_command"] else "CONVERSATION"
        print(f"  Recognized Text : {res['text']}")
        print(f"  Detected Intent : {intent_label} {'(Robot Action)' if res['is_command'] else '(Conversational Query)'}")
        if res["is_command"]:
            print(f"  Action Result   : {res.get('action_result', {})}")
        print(f"  Response Speech : \"{res['response']}\"")
        print(f"  Voice Profile   : {res['voice']} (Speed: {res['speed']}x)")
        print(f"  TTS Engine      : {res['tts_provider'].upper()}")
        lat = res["latencies"]
        print(f"  Latency Metrics : Total={lat['total_s']}s (Intent={lat['intent_s']}s, LLM/Action={lat['llm_or_action_s']}s, TTS={lat['tts_s']}s)")
        print("-" * 60 + "\n")

    await db.close()


async def run_cli_voice_test():
    """Live microphone recording + STT + AI + Kokoro TTS + laptop speaker test."""
    from core.config import settings
    from core.logger import setup_logging
    from Database.database import db
    from AI.Actions.actions import register_all_actions
    from AI.Actions.registry import registry
    from Backend.Robot.Safety.safety import safety
    from AI.Intent.engine import intent_engine
    from AI.Memory.provider import MockMemoryProvider
    from AI.LLM.provider import MockLLMProvider
    from AI.TTS.kokoro import KokoroTTSProvider
    from AI.TTS.voice_manager import voice_manager
    from AI.STT.microphone import LocalMicrophone, MockMicrophone
    from AI.pipeline import VoicePipeline

    setup_logging()
    await db.initialize()
    register_all_actions()

    print("\n" + "=" * 60)
    print("  CYNEXIS — LIVE VOICE PIPELINE TEST")
    print("=" * 60)

    mic = LocalMicrophone()
    if not mic.is_available():
        print("[WARNING] Local microphone hardware not detected. Using MockMicrophone.")
        mic = MockMicrophone()

    if getattr(settings, "llm_provider", "mock").lower() == "ollama":
        from AI.LLM.ollama_provider import OllamaLLMProvider
        llm = OllamaLLMProvider()
    else:
        llm = MockLLMProvider()
    await llm.load()
    if getattr(settings, "stt_provider", "mock").lower() == "whisper":
        from AI.STT.whisper import WhisperSTTProvider
        stt = WhisperSTTProvider()
    else:
        from AI.STT.provider import MockSTTProvider
        stt = MockSTTProvider()
    await stt.load()
    tts = KokoroTTSProvider()
    await tts.load()
    memory = MockMemoryProvider()

    pipeline = VoicePipeline(
        stt=stt, tts=tts, llm=llm,
        intent=intent_engine, memory=memory,
        actions=registry, safety=safety,
        microphone=mic,
    )

    print(f"Subsystems loaded. Active Voice: {voice_manager.get_current_voice()}")
    print("Preparing to record 3.0s of audio from microphone...")
    print("Press Enter when ready to speak...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        return

    print(">>> [SPEAK NOW (3 seconds)] <<<")
    res = await pipeline.process_audio(duration_s=3.0)

    print("\n" + "=" * 60)
    print("  PIPELINE EXECUTION RESULTS")
    print("=" * 60)
    intent_label = res["action"] if res["is_command"] else "CONVERSATION"
    print(f"  Recognized Text : {res['text']}")
    print(f"  Detected Intent : {intent_label}")
    print(f"  Response Speech : \"{res['response']}\"")
    print(f"  Voice Profile   : {res['voice']}")
    print(f"  TTS Engine      : {res['tts_provider'].upper()}")
    lat = res["latencies"]
    print(f"  Latency Metrics : Total={lat['total_s']}s (Mic={lat['mic_s']}s, STT={lat['stt_s']}s, Intent={lat['intent_s']}s, LLM/Action={lat['llm_or_action_s']}s, TTS={lat['tts_s']}s)")
    print("=" * 60)
    print("Audio response played through laptop speaker.")
    await db.close()


def main():
    parser = argparse.ArgumentParser(description="CYNEXIS Robot Platform")
    parser.add_argument("--mock", action="store_true", help="Force mock mode")
    parser.add_argument("--host", type=str, default=None, help="API host")
    parser.add_argument("--port", type=int, default=None, help="API port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    parser.add_argument("--conversation-test", action="store_true", help="Run interactive terminal conversation test")
    parser.add_argument("--voice-test", action="store_true", help="Run live microphone voice test")
    args = parser.parse_args()

    # CLI Test Modes
    if args.conversation_test:
        asyncio.run(run_cli_conversation_test())
        return

    if args.voice_test:
        asyncio.run(run_cli_voice_test())
        return

    # Server Mode
    from core.config import settings
    from core.logger import setup_logging

    setup_logging()

    if args.mock:
        settings.mock_mode = True
    host = args.host or settings.api_host
    port = args.port or settings.api_port

    print(f"""
+==================================================+
|                    CYNEXIS                        |
|   AI-Powered Gesture-Controlled Robot Platform    |
+==================================================+
|   Mode:  {"MOCK" if settings.mock_mode else "LIVE":41s}|
|   Host:  {host:41s}|
|   Port:  {str(port):41s}|
+==================================================+
    """)

    import uvicorn
    uvicorn.run(
        "Backend.api.server:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
