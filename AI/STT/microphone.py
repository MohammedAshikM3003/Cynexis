"""
CYNEXIS — Microphone Input Abstraction
Provides decoupled audio recording with dynamic Voice Activity Detection (VAD)
and silence trimming for development laptop and physical robot microphone.
"""

import io
import time
import struct
import socket
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


# ============================================================
# NETWORK UDP MICROPHONE (INMP441 / LEFT ESP32)
# ============================================================

CYNEXIS_AUDIO_MAGIC = b"CY"
AUDIO_HEADER_SIZE = 8


class NetworkMicrophone(MicrophoneInput):
    """
    Receives raw 16kHz 16-bit mono PCM UDP audio streams from the Left ESP32 (INMP441),
    buffers frames with bounded memory and sequence tracking, applies VAD,
    and returns standard WAV bytes for the frozen VoicePipeline.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        buffer_seconds: float = 10.0,
        energy_threshold: float = 0.015,
    ):
        super().__init__()
        from core.config import settings
        self.host = host or getattr(settings, "udp_audio_host", "0.0.0.0")
        self.port = port if port is not None else getattr(settings, "udp_audio_port", 50005)
        self.buffer_seconds = buffer_seconds
        self.energy_threshold = energy_threshold
        self.max_buffer_bytes = int(16000 * 2 * self.buffer_seconds)

        self._running = False
        self._socket: Optional[socket.socket] = None
        self._buffer = bytearray()
        self._lock = asyncio.Lock()

        # Statistics
        self.packets_received: int = 0
        self.packets_dropped: int = 0
        self.bytes_received: int = 0
        self.last_packet_timestamp: Optional[float] = None
        self._last_sequence: Optional[int] = None

        log.info(
            f"NetworkMicrophone initialized (host='{self.host}', port={self.port}, "
            f"buffer_cap={self.max_buffer_bytes}B, threshold={self.energy_threshold})"
        )

    @staticmethod
    def parse_packet(data: bytes) -> Optional[tuple[int, int, bytes]]:
        """
        Validates and parses a raw UDP audio packet.
        Header Format: 8 bytes
          [0:2] Magic 'CY' (0x43, 0x59)
          [2:4] Sequence (uint16 little-endian)
          [4:6] Sample Rate (uint16 little-endian, e.g. 16000)
          [6:8] Payload Length (uint16 little-endian)
        Payload: 16-bit signed PCM mono samples
        """
        if len(data) < AUDIO_HEADER_SIZE:
            return None

        try:
            magic, seq, rate, payload_len = struct.unpack("<2sHHH", data[:AUDIO_HEADER_SIZE])
        except struct.error:
            return None

        if magic != CYNEXIS_AUDIO_MAGIC:
            return None

        if payload_len != (len(data) - AUDIO_HEADER_SIZE):
            return None

        if payload_len == 0 or (payload_len % 2) != 0:
            return None  # Must represent whole 16-bit PCM samples

        pcm_bytes = data[AUDIO_HEADER_SIZE:]
        return seq, rate, pcm_bytes

    def ingest_packet(self, data: bytes) -> bool:
        """
        Synchronously parses and ingests an incoming UDP packet into the bounded ring buffer.
        """
        parsed = self.parse_packet(data)
        if not parsed:
            return False

        seq, rate, pcm_data = parsed

        # Sequence gap / packet loss tracking
        if self._last_sequence is not None:
            expected = (self._last_sequence + 1) & 0xFFFF
            gap = (seq - expected) & 0xFFFF
            if 0 < gap < 1000:
                self.packets_dropped += gap

        self._last_sequence = seq
        self.packets_received += 1
        self.bytes_received += len(pcm_data)
        self.last_packet_timestamp = time.time()

        # Append to bounded buffer
        self._buffer.extend(pcm_data)
        if len(self._buffer) > self.max_buffer_bytes:
            excess = len(self._buffer) - self.max_buffer_bytes
            del self._buffer[:excess]

        return True

    def clear_buffer(self) -> None:
        """Clear existing audio buffer."""
        self._buffer.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return audio transport statistics."""
        return {
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
            "bytes_received": self.bytes_received,
            "last_packet_timestamp": self.last_packet_timestamp,
            "buffer_bytes": len(self._buffer),
        }

    async def record(
        self,
        duration_s: float = 3.0,
        sample_rate: int = 16000,
        vad_enabled: bool = True,
        silence_timeout_s: float = 0.5,
    ) -> bytes:
        """
        Listens to the incoming network audio stream for up to duration_s,
        applies dynamic VAD, and returns 16-bit PCM WAV bytes.
        """
        capture_start = time.time()
        block_duration_s = 0.032  # 32ms frames
        block_bytes = int(sample_rate * block_duration_s * 2)  # 16-bit = 2 bytes/sample

        # Create or reuse UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)

        bound = False
        try:
            sock.bind((self.host, self.port))
            bound = True
            log.info(f"NetworkMicrophone listening on {self.host}:{self.port}...")
        except Exception as e:
            log.warning(f"NetworkMicrophone socket bind warning ({self.host}:{self.port}): {e}")

        # Clear prior buffer for fresh recording
        self.clear_buffer()

        chunks_pcm = []
        speech_detected = False
        first_speech_time: Optional[float] = None
        last_speech_time: Optional[float] = None
        first_speech_idx = 0
        last_speech_idx = 0

        noise_floor_rms = 0.005
        active_threshold = max(self.energy_threshold, noise_floor_rms * 2.5)

        loop = asyncio.get_running_loop()

        try:
            while True:
                now = time.time()
                elapsed = now - capture_start
                if elapsed >= duration_s:
                    break

                # Non-blocking receive from UDP socket if bound
                if bound:
                    try:
                        while True:
                            packet_data, _ = sock.recvfrom(2048)
                            self.ingest_packet(packet_data)
                    except (BlockingIOError, InterruptedError):
                        pass
                    except Exception as err:
                        log.debug(f"NetworkMicrophone socket recv: {err}")

                # Process available data in 32ms blocks
                while len(self._buffer) >= block_bytes:
                    raw_frame = bytes(self._buffer[:block_bytes])
                    del self._buffer[:block_bytes]

                    # Convert 16-bit PCM to float32 for RMS energy calculation
                    audio_frame = np.frombuffer(raw_frame, dtype=np.int16).astype(np.float32) / 32768.0
                    chunks_pcm.append(raw_frame)
                    chunk_idx = len(chunks_pcm) - 1

                    if vad_enabled:
                        rms = float(np.sqrt(np.mean(audio_frame**2))) if len(audio_frame) > 0 else 0.0
                        if rms > active_threshold:
                            if not speech_detected:
                                speech_detected = True
                                first_speech_time = now
                                first_speech_idx = chunk_idx
                            last_speech_time = now
                            last_speech_idx = chunk_idx
                        elif speech_detected:
                            silence_dur = now - (last_speech_time or now)
                            if silence_dur >= silence_timeout_s:
                                log.info(f"NetworkMicrophone: VAD detected {silence_dur:.3f}s trailing silence.")
                                elapsed = duration_s  # Break outer loop
                                break

                if elapsed >= duration_s:
                    break

                await asyncio.sleep(0.01)

        finally:
            if bound:
                sock.close()

        capture_stop = time.time()

        if not chunks_pcm:
            log.warning("NetworkMicrophone: No audio data captured from network.")
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
                "packets_received": self.packets_received,
                "packets_dropped": self.packets_dropped,
            }
            return b""

        full_raw_pcm = b"".join(chunks_pcm)
        audio_np = np.frombuffer(full_raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        total_duration_s = len(audio_np) / sample_rate

        leading_silence = 0.0
        trailing_silence = 0.0
        speech_duration = 0.0

        if speech_detected and first_speech_time and last_speech_time:
            leading_silence = max(0.0, first_speech_time - capture_start)
            trailing_silence = max(0.0, capture_stop - last_speech_time)
            speech_duration = max(0.0, last_speech_time - first_speech_time)

            pad_samples = int(sample_rate * 0.1)
            start_sample = max(0, int(first_speech_idx * (block_bytes // 2)) - pad_samples)
            end_sample = min(len(audio_np), int((last_speech_idx + 1) * (block_bytes // 2)) + pad_samples)
            trimmed_audio = audio_np[start_sample:end_sample]
        else:
            trimmed_audio = audio_np

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
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
        }

        # Format output as standard PCM_16 WAV
        buf = io.BytesIO()
        sf.write(buf, trimmed_audio, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    def is_available(self) -> bool:
        """Returns True if the network microphone is ready to receive."""
        return True
