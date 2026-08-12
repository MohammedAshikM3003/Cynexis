"""
CYNEXIS — Whisper STT Provider
Real offline, local Speech-to-Text transcription using Faster-Whisper.
"""

import io
import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import soundfile as sf

from core.logger import get_logger
from core.config import settings
from core.state import robot_state
from AI.STT.provider import STTProvider

log = get_logger("whisper_stt")


class WhisperSTTProvider(STTProvider):
    """
    Production local Faster-Whisper Speech-to-Text provider.
    Runs entirely on-device with zero external API or cloud connectivity.
    """

    def __init__(self, model_size: Optional[str] = None, cpu_threads: Optional[int] = None):
        self.model_size = model_size or getattr(settings, "stt_whisper_model", "base.en")
        self.device = getattr(settings, "stt_whisper_device", "cpu")
        self.compute_type = getattr(settings, "stt_whisper_compute_type", "float32")
        self.cpu_threads = cpu_threads or getattr(settings, "stt_whisper_cpu_threads", 4)
        self.beam_size = getattr(settings, "stt_whisper_beam_size", 1)
        self._model = None
        self._loaded = False
        self._loading_lock = asyncio.Lock()
        self.last_inference_metrics: Dict[str, Any] = {}

        # Place model folder directly inside workspace to keep it self-contained
        self.model_path = settings.resolve_path("AI Models/Whisper")
        os.makedirs(self.model_path, exist_ok=True)

        log.info(
            f"WhisperSTTProvider initialized (model={self.model_size}, "
            f"threads={self.cpu_threads}, beam={self.beam_size}, device={self.device}, "
            f"compute={self.compute_type}, path={self.model_path})"
        )

    def is_loaded(self) -> bool:
        """Check if Whisper model is loaded in memory."""
        return self._loaded and self._model is not None

    async def load(self) -> bool:
        """Asynchronously load the Whisper model pipeline."""
        if self.is_loaded():
            return True

        async with self._loading_lock:
            if self.is_loaded():
                return True

            try:
                log.info(f"Loading Faster-Whisper model '{self.model_size}' with {self.cpu_threads} CPU threads...")
                t0 = time.time()

                def _init_model():
                    from faster_whisper import WhisperModel
                    # Load model, downloading to self.model_path if not already present
                    return WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                        cpu_threads=self.cpu_threads,
                        download_root=str(self.model_path)
                    )

                self._model = await asyncio.to_thread(_init_model)
                self._loaded = True
                dt = time.time() - t0
                log.info(f"Faster-Whisper model loaded successfully in {dt:.3f}s")
                robot_state.ai.stt_loaded = True
                return True
            except Exception as e:
                log.error(f"Failed to load Faster-Whisper model: {e}")
                self._loaded = False
                self._model = None
                return False

    async def unload(self) -> None:
        """Unload the model to free memory."""
        async with self._loading_lock:
            self._model = None
            self._loaded = False
            robot_state.ai.stt_loaded = False
            log.info("Faster-Whisper model unloaded")

    async def transcribe(self, audio_data: bytes) -> str:
        """Decodes raw audio bytes (PCM/WAV) and transcribes text using Whisper."""
        if not audio_data:
            return ""

        if not self.is_loaded():
            loaded = await self.load()
            if not loaded:
                log.error("Cannot transcribe: Whisper model failed to load")
                return ""

        try:
            # Decode WAV bytes into normalized float32 numpy array
            audio_file = io.BytesIO(audio_data)
            audio_array, sample_rate = sf.read(audio_file, dtype="float32")

            # Whisper expects mono audio. If stereo, convert to mono by averaging channels
            if len(audio_array.shape) > 1 and audio_array.shape[1] > 1:
                audio_array = np.mean(audio_array, axis=1)

            # Whisper expects 16kHz audio. Resample if necessary using pure numpy interpolation
            if sample_rate != 16000:
                num_samples = int(len(audio_array) * 16000 / sample_rate)
                audio_array = np.interp(
                    np.linspace(0, len(audio_array), num_samples, endpoint=False),
                    np.arange(len(audio_array)),
                    audio_array
                ).astype(np.float32)

            t_whisper_start = time.time()

            def _run_transcription():
                import re
                segments, info = self._model.transcribe(
                    audio_array,
                    beam_size=self.beam_size,
                    language="en",
                    condition_on_previous_text=False,
                    without_timestamps=True,
                    temperature=0.0,
                    initial_prompt="CYNEXIS is an AI-powered robotics platform with ESP32.",
                )
                # Force generator execution in this thread
                text_segments = [seg.text for seg in segments]
                raw_text = "".join(text_segments).strip()
                
                # Phonetic correction for CYNEXIS brand name
                phonetic_patterns = [
                    (r"\b(using syntaxes|the using syntaxes)\b", "CYNEXIS"),
                    (r"\b(syntaxes|synexis|sinexis|synecsis|sin axis|cynaxis|cinaxis|sin access|syn access)\b", "CYNEXIS"),
                ]
                cleaned = raw_text
                for pat, repl in phonetic_patterns:
                    cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)
                return cleaned

            transcript = await asyncio.to_thread(_run_transcription)
            t_whisper_complete = time.time()

            self.last_inference_metrics = {
                "whisper_start": t_whisper_start,
                "whisper_complete": t_whisper_complete,
                "whisper_inference_s": round(t_whisper_complete - t_whisper_start, 3),
                "audio_samples": len(audio_array),
                "audio_duration_s": round(len(audio_array) / 16000.0, 3),
            }

            log.info(f"Whisper STT ({self.last_inference_metrics['whisper_inference_s']}s): '{transcript}'")
            return transcript
        except Exception as e:
            log.error(f"Whisper transcription failed: {e}")
            return ""
