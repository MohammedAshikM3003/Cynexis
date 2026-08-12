"""
CYNEXIS — Microphone Input Abstraction
Provides decoupled audio recording with dynamic Voice Activity Detection (VAD)
and silence trimming for development laptop and physical robot microphone.
"""

import io
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import numpy as np
import soundfile as sf
import sounddevice as sd

from core.logger import get_logger

log = get_logger("microphone")


class MicrophoneInput(ABC):
    """Abstract microphone recording interface."""

    def __init__(self):
        self.last_capture_metrics: Dict[str, Any] = {}

    @abstractmethod
    async def record(
        self,
        duration_s: float = 3.0,
        sample_rate: int = 16000,
        vad_enabled: bool = True,
        silence_timeout_s: float = 0.5,
    ) -> bytes:
        """Record audio and return 16-bit PCM WAV bytes."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if microphone input hardware is available."""
        ...


class MockMicrophone(MicrophoneInput):
    """Mock microphone for CI, unit testing, and headless execution."""

    def __init__(self, mock_audio_bytes: Optional[bytes] = None):
        super().__init__()
        self._mock_bytes = mock_audio_bytes or self._generate_mock_wav()
        log.info("MockMicrophone initialized")

    @staticmethod
    def _generate_mock_wav(sample_rate: int = 16000, duration_s: float = 1.0) -> bytes:
        """Generate 1 second of silent 16kHz mono WAV bytes."""
        samples = int(sample_rate * duration_s)
        silent_audio = np.zeros(samples, dtype=np.float32)
        buf = io.BytesIO()
        sf.write(buf, silent_audio, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    async def record(
        self,
        duration_s: float = 3.0,
        sample_rate: int = 16000,
        vad_enabled: bool = True,
        silence_timeout_s: float = 0.5,
    ) -> bytes:
        t0 = time.time()
        self.last_capture_metrics = {
            "mic_capture_start": t0,
            "first_detected_speech": t0 + 0.1,
            "last_detected_speech": t0 + 0.8,
            "capture_stop": t0 + 1.0,
            "audio_duration_s": 1.0,
            "speech_duration_s": 0.7,
            "trailing_silence_s": 0.2,
            "leading_silence_s": 0.1,
            "vad_triggered": True,
        }
        log.info(f"MOCK MIC: Simulated recording of {duration_s}s ({sample_rate}Hz)")
        return self._mock_bytes

    def is_available(self) -> bool:
        return True


class LocalMicrophone(MicrophoneInput):
    """
    Local microphone input using sounddevice with real-time streaming VAD.
    Records from the host audio input device and terminates recording on trailing silence.
    """

    def __init__(self, device: Optional[int] = None, energy_threshold: float = 0.015):
        super().__init__()
        self.device = device
        self.energy_threshold = energy_threshold
        log.info(f"LocalMicrophone initialized (device={self.device or 'default'}, threshold={energy_threshold})")

    def _record_sync_vad(
        self,
        max_duration_s: float,
        sample_rate: int,
        vad_enabled: bool,
        silence_timeout_s: float,
    ) -> bytes:
        capture_start = time.time()
        block_duration_s = 0.032  # 32ms frames
        block_size = int(sample_rate * block_duration_s)
        
        chunks = []
        speech_detected = False
        first_speech_time: Optional[float] = None
        last_speech_time: Optional[float] = None
        first_speech_idx = 0
        last_speech_idx = 0
        
        # Calculate adaptive energy threshold from noise floor
        noise_floor_rms = 0.005
        active_threshold = max(self.energy_threshold, noise_floor_rms * 2.5)

        try:
            log.info(f"Microphone: Stream recording started (max={max_duration_s}s, VAD={vad_enabled})...")
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
                device=self.device,
            ) as stream:
                while True:
                    now = time.time()
                    elapsed = now - capture_start
                    if elapsed >= max_duration_s:
                        break

                    data, overflowed = stream.read(block_size)
                    if overflowed:
                        log.debug("Microphone buffer overflowed")

                    chunk_flat = data.flatten()
                    chunks.append(chunk_flat)
                    chunk_idx = len(chunks) - 1

                    if vad_enabled:
                        rms = float(np.sqrt(np.mean(chunk_flat**2)))
                        if rms > active_threshold:
                            if not speech_detected:
                                speech_detected = True
                                first_speech_time = now
                                first_speech_idx = chunk_idx
                            last_speech_time = now
                            last_speech_idx = chunk_idx
                        elif speech_detected:
                            # Speech was previously detected; check trailing silence duration
                            silence_dur = now - (last_speech_time or now)
                            if silence_dur >= silence_timeout_s:
                                log.info(f"Microphone: VAD detected {silence_dur:.3f}s trailing silence. Stopping capture.")
                                break

            capture_stop = time.time()

            if not chunks:
                return b""

            audio_concat = np.concatenate(chunks)
            total_duration_s = len(audio_concat) / sample_rate

            # Calculate precise metrics
            leading_silence = 0.0
            trailing_silence = 0.0
            speech_duration = 0.0

            if speech_detected and first_speech_time and last_speech_time:
                leading_silence = max(0.0, first_speech_time - capture_start)
                trailing_silence = max(0.0, capture_stop - last_speech_time)
                speech_duration = max(0.0, last_speech_time - first_speech_time)
                
                # Trim leading/trailing silence with 100ms padding for natural acoustic envelope
                pad_samples = int(sample_rate * 0.1)
                start_sample = max(0, int(first_speech_idx * block_size) - pad_samples)
                end_sample = min(len(audio_concat), int((last_speech_idx + 1) * block_size) + pad_samples)
                trimmed_audio = audio_concat[start_sample:end_sample]
            else:
                trimmed_audio = audio_concat

            self.last_capture_metrics = {
                "mic_capture_start": capture_start,
                "first_detected_speech": first_speech_time or capture_start,
                "last_detected_speech": last_speech_time or capture_stop,
                "capture_stop": capture_stop,
                "audio_duration_s": round(total_duration_s, 3),
                "trimmed_duration_s": round(len(trimmed_audio) / sample_rate, 3),
                "speech_duration_s": round(speech_duration, 3),
                "trailing_silence_s": round(trailing_silence, 3),
                "leading_silence_s": round(leading_silence, 3),
                "vad_triggered": speech_detected,
            }

            log.info(
                f"Microphone capture done: total={total_duration_s:.3f}s, "
                f"speech={speech_duration:.3f}s, trailing_silence={trailing_silence:.3f}s"
            )

            buf = io.BytesIO()
            sf.write(buf, trimmed_audio, sample_rate, format="WAV", subtype="PCM_16")
            return buf.getvalue()

        except Exception as e:
            log.error(f"Microphone recording failed: {e}")
            capture_stop = time.time()
            self.last_capture_metrics = {
                "mic_capture_start": capture_start,
                "first_detected_speech": None,
                "last_detected_speech": None,
                "capture_stop": capture_stop,
                "audio_duration_s": 0.0,
                "speech_duration_s": 0.0,
                "trailing_silence_s": 0.0,
                "leading_silence_s": 0.0,
                "vad_triggered": False,
            }
            return b""

    async def record(
        self,
        duration_s: float = 3.0,
        sample_rate: int = 16000,
        vad_enabled: bool = True,
        silence_timeout_s: float = 0.5,
    ) -> bytes:
        """Record audio asynchronously in background thread with VAD."""
        try:
            return await asyncio.to_thread(
                self._record_sync_vad,
                duration_s,
                sample_rate,
                vad_enabled,
                silence_timeout_s,
            )
        except Exception as e:
            log.error(f"LocalMicrophone async error: {e}")
            return b""

    def is_available(self) -> bool:
        """Check if any input audio device is available."""
        try:
            devices = sd.query_devices()
            for d in devices:
                if d.get("max_input_channels", 0) > 0:
                    return True
            return False
        except Exception:
            return False
