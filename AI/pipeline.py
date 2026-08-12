"""
CYNEXIS — Voice & AI Conversational Pipeline
End-to-end voice loop:
MIC → STT → Intent → Safety → Action Registry → Robot
For questions: STT → Intent → LLM (+ Personality & Memory) → Kokoro TTS → Laptop Speaker
LLM NEVER directly controls hardware.
"""

import time
import asyncio
import re
from typing import Optional, AsyncIterator
import psutil

def capture_resources():
    try:
        process = psutil.Process()
        sys_cpu = psutil.cpu_percent(interval=None)
        proc_cpu = process.cpu_percent(interval=None)
        proc_ram_mb = process.memory_info().rss / (1024 * 1024)
        sys_ram_pct = psutil.virtual_memory().percent
        return {
            "sys_cpu": round(sys_cpu, 1),
            "proc_cpu": round(proc_cpu, 1),
            "proc_ram_mb": round(proc_ram_mb, 1),
            "sys_ram_pct": round(sys_ram_pct, 1),
        }
    except Exception:
        return {"sys_cpu": 0.0, "proc_cpu": 0.0, "proc_ram_mb": 0.0, "sys_ram_pct": 0.0}

from core.constants import ActionName, SystemMode
from core.state import robot_state
from core.logger import get_logger
from core.config import settings

from AI.STT.provider import STTProvider
from AI.STT.microphone import MicrophoneInput
from AI.TTS.provider import TTSProvider
from AI.TTS.voice_manager import voice_manager
from AI.LLM.provider import LLMProvider
from AI.Intent.engine import IntentEngine
from AI.Memory.provider import MemoryProvider
from AI.Actions.registry import ActionRegistry
from AI.personality import get_system_prompt
from Backend.Robot.Safety.safety import SafetyValidator

log = get_logger("pipeline")


def concat_wavs(wav_chunks: list[bytes]) -> bytes:
    """Concatenate multiple PCM-16 24kHz WAV chunks into a single valid WAV file."""
    if not wav_chunks:
        return b""
    chunks = [c for c in wav_chunks if len(c) >= 44]
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]

    # Concatenate raw PCM data (skip the 44-byte WAV header of each chunk)
    raw_pcm = b"".join(c[44:] for c in chunks)

    # Construct standard 44-byte WAV header for the combined PCM data
    header = bytearray(44)
    header[0:4] = b"RIFF"
    header[4:8] = (len(raw_pcm) + 36).to_bytes(4, "little")
    header[8:12] = b"WAVE"
    header[12:16] = b"fmt "
    header[16:20] = (16).to_bytes(4, "little")      # Subchunk1Size
    header[20:22] = (1).to_bytes(2, "little")       # AudioFormat (1 = PCM)
    header[22:24] = (1).to_bytes(2, "little")       # NumChannels (1 = Mono)
    header[24:28] = (24000).to_bytes(4, "little")   # SampleRate (24000)
    header[28:32] = (48000).to_bytes(4, "little")   # ByteRate (24000 * 1 * 2)
    header[32:34] = (2).to_bytes(2, "little")       # BlockAlign
    header[34:36] = (16).to_bytes(2, "little")      # BitsPerSample (16)
    header[36:40] = b"data"
    header[40:44] = len(raw_pcm).to_bytes(4, "little")

    return bytes(header) + raw_pcm


class VoicePipeline:
    """
    Complete end-to-end voice and conversational processing pipeline.

    Architecture:
        Robot Command Path:
            MIC -> STT -> INTENT -> SAFETY -> ACTION_REGISTRY -> CONTROLLER -> ROBOT

        Conversation Path:
            MIC -> STT -> INTENT -> LLM (Streaming) -> Sentences -> Kokoro -> Audio Queue -> Playback

    The LLM may interpret language and generate responses.
    The LLM must NOT directly control hardware.
    """

    def __init__(
        self,
        stt: STTProvider,
        tts: TTSProvider,
        llm: LLMProvider,
        intent: IntentEngine,
        memory: MemoryProvider,
        actions: ActionRegistry,
        safety: SafetyValidator,
        microphone: Optional[MicrophoneInput] = None,
    ):
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.intent = intent
        self.memory = memory
        self.actions = actions
        self.safety = safety
        self.microphone = microphone
        self.playback_queue = asyncio.Queue()
        self.playback_task = None
        self.current_tracker = None
        self._interrupted = False
        log.info("VoicePipeline initialized with low-latency streaming and audio playback queue")

    def _ensure_playback_task(self):
        """Ensure the background playback worker task is running if an event loop is active."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running event loop

        if self.playback_task is None or self.playback_task.done():
            self.playback_task = loop.create_task(self._playback_worker())

    async def _playback_worker(self):
        """Sequential playback worker task that processes speech chunks from the queue."""
        while True:
            try:
                item = await self.playback_queue.get()
                if item is None:
                    self.playback_queue.task_done()
                    break

                if isinstance(item, tuple) and len(item) == 3:
                    chunk, play_local, is_first = item
                else:
                    chunk, play_local = item
                    is_first = False

                if is_first and self.current_tracker is not None:
                    self.current_tracker["playback_started"] = time.time()
                    self.current_tracker["playback_started_resources"] = capture_resources()

                if play_local and self.tts.audio_output:
                    robot_state.voice.is_speaking = True
                    robot_state.voice.state = "SPEAKING"
                    try:
                        await self.tts.audio_output.play(chunk, sample_rate=24000)
                    finally:
                        robot_state.voice.is_speaking = False
                        if robot_state.voice.state == "SPEAKING":
                            robot_state.voice.state = "IDLE"

                self.playback_queue.task_done()

                # Check for total playback completion
                if self.playback_queue.empty() and self.current_tracker is not None:
                    if self.current_tracker.get("llm_generation_complete") is not None:
                        now = time.time()
                        self.current_tracker["total_response_complete"] = now
                        self.current_tracker["total_response_complete_resources"] = capture_resources()
                        self.current_tracker["total_playback_complete"] = now
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Playback worker error: {e}")

    def stop_speech(self) -> None:
        """Immediately stop any active speech playback and flush the audio queue."""
        self._interrupted = True
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
                self.playback_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        if hasattr(self.tts, "stop"):
            self.tts.stop()

        robot_state.voice.is_speaking = False
        if robot_state.voice.state == "SPEAKING":
            robot_state.voice.state = "IDLE"
        log.info("VoicePipeline: Active speech interrupted and stopped")

    async def _sentence_chunker(self, token_stream: AsyncIterator[str], tracker: Optional[dict] = None) -> AsyncIterator[str]:
        """Buffer tokens and yield speech chunks as early as possible.

        Strategy — yield text to Kokoro at the earliest natural break:
          1. Always yield on sentence-ending punctuation (. ! ?)
          2. Also yield on clause boundaries (, ; : —) when buffer > 25 chars
             so Kokoro starts synthesizing sooner.
          3. Force-flush if buffer > 80 chars with no punctuation at all.

        Shorter chunks = Kokoro produces first audio faster = lower TTFA.
        """
        buffer = ""
        sentence_end_re = re.compile(r"([^.!?]+[.!?]+)(?:\s+|$)")
        clause_break_re = re.compile(r"(.{20,}?[,;:\u2014\u2013\-])(?:\s+)")
        first_clause_re = re.compile(r"(.{10,}?[,;:\u2014\u2013.!?])(?:\s+)")

        is_first_token = True
        is_first_chunk = True

        if tracker is not None:
            tracker["chunks"] = []

        async for token in token_stream:
            if is_first_token and token.strip():
                is_first_token = False
                if tracker is not None:
                    tracker["llm_first_token"] = time.time()
                    tracker["llm_first_token_resources"] = capture_resources()
            buffer += token

            # For the very first chunk: ultra-fast early yielding for low TTFA
            if is_first_chunk:
                match = first_clause_re.search(buffer)
                if match:
                    chunk = match.group(1).strip().rstrip(",;:\u2014\u2013-")
                    if chunk and len(chunk) >= 8:
                        is_first_chunk = False
                        if tracker is not None:
                            now = time.time()
                            tracker["llm_first_clause"] = now
                            tracker["first_clause_ready"] = now
                            tracker["first_clause_ready_resources"] = capture_resources()
                            tracker["chunks"].append({
                                "text": chunk,
                                "length": len(chunk),
                                "reason": "first_clause_early_punct"
                            })
                        yield chunk
                        buffer = buffer[match.end():]
                        continue

                # If first chunk reaches 35 chars without punctuation, flush on word boundary
                if len(buffer) >= 35:
                    last_space = buffer.rfind(" ", 15, len(buffer) - 3)
                    if last_space > 0:
                        chunk = buffer[:last_space].strip()
                        if chunk and len(chunk) >= 12:
                            is_first_chunk = False
                            if tracker is not None:
                                now = time.time()
                                tracker["llm_first_clause"] = now
                                tracker["first_clause_ready"] = now
                                tracker["first_clause_ready_resources"] = capture_resources()
                                tracker["chunks"].append({
                                    "text": chunk,
                                    "length": len(chunk),
                                    "reason": "first_clause_word_boundary"
                                })
                            yield chunk
                            buffer = buffer[last_space:].lstrip()
                            continue

            # Standard subsequent chunk handling
            # 1. Sentence boundaries
            while True:
                match = sentence_end_re.search(buffer)
                if not match:
                    break
                sentence = match.group(1).strip()
                if sentence:
                    is_first_chunk = False
                    if tracker is not None:
                        if tracker.get("llm_first_clause") is None:
                            tracker["llm_first_clause"] = time.time()
                        if tracker.get("first_clause_ready") is None:
                            tracker["first_clause_ready"] = time.time()
                            tracker["first_clause_ready_resources"] = capture_resources()
                        tracker["chunks"].append({
                            "text": sentence,
                            "length": len(sentence),
                            "reason": "sentence_boundary"
                        })
                    yield sentence
                buffer = buffer[match.end():]

            # 2. Clause boundaries
            if len(buffer) > 25:
                match = clause_break_re.search(buffer)
                if match:
                    clause = match.group(1).strip().rstrip(",;:\u2014\u2013-")
                    if clause and len(clause) > 10:
                        is_first_chunk = False
                        if tracker is not None:
                            if tracker.get("llm_first_clause") is None:
                                tracker["llm_first_clause"] = time.time()
                            if tracker.get("first_clause_ready") is None:
                                tracker["first_clause_ready"] = time.time()
                                tracker["first_clause_ready_resources"] = capture_resources()
                            tracker["chunks"].append({
                                "text": clause,
                                "length": len(clause),
                                "reason": "clause_boundary"
                            })
                        yield clause
                        buffer = buffer[match.end():]

            # 3. Force flush at 70 chars
            if len(buffer) > 70:
                last_space = buffer.rfind(" ", 20, len(buffer) - 5)
                if last_space > 0:
                    chunk = buffer[:last_space].strip()
                    if chunk:
                        is_first_chunk = False
                        if tracker is not None:
                            if tracker.get("llm_first_clause") is None:
                                tracker["llm_first_clause"] = time.time()
                            if tracker.get("first_clause_ready") is None:
                                tracker["first_clause_ready"] = time.time()
                                tracker["first_clause_ready_resources"] = capture_resources()
                            tracker["chunks"].append({
                                "text": chunk,
                                "length": len(chunk),
                                "reason": "force_flush"
                            })
                        yield chunk
                    buffer = buffer[last_space:].lstrip()

        remaining = buffer.strip()
        if remaining:
            if tracker is not None:
                if tracker.get("llm_first_clause") is None:
                    tracker["llm_first_clause"] = time.time()
                if tracker.get("first_clause_ready") is None:
                    tracker["first_clause_ready"] = time.time()
                    tracker["first_clause_ready_resources"] = capture_resources()
                tracker["chunks"].append({
                    "text": remaining,
                    "length": len(remaining),
                    "reason": "stream_end"
                })
            yield remaining

    async def _synthesize_and_queue_response(
        self, text: str, voice: str, speed: float, result: dict, speech_end_ts: float, response_ready_ts: float, play_local: bool
    ) -> tuple[list[bytes], float]:
        """Split static text response, synthesize sentences, queue them, and track latency."""
        sentence_ends = re.compile(r"([^.!?]+[.!?]+)(?:\s+|$)")
        sentences = [s.strip() for s in sentence_ends.findall(text) if s.strip()]
        if not sentences:
            sentences = [text.strip()]

        wav_chunks = []
        is_first = True
        total_tts_time = 0.0

        for sentence in sentences:
            if self._interrupted:
                log.info("Synthesis queue: Interrupted, aborting")
                break
            t_synth = time.time()
            if is_first and self.current_tracker is not None:
                self.current_tracker["tts_synthesis_start"] = t_synth

            try:
                wav_chunk = await self.tts.synthesize(sentence, voice=voice, speed=speed)
            except Exception as e:
                log.error(f"TTS synthesis chunk failed: {e}")
                wav_chunk = None

            total_tts_time += time.time() - t_synth
            if wav_chunk is not None:
                wav_chunks.append(wav_chunk)
                await self.playback_queue.put((wav_chunk, play_local, is_first))

                if is_first:
                    is_first = False
                    now = time.time()
                    if self.current_tracker is not None:
                        self.current_tracker["first_audio_generated"] = now
                    result["latencies"]["tts_first_audio_ready"] = now
                    result["latencies"]["playback_started"] = now

        if self.current_tracker is not None:
            self.current_tracker["llm_generation_complete"] = time.time()

        return wav_chunks, total_tts_time

    def _fill_latencies(
        self, result: dict, speech_end_ts: float, stt_complete_ts: Optional[float],
        intent_complete_ts: Optional[float], response_ready_ts: Optional[float],
        tts_first_audio_ready_ts: Optional[float], playback_started_ts: Optional[float],
        total_tts_time: float, t_start: float
    ):
        """Calculate and fill relative duration latency metrics."""
        now = time.time()
        stt_comp = stt_complete_ts or speech_end_ts
        int_comp = intent_complete_ts or stt_comp
        resp_ready = response_ready_ts or int_comp
        first_audio = tts_first_audio_ready_ts or resp_ready
        play_start = playback_started_ts or first_audio

        result["latencies"] = {
            "speech_end": speech_end_ts,
            "stt_complete": stt_complete_ts,
            "intent_complete": intent_complete_ts,
            "response_ready": response_ready_ts,
            "tts_first_audio_ready": tts_first_audio_ready_ts,
            "playback_started": playback_started_ts,
            # Relative Latencies (s)
            "stt_s": round(stt_comp - speech_end_ts, 3) if stt_complete_ts else 0.0,
            "intent_s": round(int_comp - stt_comp, 3) if intent_complete_ts else 0.0,
            "llm_or_action_s": round(resp_ready - int_comp, 3) if response_ready_ts else 0.0,
            "tts_first_chunk_s": round(first_audio - resp_ready, 3) if tts_first_audio_ready_ts else 0.0,
            "tts_s": round(total_tts_time, 3),
            "time_to_first_audio_s": round(play_start - speech_end_ts, 3) if playback_started_ts else 0.0,
            "total_s": round(now - t_start, 3),
        }

        # If high-precision tracker is set, add it and calculate precise relative latencies:
        if self.current_tracker:
            tracker = self.current_tracker
            result["tracker"] = tracker
            
            # STT latency = STT complete - stt_start (or physical_speech_end)
            stt_lat = 0.0
            if tracker.get("stt_complete") and tracker.get("stt_start"):
                stt_lat = tracker["stt_complete"] - tracker["stt_start"]
            elif tracker.get("stt_complete") and tracker.get("physical_speech_end"):
                stt_lat = tracker["stt_complete"] - tracker["physical_speech_end"]
                
            # LLM TTFT = LLM first token - llm_start
            llm_ttft = 0.0
            if tracker.get("llm_first_token") and tracker.get("llm_start"):
                llm_ttft = tracker["llm_first_token"] - tracker["llm_start"]
            elif tracker.get("llm_first_token") and tracker.get("intent_complete"):
                llm_ttft = tracker["llm_first_token"] - tracker["intent_complete"]
                
            # first sentence/clause latency = first_clause_ready - llm_start
            first_clause_lat = 0.0
            if tracker.get("first_clause_ready") and tracker.get("llm_start"):
                first_clause_lat = tracker["first_clause_ready"] - tracker["llm_start"]
            elif tracker.get("llm_first_clause") and tracker.get("intent_complete"):
                first_clause_lat = tracker["llm_first_clause"] - tracker["intent_complete"]
                
            # TTS first-audio latency = tts_first_audio_ready - tts_start
            tts_first_audio_lat = 0.0
            if tracker.get("tts_first_audio_ready") and tracker.get("tts_start"):
                tts_first_audio_lat = tracker["tts_first_audio_ready"] - tracker["tts_start"]
            elif tracker.get("first_audio_generated") and tracker.get("tts_synthesis_start"):
                tts_first_audio_lat = tracker["first_audio_generated"] - tracker["tts_synthesis_start"]
                
            # 7 Discrete Pipeline Intervals
            int1_speech_to_stt = round(stt_lat, 3)
            int2_stt_to_llm = round((tracker.get("llm_start") or stt_comp) - stt_comp, 3) if tracker.get("llm_start") and stt_complete_ts else 0.0
            int3_llm_ttft = round(llm_ttft, 3)
            int4_clause_formation = round((tracker.get("first_clause_ready") or 0) - (tracker.get("llm_first_token") or 0), 3) if tracker.get("first_clause_ready") and tracker.get("llm_first_token") else 0.0
            int5_clause_to_tts = round((tracker.get("tts_start") or 0) - (tracker.get("first_clause_ready") or 0), 3) if tracker.get("tts_start") and tracker.get("first_clause_ready") else 0.0
            int6_tts_synthesis = round(tts_first_audio_lat, 3)
            int7_audio_to_playback = round((tracker.get("playback_started") or 0) - (tracker.get("tts_first_audio_ready") or 0), 3) if tracker.get("playback_started") and tracker.get("tts_first_audio_ready") else 0.0

            # actual TTFA = playback started - physical speech end (Validate: reject <= 0.0)
            actual_ttfa = None
            if tracker.get("playback_started") and tracker.get("physical_speech_end"):
                diff = tracker["playback_started"] - tracker["physical_speech_end"]
                if diff > 0.01:
                    actual_ttfa = round(diff, 3)
            elif playback_started_ts and speech_end_ts:
                diff = playback_started_ts - speech_end_ts
                if diff > 0.01:
                    actual_ttfa = round(diff, 3)
                
            # total response latency = total response complete - physical speech end
            total_response_lat = 0.0
            if tracker.get("total_response_complete") and tracker.get("physical_speech_end"):
                total_response_lat = tracker["total_response_complete"] - tracker["physical_speech_end"]
            elif tracker.get("total_playback_complete") and tracker.get("physical_speech_end"):
                total_response_lat = tracker["total_playback_complete"] - tracker["physical_speech_end"]
            else:
                total_response_lat = now - (tracker.get("physical_speech_end") or t_start)
                
            result["latencies"].update({
                "stt_latency": round(stt_lat, 3),
                "llm_ttft": round(llm_ttft, 3),
                "first_clause_latency": round(first_clause_lat, 3),
                "tts_first_audio_latency": round(tts_first_audio_lat, 3),
                "actual_ttfa": actual_ttfa,
                "total_response_latency": round(total_response_lat, 3),
                "intervals": {
                    "speech_to_stt_s": int1_speech_to_stt,
                    "stt_to_llm_s": int2_stt_to_llm,
                    "llm_ttft_s": int3_llm_ttft,
                    "clause_formation_s": int4_clause_formation,
                    "clause_to_tts_s": int5_clause_to_tts,
                    "tts_synthesis_s": int6_tts_synthesis,
                    "audio_to_playback_s": int7_audio_to_playback,
                }
            })

    async def process_audio(
        self,
        audio_data: Optional[bytes] = None,
        duration_s: float = 3.0,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        play_local: Optional[bool] = None,
    ) -> dict:
        """Process raw audio through the optimized low-latency pipeline."""
        t_start = time.time()
        self._ensure_playback_task()
        self._interrupted = False
        resolved_voice = voice or voice_manager.get_current_voice()
        resolved_speed = speed if speed is not None else voice_manager.get_speed()
        resolved_play_local = play_local if play_local is not None else getattr(settings, "tts_play_local", True)
        # Derive the real provider name from the instance, not just config
        if self.tts and hasattr(self.tts, '__class__'):
            cls = type(self.tts).__name__
            if 'Kokoro' in cls:
                provider_name = 'kokoro'
            elif 'Mock' in cls:
                provider_name = 'mock'
            else:
                provider_name = cls.lower().replace('ttsprovider', '')
        else:
            provider_name = getattr(settings, "tts_provider", "kokoro")

        result = {
            "text": "",
            "is_command": False,
            "action": None,
            "action_result": None,
            "response": "",
            "voice": resolved_voice,
            "speed": resolved_speed,
            "tts_provider": provider_name,
            "audio_bytes": b"",
            "latencies": {},
            "error": None,
        }

        tracker = {
            "speech_end": None,
            "stt_start": None,
            "stt_complete": None,
            "llm_start": None,
            "llm_first_token": None,
            "first_clause_ready": None,
            "tts_start": None,
            "tts_first_audio_ready": None,
            "playback_started": None,
            "total_response_complete": None,
            "physical_speech_end": None,
            "intent_complete": None,
            "llm_first_token": None,
            "llm_first_clause": None,
            "tts_synthesis_start": None,
            "first_audio_generated": None,
            "playback_started": None,
            "llm_generation_complete": None,
            "total_playback_complete": None,
            "chunks": [],
        }
        self.current_tracker = tracker

        # Step 0: Microphone Capture (if audio_data is not provided)
        if audio_data is None and self.microphone is not None:
            robot_state.voice.is_listening = True
            robot_state.voice.state = "LISTENING"
            try:
                audio_data = await self.microphone.record(duration_s=duration_s)
                if hasattr(self.microphone, "last_capture_metrics") and self.microphone.last_capture_metrics:
                    tracker.update(self.microphone.last_capture_metrics)
            except Exception as e:
                result["error"] = f"Microphone recording failed: {e}"
                robot_state.voice.state = "ERROR"
                log.error(result["error"])
                return result
            finally:
                robot_state.voice.is_listening = False

        speech_end_ts = time.time()
        tracker["speech_end"] = speech_end_ts
        # Use last detected speech timestamp from VAD if available, otherwise speech_end_ts
        if tracker.get("last_detected_speech"):
            tracker["physical_speech_end"] = tracker["last_detected_speech"]
        else:
            tracker["physical_speech_end"] = speech_end_ts
        tracker["speech_end_resources"] = capture_resources()

        if not audio_data:
            result["error"] = "No audio data provided or recorded."
            robot_state.voice.state = "IDLE"
            self._fill_latencies(result, speech_end_ts, None, None, None, None, None, 0.0, t_start)
            return result

        # Step 1: STT
        stt_start_ts = time.time()
        tracker["stt_start"] = stt_start_ts
        tracker["stt_start_resources"] = capture_resources()
        robot_state.voice.is_processing = True
        robot_state.voice.state = "THINKING"
        try:
            text = await self.stt.transcribe(audio_data)
            stt_complete_ts = time.time()
            tracker["stt_complete"] = stt_complete_ts
            tracker["stt_complete_resources"] = capture_resources()
            if hasattr(self.stt, "last_inference_metrics") and self.stt.last_inference_metrics:
                tracker.update(self.stt.last_inference_metrics)
            result["text"] = text
            robot_state.voice.last_utterance = text
            await self.memory.add_conversation("user", text)
        except Exception as e:
            result["error"] = f"STT failed: {e}"
            robot_state.voice.state = "ERROR"
            robot_state.voice.is_processing = False
            log.error(result["error"])
            self._fill_latencies(result, speech_end_ts, time.time(), None, None, None, None, 0.0, t_start)
            return result

        # Step 2: Intent classification
        intent_complete_ts = time.time()
        action_name = self.intent.classify(text)
        tracker["intent_complete"] = intent_complete_ts

        # Check for dangerous/invalid command keywords (Safety Bypass)
        blocked_keywords = {"hack_motors", "hack"}
        text_lower = text.lower().strip()
        if any(kw in text_lower for kw in blocked_keywords):
            result["response"] = "Safety block: Command rejected."
            result["error"] = "Safety block: Unauthorized command access."
            robot_state.voice.state = "ERROR"
            robot_state.voice.is_processing = False
            response_ready_ts = time.time()
            self._fill_latencies(result, speech_end_ts, stt_complete_ts, intent_complete_ts, response_ready_ts, None, None, 0.0, t_start)
            return result

        # LLM Start
        llm_start_ts = time.time()
        tracker["llm_start"] = llm_start_ts
        tracker["llm_start_resources"] = capture_resources()

        response_ready_ts = None
        tts_first_audio_ready_ts = None
        playback_started_ts = None
        total_tts_time = 0.0
        wav_chunks = []

        if action_name:
            # ROBOT COMMAND PATH (Bypasses LLM entirely)
            result["is_command"] = True
            result["action"] = action_name.value
            robot_state.voice.state = "EXECUTING"

            # Check for interrupt logic if command is STOP or EMERGENCY_STOP
            if action_name in {ActionName.STOP, ActionName.EMERGENCY_STOP}:
                self.stop_speech()

            # Execute action
            try:
                self.safety.validate_action(action_name.value)
                action_result = await self.actions.execute(action_name.value)
                result["action_result"] = action_result
                response_ready_ts = time.time()
                data = action_result.get("data", {})
                result["response"] = data.get("speech", f"Done: {action_name.value}")
            except Exception as e:
                result["error"] = str(e)
                result["response"] = f"I cannot do that. {e}"
                robot_state.voice.state = "ERROR"
                log.warning(f"Safety rejected '{action_name.value}': {e}")
                response_ready_ts = time.time()

            # Synthesize and play command response
            if result["response"]:
                wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                    result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local
                )
                if result["latencies"].get("tts_first_audio_ready"):
                    tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                    playback_started_ts = result["latencies"]["playback_started"]

        else:
            # CONVERSATION PATH (LLM Streaming + sentence synthesis)
            robot_state.voice.state = "THINKING"
            try:
                history = await self.memory.get_conversation_history(limit=5)
                system_prompt = get_system_prompt()
                context = f"System: {system_prompt}\n" + "\n".join(
                    f"{m['role']}: {m['content']}" for m in history
                )

                tracker["llm_start"] = time.time()
                tracker["llm_start_resources"] = capture_resources()
                token_stream = self.llm.stream(text, context=context)
                sentence_stream = self._sentence_chunker(token_stream, tracker)
                full_response = ""
                is_first = True

                async for sentence in sentence_stream:
                    if self._interrupted:
                        log.info("Pipeline loop: Interrupted flag set, aborting")
                        break
                    if is_first:
                        response_ready_ts = time.time()
                        tracker["tts_start"] = response_ready_ts
                        tracker["tts_start_resources"] = capture_resources()
                        tracker["tts_synthesis_start"] = response_ready_ts
                    full_response += sentence + " "
                    t_synth = time.time()
                    try:
                        wav_chunk = await self.tts.synthesize(sentence, voice=resolved_voice, speed=resolved_speed)
                    except Exception as e:
                        log.error(f"TTS synthesis chunk failed: {e}")
                        wav_chunk = None

                    if self._interrupted:
                        log.info("Pipeline loop: Interrupted during synthesis, aborting")
                        break

                    total_tts_time += time.time() - t_synth
                    if wav_chunk is not None:
                        wav_chunks.append(wav_chunk)
                        await self.playback_queue.put((wav_chunk, resolved_play_local, is_first))

                        if is_first:
                            is_first = False
                            now = time.time()
                            tracker["tts_first_audio_ready"] = now
                            tracker["tts_first_audio_ready_resources"] = capture_resources()
                            tracker["first_audio_generated"] = now
                            tts_first_audio_ready_ts = now
                            playback_started_ts = now
                            result["latencies"]["tts_first_audio_ready"] = now
                            result["latencies"]["playback_started"] = now
                            result["latencies"]["tts_first_chunk_s"] = round(now - response_ready_ts, 3)
                            result["latencies"]["time_to_first_audio_s"] = round(now - speech_end_ts, 3)

                tracker["llm_generation_complete"] = time.time()

                result["response"] = full_response.strip()
                if result["response"]:
                    await self.memory.add_conversation("assistant", result["response"])
                    robot_state.voice.last_response = result["response"]
            except Exception as e:
                result["error"] = f"LLM failed: {e}"
                result["response"] = "I'm sorry, I couldn't process that."
                robot_state.voice.state = "ERROR"
                log.error(result["error"])

        result["audio_bytes"] = concat_wavs(wav_chunks)
        robot_state.voice.is_processing = False
        robot_state.voice.state = "IDLE"

        self._fill_latencies(
            result, speech_end_ts, stt_complete_ts, intent_complete_ts,
            response_ready_ts, tts_first_audio_ready_ts, playback_started_ts,
            total_tts_time, t_start
        )
        return result

    async def process_text(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        play_local: Optional[bool] = None,
    ) -> dict:
        """Process text input (bypass STT) through the optimized low-latency pipeline."""
        t_start = time.time()
        self._ensure_playback_task()
        self._interrupted = False
        resolved_voice = voice or voice_manager.get_current_voice()
        resolved_speed = speed if speed is not None else voice_manager.get_speed()
        resolved_play_local = play_local if play_local is not None else getattr(settings, "tts_play_local", True)
        # Derive the real provider name from the instance, not just config
        if self.tts and hasattr(self.tts, '__class__'):
            cls = type(self.tts).__name__
            if 'Kokoro' in cls:
                provider_name = 'kokoro'
            elif 'Mock' in cls:
                provider_name = 'mock'
            else:
                provider_name = cls.lower().replace('ttsprovider', '')
        else:
            provider_name = getattr(settings, "tts_provider", "kokoro")

        result = {
            "text": text,
            "is_command": False,
            "action": None,
            "action_result": None,
            "response": "",
            "voice": resolved_voice,
            "speed": resolved_speed,
            "tts_provider": provider_name,
            "audio_bytes": b"",
            "latencies": {},
            "error": None,
        }

        tracker = {
            "speech_end": None,
            "stt_start": None,
            "stt_complete": None,
            "llm_start": None,
            "llm_first_token": None,
            "first_clause_ready": None,
            "tts_start": None,
            "tts_first_audio_ready": None,
            "playback_started": None,
            "total_response_complete": None,
            "physical_speech_end": None,
            "stt_complete": None,
            "intent_complete": None,
            "llm_first_token": None,
            "llm_first_clause": None,
            "tts_synthesis_start": None,
            "first_audio_generated": None,
            "playback_started": None,
            "llm_generation_complete": None,
            "total_playback_complete": None,
            "chunks": [],
        }
        self.current_tracker = tracker

        speech_end_ts = time.time()
        tracker["speech_end"] = speech_end_ts
        tracker["physical_speech_end"] = speech_end_ts
        tracker["speech_end_resources"] = capture_resources()
        
        stt_complete_ts = speech_end_ts
        tracker["stt_start"] = speech_end_ts
        tracker["stt_start_resources"] = capture_resources()
        tracker["stt_complete"] = stt_complete_ts
        tracker["stt_complete_resources"] = capture_resources()

        # Check for dangerous/invalid command keywords (Safety Bypass)
        blocked_keywords = {"hack_motors", "hack"}
        text_lower = text.lower().strip()
        if any(kw in text_lower for kw in blocked_keywords):
            result["response"] = "Safety block: Command rejected."
            result["error"] = "Safety block: Unauthorized command access."
            robot_state.voice.state = "ERROR"
            response_ready_ts = time.time()
            intent_complete_ts = response_ready_ts
            self._fill_latencies(result, speech_end_ts, stt_complete_ts, intent_complete_ts, response_ready_ts, None, None, 0.0, t_start)
            return result

        robot_state.voice.is_processing = True
        robot_state.voice.state = "THINKING"
        robot_state.voice.last_utterance = text
        await self.memory.add_conversation("user", text)

        # Intent classification
        action_name = self.intent.classify(text)
        intent_complete_ts = time.time()
        tracker["intent_complete"] = intent_complete_ts

        # LLM Start
        llm_start_ts = time.time()
        tracker["llm_start"] = llm_start_ts
        tracker["llm_start_resources"] = capture_resources()

        response_ready_ts = None
        tts_first_audio_ready_ts = None
        playback_started_ts = None
        total_tts_time = 0.0
        wav_chunks = []

        if action_name:
            # ROBOT COMMAND PATH (Bypasses LLM entirely)
            result["is_command"] = True
            result["action"] = action_name.value
            robot_state.voice.state = "EXECUTING"

            # Check for interrupt logic if command is STOP or EMERGENCY_STOP
            if action_name in {ActionName.STOP, ActionName.EMERGENCY_STOP}:
                self.stop_speech()

            # Execute action
            try:
                self.safety.validate_action(action_name.value)
                action_result = await self.actions.execute(action_name.value)
                result["action_result"] = action_result
                response_ready_ts = time.time()
                data = action_result.get("data", {})
                result["response"] = data.get("speech", f"Done: {action_name.value}")
            except Exception as e:
                result["error"] = str(e)
                result["response"] = f"Cannot execute: {e}"
                robot_state.voice.state = "ERROR"
                response_ready_ts = time.time()

            # Synthesize and play command response
            if result["response"]:
                wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                    result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local
                )
                if result["latencies"].get("tts_first_audio_ready"):
                    tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                    playback_started_ts = result["latencies"]["playback_started"]

        else:
            # CONVERSATION PATH (LLM Streaming + sentence synthesis)
            robot_state.voice.state = "THINKING"
            try:
                history = await self.memory.get_conversation_history(limit=5)
                system_prompt = get_system_prompt()
                context = f"System: {system_prompt}\n" + "\n".join(
                    f"{m['role']}: {m['content']}" for m in history
                )

                tracker["llm_start"] = time.time()
                tracker["llm_start_resources"] = capture_resources()
                token_stream = self.llm.stream(text, context=context)
                sentence_stream = self._sentence_chunker(token_stream, tracker)
                full_response = ""
                is_first = True

                async for sentence in sentence_stream:
                    if self._interrupted:
                        log.info("Pipeline loop: Interrupted flag set, aborting")
                        break
                    if is_first:
                        response_ready_ts = time.time()
                        tracker["tts_start"] = response_ready_ts
                        tracker["tts_start_resources"] = capture_resources()
                        tracker["tts_synthesis_start"] = response_ready_ts
                    full_response += sentence + " "
                    t_synth = time.time()
                    try:
                        wav_chunk = await self.tts.synthesize(sentence, voice=resolved_voice, speed=resolved_speed)
                    except Exception as e:
                        log.error(f"TTS synthesis chunk failed: {e}")
                        wav_chunk = None

                    if self._interrupted:
                        log.info("Pipeline loop: Interrupted during synthesis, aborting")
                        break

                    total_tts_time += time.time() - t_synth
                    if wav_chunk is not None:
                        wav_chunks.append(wav_chunk)
                        await self.playback_queue.put((wav_chunk, resolved_play_local, is_first))

                        if is_first:
                            is_first = False
                            now = time.time()
                            tracker["tts_first_audio_ready"] = now
                            tracker["tts_first_audio_ready_resources"] = capture_resources()
                            tracker["first_audio_generated"] = now
                            tts_first_audio_ready_ts = now
                            playback_started_ts = now
                            result["latencies"]["tts_first_audio_ready"] = now
                            result["latencies"]["playback_started"] = now
                            result["latencies"]["tts_first_chunk_s"] = round(now - response_ready_ts, 3)
                            result["latencies"]["time_to_first_audio_s"] = round(now - speech_end_ts, 3)

                tracker["llm_generation_complete"] = time.time()

                result["response"] = full_response.strip()
                if result["response"]:
                    await self.memory.add_conversation("assistant", result["response"])
                    robot_state.voice.last_response = result["response"]
            except Exception as e:
                result["error"] = f"LLM failed: {e}"
                result["response"] = "I'm sorry, I couldn't process that."
                robot_state.voice.state = "ERROR"
                log.error(result["error"])

        result["audio_bytes"] = concat_wavs(wav_chunks)
        robot_state.voice.is_processing = False
        robot_state.voice.state = "IDLE"

        self._fill_latencies(
            result, speech_end_ts, stt_complete_ts, intent_complete_ts,
            response_ready_ts, tts_first_audio_ready_ts, playback_started_ts,
            total_tts_time, t_start
        )
        return result
