"""
CYNEXIS — Kokoro TTS Provider
Real offline, local Text-to-Speech synthesis using Kokoro-82M.

Backend priority:
  1. ONNX  — ~1.5x faster on CPU, lighter memory (if kokoro-onnx + model files present)
  2. PyTorch — original Kokoro KPipeline (always available as fallback)
"""

import io
import os
import re
import time
import asyncio
from pathlib import Path
from typing import Optional
import numpy as np
import soundfile as sf

from core.logger import get_logger
from core.config import settings, PROJECT_ROOT
from core.state import robot_state
from AI.TTS.provider import TTSProvider
from AI.TTS.voice_manager import voice_manager, is_valid_voice, MIN_TTS_SPEED, MAX_TTS_SPEED
from AI.TTS.audio_output import AudioOutput, LocalAudioOutput, MockAudioOutput

log = get_logger("kokoro_tts")

# Safe input limits
MAX_TEXT_LENGTH = 1000
SAMPLE_RATE = 24000


class KokoroTTSProvider(TTSProvider):
    """
    Production local Kokoro TTS provider.
    Runs entirely on-device with zero external API / cloud dependency.

    Backend priority:
      1. ONNX  — ~1.5x faster on CPU for short chunks (best for TTFA)
      2. PyTorch — original Kokoro KPipeline (fallback)
    """

    # ONNX model file paths
    _ONNX_MODEL = Path(PROJECT_ROOT) / "AI Models" / "Kokoro" / "kokoro-v1.0.onnx"
    _ONNX_VOICES = Path(PROJECT_ROOT) / "AI Models" / "Kokoro" / "voices-v1.0.bin"

    def __init__(self, audio_output: Optional[AudioOutput] = None, lang_code: str = "a"):
        self.lang_code = lang_code
        self._pipeline = None       # PyTorch KPipeline (if used)
        self._onnx_model = None     # ONNX Kokoro instance (if used)
        self._backend = None        # "onnx" or "pytorch"
        self._loaded = False
        self._loading_lock = asyncio.Lock()

        # Initialize audio output device
        if audio_output is not None:
            self.audio_output = audio_output
        elif getattr(settings, "tts_play_local", True):
            self.audio_output = LocalAudioOutput()
        else:
            self.audio_output = MockAudioOutput()

        log.info(f"KokoroTTSProvider initialized (lang_code='{self.lang_code}')")

    def is_loaded(self) -> bool:
        """Check if Kokoro model is loaded in memory."""
        return self._loaded and (self._pipeline is not None or self._onnx_model is not None)

    @property
    def backend(self) -> str:
        """Return active backend name: 'onnx', 'pytorch', or 'none'."""
        return self._backend or "none"

    def _can_use_onnx(self) -> bool:
        """Check if ONNX backend is available (package + model files)."""
        try:
            import kokoro_onnx  # noqa: F401
        except ImportError:
            return False
        return self._ONNX_MODEL.exists() and self._ONNX_VOICES.exists()

    async def load(self) -> bool:
        """Load the Kokoro model. Prefers ONNX (~1.5x faster), falls back to PyTorch."""
        if self.is_loaded():
            return True

        async with self._loading_lock:
            if self.is_loaded():
                return True

            try:
                log.info("Loading Kokoro TTS model...")
                t0 = time.time()
                voices_to_warm = ["am_michael", "af_bella", "bm_lewis"]

                if self._can_use_onnx():
                    # ── ONNX backend (faster on CPU) ──────────────
                    def _init_onnx():
                        from kokoro_onnx import Kokoro
                        import onnxruntime as ort
                        
                        kokoro_instance = Kokoro(str(self._ONNX_MODEL), str(self._ONNX_VOICES))
                        
                        # Apply custom thread configuration & graph optimization
                        intra_threads = getattr(settings, "tts_onnx_intra_threads", 6)
                        opts = ort.SessionOptions()
                        opts.intra_op_num_threads = intra_threads
                        opts.inter_op_num_threads = 1
                        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                        
                        # Re-create InferenceSession with the options
                        providers = kokoro_instance.sess.get_providers()
                        kokoro_instance.sess = ort.InferenceSession(
                            str(self._ONNX_MODEL),
                            sess_options=opts,
                            providers=providers
                        )
                        return kokoro_instance

                    self._onnx_model = await asyncio.to_thread(_init_onnx)
                    self._backend = "onnx"
                    dt = time.time() - t0
                    log.info(f"Kokoro ONNX backend loaded in {dt:.3f}s")

                    # Pre-warm all 3 voices
                    def _prewarm_onnx(model, voices):
                        for v in voices:
                            try:
                                model.create("Hi.", voice=v, speed=1.0, lang="en-us")
                            except Exception:
                                pass

                    t_warm = time.time()
                    await asyncio.to_thread(_prewarm_onnx, self._onnx_model, voices_to_warm)
                    log.info(
                        f"Kokoro ONNX voices pre-warmed "
                        f"({', '.join(voices_to_warm)}) in {time.time()-t_warm:.3f}s"
                    )

                else:
                    # ── PyTorch fallback ───────────────────────────
                    def _init_pipeline():
                        from kokoro import KPipeline
                        return KPipeline(lang_code=self.lang_code)

                    self._pipeline = await asyncio.to_thread(_init_pipeline)
                    self._backend = "pytorch"
                    dt = time.time() - t0
                    log.info(f"Kokoro PyTorch backend loaded in {dt:.3f}s")

                    # Pre-warm all 3 voices
                    def _prewarm_voices(pipeline, voices):
                        for v in voices:
                            try:
                                gen = pipeline("Hi.", voice=v, speed=1.0, split_pattern=r"\n+")
                                for _ in gen:
                                    pass
                            except Exception:
                                pass

                    t_warm = time.time()
                    await asyncio.to_thread(_prewarm_voices, self._pipeline, voices_to_warm)
                    log.info(
                        f"Kokoro PyTorch voices pre-warmed "
                        f"({', '.join(voices_to_warm)}) in {time.time()-t_warm:.3f}s"
                    )

                self._loaded = True
                robot_state.ai.tts_loaded = True
                return True
            except Exception as e:
                log.error(f"Failed to load Kokoro TTS: {e}")
                self._loaded = False
                self._pipeline = None
                self._onnx_model = None
                self._backend = None
                return False

    async def unload(self) -> None:
        """Unload pipeline to free memory if needed."""
        async with self._loading_lock:
            self._pipeline = None
            self._onnx_model = None
            self._backend = None
            self._loaded = False
            robot_state.ai.tts_loaded = False
            log.info("Kokoro TTS pipeline unloaded")

    def _validate_text(self, text: str) -> str:
        """Validate input text for synthesis."""
        if not isinstance(text, str):
            raise ValueError(f"Text must be a string, got {type(text).__name__}")
        clean = text.strip()
        if not clean:
            raise ValueError("Text cannot be empty or whitespace only")
        if len(clean) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Text length ({len(clean)}) exceeds maximum allowed ({MAX_TEXT_LENGTH} characters)"
            )
        return clean

    def _resolve_voice_and_speed(
        self, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> tuple[str, float]:
        """Resolve and validate voice ID and speed factor."""
        resolved_voice = voice or voice_manager.get_current_voice()
        if not is_valid_voice(resolved_voice):
            raise ValueError(f"Unknown or invalid voice ID '{resolved_voice}'")

        if speed is not None:
            if not isinstance(speed, (int, float)) or speed < MIN_TTS_SPEED or speed > MAX_TTS_SPEED:
                raise ValueError(
                    f"Speed {speed} out of safe range [{MIN_TTS_SPEED}, {MAX_TTS_SPEED}]"
                )
            resolved_speed = float(speed)
        else:
            resolved_speed = voice_manager.get_speed()

        return resolved_voice, resolved_speed

    @staticmethod
    def verbalize_numbers_and_symbols(text: str) -> str:
        """
        Normalize numbers and math symbols into natural, spoken English words
        for crystal-clear Kokoro neural TTS pronunciation.
        Examples:
          '13,350,000' -> 'thirteen million three hundred fifty thousand'
          '32,300' -> 'thirty-two thousand three hundred'
          '1500 * 8900 = 13,350,000' -> 'one thousand five hundred times eight thousand nine hundred equals thirteen million three hundred fifty thousand'
        """
        if not text:
            return ""

        units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                 "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                 "seventeen", "eighteen", "nineteen"]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

        def int_to_words(n: int) -> str:
            if n == 0:
                return "zero"
            if n < 0:
                return f"minus {int_to_words(abs(n))}"

            parts = []
            if n >= 1_000_000_000_000:
                parts.append(f"{int_to_words(n // 1_000_000_000_000)} trillion")
                n %= 1_000_000_000_000
            if n >= 1_000_000_000:
                parts.append(f"{int_to_words(n // 1_000_000_000)} billion")
                n %= 1_000_000_000
            if n >= 1_000_000:
                parts.append(f"{int_to_words(n // 1_000_000)} million")
                n %= 1_000_000
            if n >= 1_000:
                parts.append(f"{int_to_words(n // 1_000)} thousand")
                n %= 1_000
            if n >= 100:
                parts.append(f"{units[n // 100]} hundred")
                n %= 100
            if n >= 20:
                t = tens[n // 10]
                u = units[n % 10]
                parts.append(f"{t}-{u}" if u else t)
            elif n > 0:
                parts.append(units[n])

            return " ".join(parts)

        # 1. Replace math symbols with spoken words
        s = text
        s = re.sub(r"\s*[\*×]\s*", " times ", s)
        s = re.sub(r"\s*=\s*", " equals ", s)
        s = re.sub(r"(\d+)\s*\/\s*(\d+)", r"\1 divided by \2", s)
        s = re.sub(r"\s*\+\s*", " plus ", s)
        s = re.sub(r"(\d+)\s*%", r"\1 percent", s)

        # 2. Convert comma-separated numbers and standalone integers
        def replace_num_match(m):
            raw = m.group(0).replace(",", "")
            # Preserve time formats like 3:11
            if ":" in raw:
                return m.group(0)
            # Handle decimals
            if "." in raw:
                int_part, dec_part = raw.split(".", 1)
                int_words = int_to_words(int(int_part)) if int_part else "zero"
                dec_words = " ".join(units[int(d)] if d.isdigit() and int(d) < 10 else d for d in dec_part)
                return f"{int_words} point {dec_words}"
            try:
                val = int(raw)
                # Keep 4-digit years like 2026 as is (Kokoro pronounces years well) unless in math context
                if 1900 <= val <= 2099 and len(raw) == 4 and "year" in text.lower():
                    return m.group(0)
                return int_to_words(val)
            except Exception:
                return m.group(0)

        # Match numbers with commas (e.g. 13,350,000 or 26,910) or standalone multi-digit numbers
        s = re.sub(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", replace_num_match, s)

        # Normalize extra spaces
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _generate_wav_sync(self, text: str, voice: str, speed: float) -> bytes:
        """Synchronous synthesis — dispatches to ONNX or PyTorch backend."""
        spoken_text = self.verbalize_numbers_and_symbols(text)
        if self._backend == "onnx" and self._onnx_model is not None:
            return self._generate_wav_onnx(spoken_text, voice, speed)
        else:
            return self._generate_wav_pytorch(spoken_text, voice, speed)

    def _generate_wav_onnx(self, text: str, voice: str, speed: float) -> bytes:
        """ONNX synthesis — ~1.5x faster on CPU for short chunks."""
        samples, sr = self._onnx_model.create(text, voice=voice, speed=speed, lang="en-us")
        if samples is None or len(samples) == 0:
            return b""
        out_buf = io.BytesIO()
        sf.write(out_buf, samples, sr, format="WAV", subtype="PCM_16")
        return out_buf.getvalue()

    def _generate_wav_pytorch(self, text: str, voice: str, speed: float) -> bytes:
        """PyTorch synthesis — original Kokoro KPipeline fallback."""
        if self._pipeline is None:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code=self.lang_code)
            self._loaded = True
            self._backend = "pytorch"

        generator = self._pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+")
        audio_chunks = []
        for gs, ps, audio in generator:
            if audio is not None:
                audio_chunks.append(audio)

        if not audio_chunks:
            return b""

        full_audio = np.concatenate(audio_chunks)
        out_buf = io.BytesIO()
        sf.write(out_buf, full_audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return out_buf.getvalue()

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """
        Synthesize text to 24kHz 16-bit PCM WAV audio bytes.
        Does NOT trigger local speaker playback.
        """
        clean_text = self._validate_text(text)
        resolved_voice, resolved_speed = self._resolve_voice_and_speed(voice, speed)

        # Ensure model is loaded
        if not self.is_loaded():
            loaded = await self.load()
            if not loaded:
                log.error("Cannot synthesize: Kokoro TTS failed to load")
                return b""

        try:
            t0 = time.time()
            wav_bytes = await asyncio.to_thread(
                self._generate_wav_sync, clean_text, resolved_voice, resolved_speed
            )
            dt = time.time() - t0
            duration_s = len(wav_bytes) / (SAMPLE_RATE * 2) if wav_bytes else 0
            log.info(
                f"Kokoro synthesized {len(wav_bytes)} bytes ({duration_s:.2f}s) in {dt:.3f}s "
                f"[voice={resolved_voice}, speed={resolved_speed}, backend={self._backend}]"
            )

            # Optional debug logging to file
            if getattr(settings, "tts_save_logs", False) and wav_bytes:
                self._save_debug_audio(wav_bytes, resolved_voice)

            return wav_bytes
        except Exception as e:
            log.error(f"Kokoro synthesis failed: {e}")
            return b""

    async def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> bytes:
        """
        Synthesize text and play through configured audio output.
        Preempts any active speech before starting new speech.
        """
        self.stop()
        wav_bytes = await self.synthesize(text, voice=voice, speed=speed)
        if not wav_bytes:
            return b""

        if getattr(settings, "tts_play_local", True) and self.audio_output:
            robot_state.voice.is_speaking = True
            robot_state.voice.state = "SPEAKING"
            try:
                await self.audio_output.play(wav_bytes, sample_rate=SAMPLE_RATE)
            finally:
                robot_state.voice.is_speaking = False
                if robot_state.voice.state == "SPEAKING":
                    robot_state.voice.state = "IDLE"

        return wav_bytes

    def stop(self) -> None:
        """Stop any active speech audio playback immediately."""
        if self.audio_output:
            self.audio_output.stop()
        robot_state.voice.is_speaking = False
        if robot_state.voice.state == "SPEAKING":
            robot_state.voice.state = "IDLE"
        log.info("KokoroTTSProvider: Speech stopped")


    def _save_debug_audio(self, wav_bytes: bytes, voice: str) -> None:
        """Save synthesized audio for debugging if enabled."""
        try:
            log_dir = PROJECT_ROOT / getattr(settings, "tts_log_path", "./Logs/TTS")
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            file_path = log_dir / f"tts_{timestamp}_{voice}.wav"
            with open(file_path, "wb") as f:
                f.write(wav_bytes)
            log.debug(f"Saved TTS debug audio to {file_path}")
        except Exception as e:
            log.warning(f"Could not save TTS debug audio: {e}")
