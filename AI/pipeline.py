"""
CYNEXIS — Voice & AI Conversational Pipeline
End-to-end voice loop:
MIC → STT → Intent → Safety → Action Registry → Robot
For questions: STT → Intent → LLM (+ Personality & Memory) → Kokoro TTS → Laptop Speaker
LLM NEVER directly controls hardware.
"""

import base64
import time
import asyncio
import os
import re
from typing import Optional, AsyncIterator, Callable, Awaitable
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
from AI.Router.models import RouteCategory, RoutingResult
from AI.Router.router import IntelligenceRouter, intelligence_router

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
        router: Optional[IntelligenceRouter] = None,
    ):
        self.stt = stt
        self.tts = tts
        self.llm = llm
        self.intent = intent
        self.memory = memory
        self.actions = actions
        self.safety = safety
        self.microphone = microphone
        self.router = router if router is not None else intelligence_router
        self.playback_queue = asyncio.Queue()
        self.playback_task = None
        # WS audio sender queue — bounded to 8 chunks to limit memory; the sender
        # task drains this independently of TTS synthesis so they don't block each other.
        self._ws_queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._ws_sender_task: Optional[asyncio.Task] = None
        self._ws_connection = None  # active WebSocket reference set by ws_voice.py
        self._ws_chunk_index: int = 0
        self.current_tracker = None
        self._interrupted = False
        self._chunks_generated: int = 0
        self._chunks_sent: int = 0
        self._geocode_cache = {}
        log.info("VoicePipeline initialized with low-latency streaming and Intelligence Router")

    def _ensure_playback_task(self):
        """Ensure the background playback worker task is running if an event loop is active."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running event loop

        if self.playback_task is None or self.playback_task.done():
            self.playback_task = loop.create_task(self._playback_worker())

    def _get_history_limit(self, text: str) -> int:
        """Dynamically determine how many turns of history to send based on context relevance."""
        text_lower = text.lower().strip()
        followup_markers = {
            "it", "they", "he", "she", "this", "that", "these", "those", "them", "him", "her",
            "then", "there", "what about", "how about", "and", "why", "who", "which",
            "more", "continue", "explain", "elaborate"
        }
        words = set(re.findall(r"\b\w+\b", text_lower))
        is_followup = any(marker in text_lower for marker in ["what about", "how about"]) or not words.isdisjoint(followup_markers)
        if len(words) <= 2:
            is_followup = True
        return 3 if is_followup else 0

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
        # Also drain the WS sender queue so stale chunks aren't delivered after stop.
        while not self._ws_queue.empty():
            try:
                self._ws_queue.get_nowait()
                self._ws_queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

        if hasattr(self.tts, "stop"):
            self.tts.stop()

        robot_state.voice.is_speaking = False
        if robot_state.voice.state == "SPEAKING":
            robot_state.voice.state = "IDLE"
        log.info("VoicePipeline: Active speech interrupted and stopped")

    def _ensure_ws_sender_task(self) -> None:
        """Start the WS sender worker task if not already running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._ws_sender_task is None or self._ws_sender_task.done():
            self._ws_sender_task = loop.create_task(self._ws_sender_worker())

    async def _ws_sender_worker(self) -> None:
        """
        Dedicated task that drains the WS audio queue and sends chunks to the
        browser independently of TTS synthesis.

        By separating WS delivery from the synthesis loop we avoid head-of-line
        blocking: TTS for chunk N+1 starts the moment synthesis for chunk N
        finishes, regardless of how long the WebSocket send takes.
        """
        while True:
            try:
                item = await self._ws_queue.get()
                if item is None:  # sentinel — shut down
                    self._ws_queue.task_done()
                    break
                wav_bytes, text_chunk, is_first, t_synth_start, t_synth_end = item
                ws = self._ws_connection
                if ws is not None:
                    try:
                        # base64 encoding in a thread — keeps event loop free
                        b64 = await asyncio.to_thread(
                            lambda b=wav_bytes: base64.b64encode(b).decode("utf-8")
                        )
                        await ws.send_json({
                            "type": "chunk",
                            "index": self._ws_chunk_index,
                            "text": text_chunk,
                            "is_first": is_first,
                            "audio_base64": b64,
                            "tts_start": t_synth_start,
                            "tts_end": t_synth_end,
                            "ws_send_ts": time.time(),
                        })
                        self._ws_chunk_index += 1
                        self._chunks_sent += 1
                    except Exception as send_err:
                        log.debug(f"WS sender: failed to send chunk: {send_err}")
                self._ws_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"WS sender worker error: {e}")

    async def _sentence_chunker(self, token_stream: AsyncIterator[str], tracker: Optional[dict] = None) -> AsyncIterator[str]:
        """Buffer tokens and yield speech chunks for Kokoro.

        CHUNKING STRATEGY
        -----------------
        Two hard constraints:

          1. LOW TTFA — chunk 0 must start synthesizing as soon as there
             is a natural, non-trivially-short sentence to work with.

          2. NO STARVATION — chunk 0 must provide enough playback buffer
             for chunk 1 to finish synthesizing before chunk 0 ends.

        At ~14–15 chars/sec spoken (Kokoro default, measured from telemetry)
        the sweet spot for chunk 0 is approximately 30–90 characters:

          30 chars ≈ 2.0 s   (minimum useful buffer)
          50 chars ≈ 3.3 s   (comfortable target)
          90 chars ≈ 6.0 s   (hard cap — above this TTFA becomes painful)

        FIRST CHUNK ALGORITHM
        ---------------------
        Walk complete sentences one at a time.  At each sentence boundary:

          • If accumulated text < FIRST_CHUNK_MIN_CHARS:
                keep accumulating — don't yield a trivially short first word.
          • If accumulated text >= FIRST_CHUNK_MIN_CHARS:
                yield immediately and switch to subsequent-chunk mode.

        This fires as soon as the FIRST complete sentence that is long
        enough is available — it does NOT hold all sentences until the
        total crosses the threshold (that was the 10.5 s bug).

        The FIRST_CHUNK_TARGET_CHARS / FIRST_CHUNK_MAX_CHARS constants are
        safety valves for pathological cases (no punctuation, very short
        sentences that keep arriving).

        SUBSEQUENT CHUNKS
        -----------------
        After chunk 0 is emitted, switch to natural-boundary splitting with
        a SUBSEQUENT_FORCE_FLUSH hard cap.
        """
        # ── Tuning knobs ─────────────────────────────────────────────────
        # At ~14–15 chars/sec spoken:
        #   30 chars ≈ 2.0 s  — minimum to avoid starvation after chunk 0
        #   50 chars ≈ 3.3 s  — comfortable target; yield if single sentence reaches this
        #   90 chars ≈ 6.0 s  — hard max; never accumulate more than this for chunk 0
        # Tune these if measured audio durations diverge significantly.
        FIRST_CHUNK_MIN_CHARS: int = 25    # must reach at a sentence boundary to yield chunk 0
        FIRST_CHUNK_TARGET_CHARS: int = 40 # if a single sentence already exceeds this, yield immediately
        FIRST_CHUNK_MAX_CHARS: int = 60    # hard cap — force-flush regardless of boundary
        SUBSEQUENT_FORCE_FLUSH: int = 120  # unchanged from before
        # ─────────────────────────────────────────────────────────────────

        buffer = ""
        is_first_token = True
        is_first_chunk = True

        # Sentence-end regex — matches text ending with . ! ? ; or newline.
        natural_end_re = re.compile(r"([^.!?;\n]+[.!?;\n])(?:\s+|$)")

        if tracker is not None:
            tracker["chunks"] = []

        async for token in token_stream:
            if is_first_token and token.strip():
                is_first_token = False
                if tracker is not None:
                    tracker["llm_first_token"] = time.time()
                    tracker["llm_first_token_resources"] = capture_resources()
            buffer += token

            if is_first_chunk:
                # ── First-chunk phase ─────────────────────────────────────
                # Walk sentences ONE AT A TIME.  Yield at the first boundary
                # where accumulated text is >= FIRST_CHUNK_MIN_CHARS.
                # This avoids the "accumulate all → 10 s chunk" problem.

                first_chunk_acc = ""   # complete sentences seen so far
                remainder = buffer     # tail after last complete sentence

                while True:
                    m = natural_end_re.search(remainder)
                    if not m:
                        break  # no more complete sentences in buffer right now

                    sentence = m.group(1).strip()
                    candidate = (first_chunk_acc + " " + sentence).strip() if first_chunk_acc else sentence
                    remainder = remainder[m.end():]

                    # Yield immediately if this sentence alone is already large
                    # enough (target chars) — don't wait for another sentence.
                    if len(candidate) >= FIRST_CHUNK_MIN_CHARS:
                        # We have enough — emit chunk 0 and stop accumulating.
                        is_first_chunk = False
                        if tracker is not None:
                            now = time.time()
                            tracker["llm_first_clause"] = now
                            tracker["first_clause_ready"] = now
                            tracker["first_clause_ready_resources"] = capture_resources()
                            tracker["chunks"].append({
                                "text": candidate,
                                "length": len(candidate),
                                "reason": "first_chunk_threshold_met"
                            })
                        yield candidate
                        buffer = remainder
                        break  # exit inner while; continue token loop in subsequent mode
                    else:
                        # This sentence is too short on its own.  Accumulate
                        # it and check the next sentence before deciding.
                        first_chunk_acc = candidate
                        # Don't update buffer yet — wait until we decide to yield.

                # If we just yielded chunk 0, the inner break set is_first_chunk=False.
                # The outer `continue` will restart the token loop in subsequent mode.
                if not is_first_chunk:
                    continue

                # Hard max guard — if buffer has grown past FIRST_CHUNK_MAX_CHARS
                # without a sentence boundary long enough to trigger the above,
                # flush whatever we have to prevent TTFA from growing unbounded.
                if len(buffer) >= FIRST_CHUNK_MAX_CHARS:
                    if first_chunk_acc:
                        # We have some accumulated sentences — use them.
                        chunk = first_chunk_acc
                        buffer = remainder
                    else:
                        # No sentence boundary at all — word-boundary flush.
                        last_space = buffer.rfind(" ", 40, len(buffer) - 5)
                        if last_space > 0:
                            chunk = buffer[:last_space].strip()
                            buffer = buffer[last_space:].lstrip()
                        else:
                            chunk = buffer.strip()
                            buffer = ""
                    if chunk:
                        is_first_chunk = False
                        if tracker is not None:
                            now = time.time()
                            tracker["llm_first_clause"] = now
                            tracker["first_clause_ready"] = now
                            tracker["first_clause_ready_resources"] = capture_resources()
                            tracker["chunks"].append({
                                "text": chunk,
                                "length": len(chunk),
                                "reason": "first_chunk_max_flush"
                            })
                        yield chunk
                    continue

                # Not enough yet — keep accumulating tokens.
                continue

            # ── Subsequent chunks: standard natural-boundary splitting ─────
            while True:
                match = natural_end_re.search(buffer)
                if not match:
                    break
                chunk = match.group(1).strip()
                if chunk:
                    if tracker is not None:
                        if tracker.get("llm_first_clause") is None:
                            tracker["llm_first_clause"] = time.time()
                        if tracker.get("first_clause_ready") is None:
                            tracker["first_clause_ready"] = time.time()
                            tracker["first_clause_ready_resources"] = capture_resources()
                        tracker["chunks"].append({
                            "text": chunk,
                            "length": len(chunk),
                            "reason": "natural_boundary"
                        })
                    yield chunk
                buffer = buffer[match.end():]

            # Force-flush at SUBSEQUENT_FORCE_FLUSH chars to prevent
            # unbounded buffer growth when the LLM produces no punctuation.
            if len(buffer) > SUBSEQUENT_FORCE_FLUSH:
                last_space = buffer.rfind(" ", 80, len(buffer) - 5)
                if last_space > 0:
                    chunk = buffer[:last_space].strip()
                    if chunk:
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

        # ── Stream-end flush ──────────────────────────────────────────────
        # Yield whatever remains when the LLM stream ends.
        # This is the ONLY path for very short single-sentence answers
        # (e.g. "Four.") that never triggered the threshold above.
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
        self, text: str, voice: str, speed: float, result: dict, speech_end_ts: float, response_ready_ts: float, play_local: bool,
        chunk_callback: Optional[Callable[[bytes, str, bool, float, float], Awaitable[None]]] = None
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
                self._chunks_generated += 1
                is_first = False
                # Non-blocking WS delivery: enqueue for the sender worker.
                # Falls back to legacy chunk_callback for non-WS paths (REST API, CLI).
                if self._ws_connection is not None:
                    try:
                        self._ws_queue.put_nowait(
                            (wav_chunk, sentence, is_first, t_synth, time.time())
                        )
                    except asyncio.QueueFull:
                        log.warning("WS audio queue full — dropping chunk for browser")
                elif chunk_callback is not None:
                    try:
                        await chunk_callback(wav_chunk, sentence, is_first, t_synth, time.time())
                    except Exception as cb_err:
                        log.debug(f"Chunk callback error (legacy path): {cb_err}")

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

    async def _resolve_user_location(self, user_loc: str) -> Optional[tuple]:
        """Resolves raw USER_LOCATION string into (lat, lon) coordinates."""
        user_loc_clean = user_loc.strip()
        m = re.match(r"^\s*([\-\d\.]+)\s*,\s*([\-\d\.]+)\s*$", user_loc_clean)
        if m:
            return float(m.group(1)), float(m.group(2))
        
        lower_loc = user_loc_clean.lower()
        if lower_loc == "chennai":
            return 13.0827, 80.2707
        
        cache_key = lower_loc
        if cache_key in self._geocode_cache:
            return self._geocode_cache[cache_key]
        
        import httpx
        headers = {"User-Agent": "CynexisVoiceAssistant/1.0"}
        async with httpx.AsyncClient(timeout=2.5) as client:
            try:
                url = f"https://nominatim.openstreetmap.org/search?q={user_loc_clean}&format=json&limit=1&accept-language=en"
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        coords = float(data[0]["lat"]), float(data[0]["lon"])
                        self._geocode_cache[cache_key] = coords
                        log.info(f"Geocoded override location '{user_loc_clean}' to {coords}")
                        return coords
            except Exception:
                pass

            segments = [s.strip() for s in user_loc_clean.split(",")]
            for segment in segments:
                if not segment or len(segment) < 3:
                    continue
                clean_seg = re.sub(r"\b\d{6}\b", "", segment)
                clean_seg = clean_seg.replace("-", "").strip()
                if not clean_seg or len(clean_seg) < 3:
                    continue
                try:
                    url = f"https://nominatim.openstreetmap.org/search?q={clean_seg}&format=json&limit=1&accept-language=en"
                    r = await client.get(url, headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        if data:
                            coords = float(data[0]["lat"]), float(data[0]["lon"])
                            self._geocode_cache[cache_key] = coords
                            log.info(f"Geocoded override location segment '{clean_seg}' to {coords}")
                            return coords
                except Exception:
                    pass

        return None

    async def process_audio(
        self,
        audio_data: Optional[bytes] = None,
        duration_s: float = 3.0,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        play_local: Optional[bool] = None,
        chunk_callback: Optional[Callable[[bytes, str, bool, float, float], Awaitable[None]]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        accuracy: Optional[float] = None,
        timestamp: Optional[float] = None,
        allow_location_request: bool = False,
    ) -> dict:
        """Process raw audio through the optimized low-latency pipeline."""
        # Geolocation override check
        user_loc = getattr(settings, "user_location", None) or os.getenv("USER_LOCATION")
        if user_loc:
            coords = await self._resolve_user_location(user_loc)
            if coords:
                latitude, longitude = coords
                accuracy = 10.0
                timestamp = time.time() * 1000

        t_start = time.time()
        self._chunks_generated = 0
        self._chunks_sent = 0
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
            "online_telemetry": None,
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

        # Step 2: Routing / Intent classification
        intent_complete_ts = time.time()
        tracker["intent_complete"] = intent_complete_ts

        # Route query through IntelligenceRouter
        route_info: Optional[RoutingResult] = None
        if self.router and getattr(settings, "router_enabled", True):
            route_info = await self.router.route_and_resolve(
                text, latitude=latitude, longitude=longitude, accuracy=accuracy, timestamp=timestamp
            )
            result["route"] = route_info.route.value
            result["route_confidence"] = route_info.confidence
            result["route_reason"] = route_info.reason
            if hasattr(route_info, "online_telemetry") and route_info.online_telemetry:
                result["online_telemetry"] = route_info.online_telemetry

            # If route is WEATHER or LOCATION and we don't have latitude, check if location request is allowed
            log.info(f"GEOLOCATION CHECK: route={route_info.route} latitude={latitude} allow_location_request={allow_location_request}")
            from AI.Router.tools.weather_tool import WeatherTool
            city = WeatherTool.extract_city(text)
            is_weather_gps = (route_info.route == RouteCategory.WEATHER and city is None)
            is_location_query = (route_info.route == RouteCategory.LOCATION)
            if (is_weather_gps or is_location_query) and latitude is None:
                if allow_location_request:
                    result["needs_location"] = True
                    result["recognized_text"] = text
                    robot_state.voice.is_processing = False
                    robot_state.voice.state = "IDLE"
                    self._fill_latencies(
                        result, speech_end_ts, stt_complete_ts, intent_complete_ts,
                        time.time(), None, None, 0.0, t_start
                    )
                    return result
        else:
            action_temp = self.intent.classify(text)
            result["route"] = RouteCategory.ROBOT_COMMAND.value if action_temp else RouteCategory.LOCAL.value

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

        # LLM / Tool Start
        llm_start_ts = time.time()
        tracker["llm_start"] = llm_start_ts
        tracker["llm_start_resources"] = capture_resources()

        response_ready_ts = None
        tts_first_audio_ready_ts = None
        playback_started_ts = None
        total_tts_time = 0.0
        wav_chunks = []

        action_name = self.intent.classify(text) if (route_info is None or route_info.route == RouteCategory.ROBOT_COMMAND) else None

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
                    result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                    chunk_callback=chunk_callback
                )
                if result["latencies"].get("tts_first_audio_ready"):
                    tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                    playback_started_ts = result["latencies"]["playback_started"]

        elif route_info and route_info.direct_response:
            # DETERMINISTIC TOOL PATH (Instant response via Time, Date, Calc, Status, Project Knowledge, or Offline Fallback)
            response_ready_ts = time.time()
            result["response"] = route_info.direct_response
            await self.memory.add_conversation("assistant", result["response"])
            robot_state.voice.last_response = result["response"]

            wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                chunk_callback=chunk_callback
            )
            if result["latencies"].get("tts_first_audio_ready"):
                tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                playback_started_ts = result["latencies"]["playback_started"]

        elif route_info and route_info.route == RouteCategory.VISION:
            # VISION PATH (Moondream2 scene description)
            try:
                action_res = await self.actions.execute(ActionName.DESCRIBE_SCENE.value)
                result["action_result"] = action_res
                data = action_res.get("data", {})
                result["response"] = data.get("speech", data.get("description", "I see the environment."))
            except Exception as e:
                result["error"] = str(e)
                result["response"] = f"Vision error: {e}"
            response_ready_ts = time.time()
            await self.memory.add_conversation("assistant", result["response"])
            robot_state.voice.last_response = result["response"]

            wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                chunk_callback=chunk_callback
            )
            if result["latencies"].get("tts_first_audio_ready"):
                tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                playback_started_ts = result["latencies"]["playback_started"]

        else:
            # CONVERSATION PATH (LLM Streaming + sentence synthesis, with optional live retrieved context)
            robot_state.voice.state = "THINKING"
            try:
                history = await self.memory.get_conversation_history(limit=3)
                system_prompt = get_system_prompt()
                augmented = route_info.augmented_context if route_info else None
                if augmented:
                    context = f"System: {system_prompt}\n{augmented}\n" + "\n".join(
                        f"{m['role']}: {m['content']}" for m in history
                    )
                else:
                    context = f"System: {system_prompt}\n" + "\n".join(
                        f"{m['role']}: {m['content']}" for m in history
                    )

                tracker["llm_start"] = time.time()
                tracker["llm_start_resources"] = capture_resources()
                stream_prompt = text if not augmented else f"{text}\n(State the actual news stories or key facts directly in 1-2 spoken sentences.)"
                token_stream = self.llm.stream(stream_prompt, context=context)
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

                        # Non-blocking WS delivery: enqueue for the sender worker.
                        if self._ws_connection is not None:
                            try:
                                self._ws_queue.put_nowait(
                                    (wav_chunk, sentence, is_first, t_synth, time.time())
                                )
                            except asyncio.QueueFull:
                                log.warning("WS audio queue full — dropping chunk for browser")
                        elif chunk_callback is not None:
                            try:
                                await chunk_callback(wav_chunk, sentence, is_first, t_synth, time.time())
                            except Exception as cb_err:
                                log.debug(f"Chunk callback error (legacy path): {cb_err}")

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
        chunk_callback: Optional[Callable[[bytes, str, bool, float, float], Awaitable[None]]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        accuracy: Optional[float] = None,
        timestamp: Optional[float] = None,
        allow_location_request: bool = False,
    ) -> dict:
        """Process text input (bypass STT) through the optimized low-latency pipeline."""
        # Geolocation override check
        user_loc = getattr(settings, "user_location", None) or os.getenv("USER_LOCATION")
        if user_loc:
            coords = await self._resolve_user_location(user_loc)
            if coords:
                latitude, longitude = coords
                accuracy = 10.0
                timestamp = time.time() * 1000

        t_start = time.time()
        self._chunks_generated = 0
        self._chunks_sent = 0
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
            "online_telemetry": None,
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

        # Routing / Intent classification
        intent_complete_ts = time.time()
        tracker["intent_complete"] = intent_complete_ts

        # Route query through IntelligenceRouter
        route_info: Optional[RoutingResult] = None
        if self.router and getattr(settings, "router_enabled", True):
            route_info = await self.router.route_and_resolve(
                text, latitude=latitude, longitude=longitude, accuracy=accuracy, timestamp=timestamp
            )
            result["route"] = route_info.route.value
            result["route_confidence"] = route_info.confidence
            result["route_reason"] = route_info.reason
            if hasattr(route_info, "online_telemetry") and route_info.online_telemetry:
                result["online_telemetry"] = route_info.online_telemetry

            # If route is WEATHER and we don't have latitude, check if location request is allowed (only if not explicit city)
            # If route is WEATHER or LOCATION and we don't have latitude, check if location request is allowed
            log.info(f"GEOLOCATION CHECK TEXT: route={route_info.route} latitude={latitude} allow_location_request={allow_location_request}")
            from AI.Router.tools.weather_tool import WeatherTool
            city = WeatherTool.extract_city(text)
            is_weather_gps = (route_info.route == RouteCategory.WEATHER and city is None)
            is_location_query = (route_info.route == RouteCategory.LOCATION)
            if (is_weather_gps or is_location_query) and latitude is None:
                if allow_location_request:
                    result["needs_location"] = True
                    result["recognized_text"] = text
                    robot_state.voice.is_processing = False
                    robot_state.voice.state = "IDLE"
                    response_ready_ts = time.time()
                    self._fill_latencies(
                        result, speech_end_ts, stt_complete_ts, intent_complete_ts,
                        response_ready_ts, None, None, 0.0, t_start
                    )
                    return result
        else:
            action_temp = self.intent.classify(text)
            result["route"] = RouteCategory.ROBOT_COMMAND.value if action_temp else RouteCategory.LOCAL.value

        # LLM / Tool Start
        llm_start_ts = time.time()
        tracker["llm_start"] = llm_start_ts
        tracker["llm_start_resources"] = capture_resources()

        response_ready_ts = None
        tts_first_audio_ready_ts = None
        playback_started_ts = None
        total_tts_time = 0.0
        wav_chunks = []

        action_name = self.intent.classify(text) if (route_info is None or route_info.route == RouteCategory.ROBOT_COMMAND) else None

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
                    result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                    chunk_callback=chunk_callback
                )
                if result["latencies"].get("tts_first_audio_ready"):
                    tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                    playback_started_ts = result["latencies"]["playback_started"]

        elif route_info and route_info.route in (RouteCategory.CALCULATOR, "CALCULATOR") and route_info.direct_response:
            # DETERMINISTIC CALCULATOR PATH
            response_ready_ts = time.time()
            result["response"] = route_info.direct_response
            await self.memory.add_conversation("assistant", result["response"])
            robot_state.voice.last_response = result["response"]

            wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                chunk_callback=chunk_callback
            )
            if result["latencies"].get("tts_first_audio_ready"):
                tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                playback_started_ts = result["latencies"]["playback_started"]

            # Print Calculator Telemetry
            tool_time = time.time() - t_start
            print(f"\n============================================================\n"
                  f"[CALCULATOR TELEMETRY]\n"
                  f"ollama=false\n"
                  f"tool_time={tool_time:.3f} s\n"
                  f"direct_response=true\n"
                  f"============================================================\n")

        elif route_info and route_info.direct_response:
            # DETERMINISTIC TOOL PATH (Instant response via Time, Date, Status, Project Knowledge, or Offline Fallback)
            response_ready_ts = time.time()
            result["response"] = route_info.direct_response
            await self.memory.add_conversation("assistant", result["response"])
            robot_state.voice.last_response = result["response"]

            wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                chunk_callback=chunk_callback
            )
            if result["latencies"].get("tts_first_audio_ready"):
                tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                playback_started_ts = result["latencies"]["playback_started"]

        elif route_info and route_info.route == RouteCategory.VISION:
            # VISION PATH (Moondream2 scene description)
            try:
                action_res = await self.actions.execute(ActionName.DESCRIBE_SCENE.value)
                result["action_result"] = action_res
                data = action_res.get("data", {})
                result["response"] = data.get("speech", data.get("description", "I see the environment."))
            except Exception as e:
                result["error"] = str(e)
                result["response"] = f"Vision error: {e}"
            response_ready_ts = time.time()
            await self.memory.add_conversation("assistant", result["response"])
            robot_state.voice.last_response = result["response"]

            wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
                result["response"], resolved_voice, resolved_speed, result, speech_end_ts, response_ready_ts, resolved_play_local,
                chunk_callback=chunk_callback
            )
            if result["latencies"].get("tts_first_audio_ready"):
                tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
                playback_started_ts = result["latencies"]["playback_started"]

        else:
            # CONVERSATION PATH (LLM Streaming + sentence synthesis, with optional live retrieved context)
            robot_state.voice.state = "THINKING"
            try:
                limit = self._get_history_limit(text)
                history = await self.memory.get_conversation_history(limit=limit)
                system_prompt = get_system_prompt()
                augmented = route_info.augmented_context if route_info else None
                if augmented:
                    context = f"System: {system_prompt}\n{augmented}\n" + "\n".join(
                        f"{m['role']}: {m['content']}" for m in history
                    )
                else:
                    context = f"System: {system_prompt}\n" + "\n".join(
                        f"{m['role']}: {m['content']}" for m in history
                    )

                tracker["llm_start"] = time.time()
                tracker["llm_start_resources"] = capture_resources()
                stream_prompt = text if not augmented else f"{text}\n(State the actual news stories or key facts directly in 1-2 spoken sentences.)"
                token_stream = self.llm.stream(stream_prompt, context=context)
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

                        # Non-blocking WS delivery: enqueue for the sender worker.
                        if self._ws_connection is not None:
                            try:
                                self._ws_queue.put_nowait(
                                    (wav_chunk, sentence, is_first, t_synth, time.time())
                                )
                            except asyncio.QueueFull:
                                log.warning("WS audio queue full — dropping chunk for browser")
                        elif chunk_callback is not None:
                            try:
                                await chunk_callback(wav_chunk, sentence, is_first, t_synth, time.time())
                            except Exception as cb_err:
                                log.debug(f"Chunk callback error (legacy path): {cb_err}")

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


    async def process_direct_response(
        self,
        text: str,
        response_text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        play_local: Optional[bool] = None,
        chunk_callback: Optional[Callable[[bytes, str, bool, float, float], Awaitable[None]]] = None,
        route: str = "WEATHER"
    ) -> dict:
        """Process a direct deterministic response (e.g. location error, calculator result) without routing/LLM."""
        t_start = time.time()
        self._chunks_generated = 0
        self._chunks_sent = 0
        self._ensure_playback_task()
        self._interrupted = False
        resolved_voice = voice or voice_manager.get_current_voice()
        resolved_speed = speed if speed is not None else voice_manager.get_speed()
        resolved_play_local = play_local if play_local is not None else getattr(settings, "tts_play_local", True)
        
        result = {
            "text": text,
            "route": route,
            "response": response_text,
            "is_command": False,
            "action": None,
            "latencies": {},
            "online_telemetry": None
        }
        
        await self.memory.add_conversation("user", text)
        await self.memory.add_conversation("assistant", response_text)
        robot_state.voice.last_response = response_text
        
        response_ready_ts = time.time()
        
        wav_chunks, total_tts_time = await self._synthesize_and_queue_response(
            response_text, resolved_voice, resolved_speed, result, t_start, response_ready_ts, resolved_play_local,
            chunk_callback=chunk_callback
        )
        
        tts_first_audio_ready_ts = None
        playback_started_ts = None
        if result["latencies"].get("tts_first_audio_ready"):
            tts_first_audio_ready_ts = result["latencies"]["tts_first_audio_ready"]
            playback_started_ts = result["latencies"]["playback_started"]
            
        self._fill_latencies(
            result, t_start, t_start, t_start,
            response_ready_ts, tts_first_audio_ready_ts, playback_started_ts,
            total_tts_time, t_start
        )
        return result

