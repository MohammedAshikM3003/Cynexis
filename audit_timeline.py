import sys
import os
import time
import asyncio
import uuid
import re
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

# Global trace dictionary for current request
events = {}

def rel(key, t_start):
    if key in events:
        return f"{events[key] - t_start:.3f}"
    return "N/A"

def total(key_start, key_end):
    if key_start in events and key_end in events:
        return f"{events[key_end] - events[key_start]:.3f}"
    return "N/A"

def print_timeline(request_id):
    t_start = events.get("REQUEST_START")
    if not t_start:
        print("Error: REQUEST_START not recorded.")
        return

    print(f"\n[CYNEXIS REQUEST {request_id}]")
    print(f"\nSTT:")
    print(f"  start = {rel('STT_START', t_start)}")
    print(f"  end   = {rel('STT_END', t_start)}")
    print(f"  total = {total('STT_START', 'STT_END')}")

    print(f"\nROUTER:")
    print(f"  start = {rel('ROUTER_START', t_start)}")
    print(f"  end   = {rel('ROUTER_END', t_start)}")
    print(f"  total = {total('ROUTER_START', 'ROUTER_END')}")
    print(f"  route = {events.get('ROUTE_SELECTED', 'UNKNOWN')}")

    if "TOOL_START" in events:
        print(f"\nTOOL:")
        print(f"  start = {rel('TOOL_START', t_start)}")
        print(f"  end   = {rel('TOOL_END', t_start)}")
        print(f"  total = {total('TOOL_START', 'TOOL_END')}")

    if "SEARCH_START" in events:
        print(f"\nSEARCH:")
        print(f"  start = {rel('SEARCH_START', t_start)}")
        print(f"  end   = {rel('SEARCH_END', t_start)}")
        print(f"  total = {total('SEARCH_START', 'SEARCH_END')}")

    if "LLM_START" in events:
        print(f"\nLLM:")
        print(f"  start       = {rel('LLM_START', t_start)}")
        print(f"  first_token = {rel('LLM_FIRST_TOKEN', t_start)}")
        print(f"  end         = {rel('LLM_END', t_start)}")
        print(f"  TTFT        = {total('LLM_START', 'LLM_FIRST_TOKEN')}")
        print(f"  total       = {total('LLM_START', 'LLM_END')}")

    if "CHUNKER_FIRST_CHUNK" in events:
        print(f"\nCHUNKER:")
        print(f"  first_chunk = {rel('CHUNKER_FIRST_CHUNK', t_start)}")

    if "TTS_START" in events:
        print(f"\nTTS:")
        print(f"  start = {rel('TTS_START', t_start)}")
        print(f"  end   = {rel('TTS_END', t_start)}")
        print(f"  total = {total('TTS_START', 'TTS_END')}")

    print(f"\nAUDIO:")
    print(f"  playback_start = {rel('AUDIO_PLAY_START', t_start)}")

    print(f"\nREQUEST:")
    print(f"  total = {rel('REQUEST_END', t_start)}")
    print("=" * 60)

async def main():
    print("Initializing components...")
    await db.initialize()
    register_all_actions()

    # Load components
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

    # ── Monkey-Patching for detailed tracing ──
    original_transcribe = pipeline.stt.transcribe
    async def patched_transcribe(audio_data):
        events["STT_START"] = time.time()
        res = await original_transcribe(audio_data)
        events["STT_END"] = time.time()
        return res
    pipeline.stt.transcribe = patched_transcribe

    original_route_and_resolve = pipeline.router.route_and_resolve
    async def patched_route_and_resolve(text):
        events["ROUTER_START"] = time.time()
        res = await original_route_and_resolve(text)
        events["ROUTER_END"] = time.time()
        events["ROUTE_SELECTED"] = res.route.value
        return res
    pipeline.router.route_and_resolve = patched_route_and_resolve

    original_search = pipeline.router.web_provider.search
    async def patched_search(query, max_results=3):
        events["SEARCH_START"] = time.time()
        res = await original_search(query, max_results)
        events["SEARCH_END"] = time.time()
        return res
    pipeline.router.web_provider.search = patched_search

    from AI.Router.tools.calculator_tool import SafeCalculatorTool
    original_calc_process = SafeCalculatorTool.process
    def patched_calc_process(query):
        events["TOOL_START"] = time.time()
        res = original_calc_process(query)
        events["TOOL_END"] = time.time()
        return res
    SafeCalculatorTool.process = patched_calc_process

    original_llm_stream = pipeline.llm.stream
    async def patched_llm_stream(prompt, context=""):
        events["LLM_START"] = time.time()
        first_token_recorded = False
        async for token in original_llm_stream(prompt, context):
            if not first_token_recorded:
                events["LLM_FIRST_TOKEN"] = time.time()
                first_token_recorded = True
            yield token
        events["LLM_END"] = time.time()
    pipeline.llm.stream = patched_llm_stream

    original_chunker = pipeline._sentence_chunker
    async def patched_chunker(token_stream, tracker=None):
        first_chunk_recorded = False
        async for chunk in original_chunker(token_stream, tracker):
            if not first_chunk_recorded:
                events["CHUNKER_FIRST_CHUNK"] = time.time()
                first_chunk_recorded = True
            yield chunk
    pipeline._sentence_chunker = patched_chunker

    original_synthesize = pipeline.tts.synthesize
    async def patched_synthesize(text, voice=None, speed=1.0):
        if "TTS_START" not in events:
            events["TTS_START"] = time.time()
        res = await original_synthesize(text, voice, speed)
        if "TTS_END" not in events:
            events["TTS_END"] = time.time()
        return res
    pipeline.tts.synthesize = patched_synthesize

    original_play = pipeline.tts.audio_output.play
    async def patched_play(audio_data, sample_rate=24000):
        if "AUDIO_PLAY_START" not in events:
            events["AUDIO_PLAY_START"] = time.time()
        res = await original_play(audio_data, sample_rate)
        return res
    pipeline.tts.audio_output.play = patched_play

    # ── Prewarming ──
    print("\nPrewarming LLM, TTS, STT to avoid initial loading penalty...")
    async for _ in pipeline.llm.stream("Warmup."):
         pass
    warmup_audio = await pipeline.tts.synthesize("Warmup.", voice="am_michael", speed=1.0)
    await pipeline.stt.transcribe(warmup_audio)
    await pipeline.playback_queue.join()
    print("Prewarming complete.")

    queries = [
        "What is YouTube?",
        "What is 25 + 37?",
        "What is the weather today?",
        "What's on my calendar today?",
        "What is happening with NVIDIA?",
    ]

    for q in queries:
        print(f"\n" + "=" * 60)
        print(f"Executing: '{q}'")
        print("=" * 60)
        
        global events
        events = {}
        
        # 1. Synthesize query text to WAV bytes to feed to STT
        query_audio = await pipeline.tts.synthesize(q, voice="am_michael", speed=1.0)
        
        # 2. Reset playback queue
        pipeline.stop_speech()
        await pipeline.playback_queue.join()
        
        # 3. Process the audio
        req_id = uuid.uuid4().hex[:6]
        events["REQUEST_START"] = time.time()
        
        res = await pipeline.process_audio(query_audio, voice="am_michael", play_local=True)
        
        # 4. Wait for audio playback to finish
        await pipeline.playback_queue.join()
        events["REQUEST_END"] = time.time()
        
        # 5. Output timeline
        print_timeline(req_id)
        
        # Short sleep between queries
        await asyncio.sleep(1.0)

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
