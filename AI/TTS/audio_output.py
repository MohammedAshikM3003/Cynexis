"""
CYNEXIS — Audio Output Abstraction
Provides decoupled audio playback for laptop speaker and robot audio hardware.
"""

import io
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
import soundfile as sf
import sounddevice as sd

from core.logger import get_logger

log = get_logger("audio_output")


class AudioOutput(ABC):
    """Abstract audio output device interface."""

    @abstractmethod
    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        """Play audio bytes (WAV formatted or PCM). Returns True if played successfully."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if audio output device is available."""
        ...

    def stop(self) -> None:
        """Stop any active audio playback immediately."""
        pass



class MockAudioOutput(AudioOutput):
    """Mock audio output — logs playback simulation without touching audio hardware."""

    def __init__(self):
        log.info("MockAudioOutput initialized")

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        if not audio_data:
            log.debug("MockAudioOutput: Received empty audio bytes, skipping playback.")
            return True
        log.info(f"MOCK AUDIO: Simulated playback of {len(audio_data)} bytes ({sample_rate}Hz)")
        return True

    def is_available(self) -> bool:
        return True

    def stop(self) -> None:
        log.info("MockAudioOutput: Playback stopped")


class LocalAudioOutput(AudioOutput):
    """
    Local audio output — plays generated audio through the computer/robot default audio device.
    Uses non-blocking worker thread via asyncio.to_thread so event loop is never stalled.
    """

    def __init__(self, device: Optional[int] = None):
        self.device = device
        log.info(f"LocalAudioOutput initialized (device={self.device or 'default'})")

    def _play_sync(self, audio_data: bytes, sample_rate: int) -> bool:
        try:
            # Read WAV bytes with soundfile
            data, fs = sf.read(io.BytesIO(audio_data), dtype="float32")
            sd.play(data, samplerate=fs, device=self.device)
            sd.wait()
            return True
        except Exception as e:
            log.error(f"LocalAudioOutput playback failed: {e}")
            return False

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        """Play audio bytes asynchronously in background thread."""
        if not audio_data:
            log.warning("LocalAudioOutput: Cannot play empty audio data.")
            return False

        try:
            # Stop any ongoing playback before starting new speech
            self.stop()
            return await asyncio.to_thread(self._play_sync, audio_data, sample_rate)
        except Exception as e:
            log.error(f"Audio playback error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if any audio output device is detected."""
        try:
            devices = sd.query_devices()
            return len(devices) > 0
        except Exception:
            return False

    def stop(self) -> None:
        """Immediately stop any active sounddevice playback."""
        try:
            sd.stop()
            log.debug("LocalAudioOutput: sd.stop() executed")
        except Exception as e:
            log.warning(f"Error stopping audio playback: {e}")


# Centralized bypass switch for clean A/B testing of loudness processor
LOUDNESS_PROCESSING_ENABLED = True


class RoverAudioOutput(AudioOutput):
    """
    Rover audio output — streams synthesized Kokoro TTS audio (24kHz 16-bit PCM)
    over UDP to the Rover ESP32 MAX98357A I2S 3W speaker driver.
    """

    CYNEXIS_AUDIO_MAGIC = b"CY"

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        import socket
        from core.config import settings

        self.host = host or getattr(settings, "rover_audio_host", "255.255.255.255")
        self.port = port if port is not None else getattr(settings, "rover_audio_port", 50006)
        self.sequence_num: int = 0
        log.info(f"RoverAudioOutput initialized (host='{self.host}', port={self.port})")

    def _send_udp_stream_sync(self, audio_data: bytes, sample_rate: int) -> bool:
        import socket
        import struct
        import time
        import numpy as np

        if not audio_data:
            return False

        try:
            # Parse WAV header if present, extract raw PCM-16 mono bytes
            if len(audio_data) >= 44 and audio_data[:4] == b"RIFF":
                raw_pcm = audio_data[44:]
            else:
                raw_pcm = audio_data

            # ── CYNEXIS STAGE A ACTIVE-SPEECH LOUDNESS PROCESSOR ──
            if raw_pcm and LOUDNESS_PROCESSING_ENABLED:
                pcm_samples = np.frombuffer(raw_pcm, dtype=np.int16)
                n = len(pcm_samples)

                if n > 0:
                    try:
                        # Float64 working copy (never mutate original pcm_samples buffer)
                        work = pcm_samples.astype(np.float64)

                        # 1. DC Offset Removal (mean subtraction)
                        work -= np.mean(work)

                        original_peak = int(np.max(np.abs(work)))
                        full_rms = float(np.sqrt(np.mean(work ** 2)))

                        # 2. Active-Speech Measurement (20ms frames, 10ms hop at 24kHz)
                        FRAME_MS = 20.0
                        HOP_MS = 10.0
                        sr_val = float(sample_rate) if sample_rate > 0 else 24000.0
                        frame_len = int(round((FRAME_MS / 1000.0) * sr_val))  # 480 samples
                        hop_len = int(round((HOP_MS / 1000.0) * sr_val))      # 240 samples

                        # Mandatory short-buffer protection
                        if n < frame_len:
                            frame_rms = np.array([np.sqrt(np.mean(work ** 2))])
                        else:
                            frames = np.lib.stride_tricks.sliding_window_view(work, frame_len)[::hop_len]
                            frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))

                        active_floor = max(0.08 * (frame_rms.max() if len(frame_rms) else 0.0), 150.0)
                        active_mask = frame_rms > active_floor

                        if np.any(active_mask):
                            active_rms = float(np.sqrt(np.mean(frame_rms[active_mask] ** 2)))
                            active_percentage = float(100.0 * np.sum(active_mask) / len(frame_rms))
                        else:
                            active_rms = 0.0
                            active_percentage = 0.0

                        # 3. Static Loudness Gain (TARGET_ACTIVE_RMS = 12000.0, MAX_GAIN = 5.0)
                        TARGET_ACTIVE_RMS = 12000.0
                        MAX_GAIN = 5.0

                        if active_rms > 0:
                            raw_gain = TARGET_ACTIVE_RMS / active_rms
                            loudness_gain = min(MAX_GAIN, raw_gain)
                            gain_capped = raw_gain > MAX_GAIN
                        else:
                            loudness_gain = 1.0
                            gain_capped = False

                        work *= loudness_gain
                        pre_comp_peak = float(np.max(np.abs(work)))

                        # 4. Real Envelope-Following Compressor (-10dBFS Thresh, 2:1 Ratio, 10dB Knee, 10ms Att, 150ms Rel)
                        COMP_THRESHOLD_DB = -10.0
                        COMP_RATIO = 2.0
                        COMP_KNEE_DB = 10.0
                        COMP_ATTACK_MS = 10.0
                        COMP_RELEASE_MS = 150.0

                        if n < frame_len:
                            comp_frame_rms = np.array([np.sqrt(np.mean(work ** 2))])
                        else:
                            comp_frames = np.lib.stride_tricks.sliding_window_view(work, frame_len)[::hop_len]
                            comp_frame_rms = np.sqrt(np.mean(comp_frames ** 2, axis=1))

                        level_db = 20.0 * np.log10(np.maximum(comp_frame_rms, 1e-9) / 32767.0)
                        d = level_db - COMP_THRESHOLD_DB

                        gain_db = np.zeros_like(level_db)
                        knee_half = COMP_KNEE_DB / 2.0
                        for k in range(len(level_db)):
                            dk = d[k]
                            if dk <= -knee_half:
                                gain_db[k] = 0.0
                            elif abs(dk) < knee_half:
                                gain_db[k] = -(1.0 - 1.0 / COMP_RATIO) * ((dk + knee_half) ** 2) / (2.0 * COMP_KNEE_DB)
                            else:
                                gain_db[k] = -(1.0 - 1.0 / COMP_RATIO) * dk

                        alpha_a = np.exp(-HOP_MS / COMP_ATTACK_MS)
                        alpha_r = np.exp(-HOP_MS / COMP_RELEASE_MS)

                        smoothed_gain_db = np.zeros_like(gain_db)
                        curr = gain_db[0] if len(gain_db) > 0 else 0.0
                        for k in range(len(gain_db)):
                            target = gain_db[k]
                            if target < curr:  # Gain reduction becoming more negative -> Attack
                                curr = alpha_a * curr + (1.0 - alpha_a) * target
                            else:              # Recovery towards 0 -> Release
                                curr = alpha_r * curr + (1.0 - alpha_r) * target
                            smoothed_gain_db[k] = curr

                        linear_gain = 10.0 ** (smoothed_gain_db / 20.0)

                        if len(gain_db) == 1:
                            sample_gain = np.full(n, linear_gain[0])
                        else:
                            frame_centers = np.arange(len(gain_db)) * hop_len + (frame_len / 2.0)
                            sample_indices = np.arange(n)
                            sample_gain = np.interp(sample_indices, frame_centers, linear_gain)

                        work *= sample_gain
                        post_comp_peak = float(np.max(np.abs(work)))
                        max_gain_reduction_db = float(np.min(smoothed_gain_db)) if len(smoothed_gain_db) else 0.0

                        # 5. Automatic Makeup Gain (Active RMS recovery up to MAX_MAKEUP_DB = 6.0 dB, min 1.0x)
                        PEAK_LIMIT = 30000.0
                        MAX_MAKEUP_DB = 6.0

                        if n < frame_len:
                            post_comp_frame_rms = np.array([np.sqrt(np.mean(work ** 2))])
                        else:
                            post_comp_frames = np.lib.stride_tricks.sliding_window_view(work, frame_len)[::hop_len]
                            post_comp_frame_rms = np.sqrt(np.mean(post_comp_frames ** 2, axis=1))

                        post_comp_active_floor = max(0.08 * (post_comp_frame_rms.max() if len(post_comp_frame_rms) else 0.0), 150.0)
                        post_comp_active_mask = post_comp_frame_rms > post_comp_active_floor
                        if np.any(post_comp_active_mask):
                            post_comp_active_rms = float(np.sqrt(np.mean(post_comp_frame_rms[post_comp_active_mask] ** 2)))
                        else:
                            post_comp_active_rms = 0.0

                        if post_comp_active_rms > 0:
                            needed = TARGET_ACTIVE_RMS / post_comp_active_rms
                        else:
                            needed = 1.0

                        makeup_cap = 10.0 ** (MAX_MAKEUP_DB / 20.0)
                        makeup = max(1.0, min(needed, makeup_cap))
                        makeup_capped = needed > makeup_cap

                        work *= makeup

                        # 6. Fast Peak Limiter (4ms Frame, 1ms Hop, Ceiling=30000, 0.5ms Att, 10ms Rel)
                        LIM_FRAME_MS = 4.0
                        LIM_HOP_MS = 1.0
                        LIM_CEILING = 30000.0
                        LIM_ATTACK_MS = 0.5
                        LIM_RELEASE_MS = 10.0

                        lim_frame_len = int(round((LIM_FRAME_MS / 1000.0) * sr_val))  # 96 samples
                        lim_hop_len = int(round((LIM_HOP_MS / 1000.0) * sr_val))      # 24 samples

                        if n < lim_frame_len:
                            lim_frame_peaks = np.array([np.max(np.abs(work))])
                        else:
                            lim_frames = np.lib.stride_tricks.sliding_window_view(np.abs(work), lim_frame_len)[::lim_hop_len]
                            lim_frame_peaks = np.max(lim_frames, axis=1)

                        req_gain = np.minimum(1.0, LIM_CEILING / np.maximum(lim_frame_peaks, 1e-9))
                        req_gain_db = 20.0 * np.log10(np.maximum(req_gain, 1e-9))

                        lim_alpha_a = np.exp(-LIM_HOP_MS / LIM_ATTACK_MS)
                        lim_alpha_r = np.exp(-LIM_HOP_MS / LIM_RELEASE_MS)

                        lim_smoothed_db = np.zeros_like(req_gain_db)
                        lim_curr = req_gain_db[0] if len(req_gain_db) > 0 else 0.0
                        for k in range(len(req_gain_db)):
                            target = req_gain_db[k]
                            if target < lim_curr:
                                lim_curr = lim_alpha_a * lim_curr + (1.0 - lim_alpha_a) * target
                            else:
                                lim_curr = lim_alpha_r * lim_curr + (1.0 - lim_alpha_r) * target
                            lim_smoothed_db[k] = lim_curr

                        lim_linear_gain = 10.0 ** (lim_smoothed_db / 20.0)

                        if len(req_gain_db) == 1:
                            lim_sample_gain = np.full(n, lim_linear_gain[0])
                        else:
                            lim_centers = np.arange(len(req_gain_db)) * lim_hop_len + (lim_frame_len / 2.0)
                            sample_indices = np.arange(n)
                            lim_sample_gain = np.interp(sample_indices, lim_centers, lim_linear_gain)

                        work *= lim_sample_gain
                        post_lim_peak = float(np.max(np.abs(work)))
                        lim_max_gr_db = float(np.min(lim_smoothed_db)) if len(lim_smoothed_db) else 0.0

                        # 7. Exact Final Peak Safety Check (Must NEVER increase signal)
                        final_peak_now = float(np.max(np.abs(work))) if work.size else 0.0
                        if final_peak_now > PEAK_LIMIT:
                            work *= (PEAK_LIMIT / final_peak_now)

                        # Non-finite check safety
                        if not np.all(np.isfinite(work)):
                            raise ValueError("DSP produced non-finite values (NaN/Inf)")

                        # Int16 conversion & clipping audit
                        clipped_count = int(np.sum((work < -32768) | (work > 32767)))
                        scaled_samples = np.clip(work, -32768, 32767).astype(np.int16)
                        assert len(scaled_samples) == len(pcm_samples), "Sample count changed during DSP!"

                        # Final Active RMS & Crest calculation
                        final_work = scaled_samples.astype(np.float64)
                        final_peak = int(np.max(np.abs(final_work))) if final_work.size else 0
                        if n < frame_len:
                            final_frame_rms = np.array([np.sqrt(np.mean(final_work ** 2))])
                        else:
                            final_frames = np.lib.stride_tricks.sliding_window_view(final_work, frame_len)[::hop_len]
                            final_frame_rms = np.sqrt(np.mean(final_frames ** 2, axis=1))

                        final_active_floor = max(0.08 * (final_frame_rms.max() if len(final_frame_rms) else 0.0), 150.0)
                        final_active_mask = final_frame_rms > final_active_floor
                        if np.any(final_active_mask):
                            final_active_rms = float(np.sqrt(np.mean(final_frame_rms[final_active_mask] ** 2)))
                        else:
                            final_active_rms = 0.0

                        final_crest_db = 20.0 * np.log10(final_peak / max(final_active_rms, 1e-9))

                        raw_peak_db = 20.0 * np.log10(max(original_peak, 1) / 32767.0)
                        raw_rms_db = 20.0 * np.log10(max(full_rms, 1e-9) / 32767.0)
                        active_rms_db = 20.0 * np.log10(max(active_rms, 1e-9) / 32767.0)
                        final_active_rms_db = 20.0 * np.log10(max(final_active_rms, 1e-9) / 32767.0)

                        print(
                            f"[TTS PCM] Raw Peak: {original_peak} ({raw_peak_db:.1f} dB) | "
                            f"Raw RMS: {full_rms:.1f} ({raw_rms_db:.1f} dB) | "
                            f"Active RMS: {active_rms:.1f} ({active_rms_db:.1f} dB) | "
                            f"Active: {active_percentage:.2f}% | "
                            f"Gain: {loudness_gain:.2f}x | "
                            f"GainCapped: {'YES' if gain_capped else 'NO'} | "
                            f"PreComp Peak: {pre_comp_peak:.0f} | "
                            f"Comp GR max: {max_gain_reduction_db:.1f} dB | "
                            f"PostComp Peak: {post_comp_peak:.0f} | "
                            f"Makeup: {makeup:.2f}x | "
                            f"MakeupCapped: {'YES' if makeup_capped else 'NO'} | "
                            f"PostLim Peak: {post_lim_peak:.0f} | "
                            f"Lim GR max: {lim_max_gr_db:.1f} dB | "
                            f"Final Peak: {final_peak} | "
                            f"Final Active RMS: {final_active_rms:.1f} ({final_active_rms_db:.1f} dB) | "
                            f"Final Crest: {final_crest_db:.1f} dB | "
                            f"Clipped: {clipped_count} | "
                            f"Samples: {len(pcm_samples)} -> {len(scaled_samples)}",
                            flush=True
                        )

                        raw_pcm = scaled_samples.tobytes()

                    except Exception as dsp_err:
                        log.warning(f"Loudness processor fallback triggered: {dsp_err}")
                        scaled_samples = np.clip(pcm_samples, -32768, 32767).astype(np.int16)
                        raw_pcm = scaled_samples.tobytes()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if self.host.endswith(".255") or self.host == "255.255.255.255":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            chunk_size = 1000  # 500 samples of 16-bit PCM per packet (20.8ms)
            total_sent = 0
            sr = float(sample_rate) if sample_rate > 0 else 24000.0

            # Absolute baseline timestamp for drift-free real-time stream scheduling
            next_target_time = time.perf_counter()

            for i in range(0, len(raw_pcm), chunk_size):
                chunk = raw_pcm[i:i + chunk_size]
                if not chunk:
                    continue

                self.sequence_num = (self.sequence_num + 1) & 0xFFFF
                # 8-byte header: [Magic 2B 'CY'][Seq uint16][Rate uint16][Length uint16]
                header = struct.pack("<2sHHH", self.CYNEXIS_AUDIO_MAGIC, self.sequence_num, int(sr), len(chunk))
                packet = header + chunk
                sock.sendto(packet, (self.host, self.port))
                total_sent += len(chunk)

                # Real-time pacing based on actual mono sample count in this chunk
                num_samples = len(chunk) // 2
                chunk_duration_s = num_samples / sr
                next_target_time += chunk_duration_s

                # High-precision drift-free pacing: yield if far away, micro-poll near target
                while True:
                    now = time.perf_counter()
                    remaining_s = next_target_time - now
                    if remaining_s <= 0:
                        break
                    if remaining_s > 0.002:
                        time.sleep(remaining_s - 0.001)  # Coarse yield up to 1ms before target
                    else:
                        time.sleep(0.0001)  # Micro-yield (100μs) to prevent 100% CPU lock

            sock.close()
            log.info(f"RoverAudioOutput: Sent {total_sent} PCM bytes ({len(raw_pcm)}B total) to {self.host}:{self.port}")
            return True
        except Exception as e:
            log.error(f"RoverAudioOutput UDP streaming failed: {e}")
            return False

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        """Stream audio bytes to Rover ESP32 asynchronously."""
        if not audio_data:
            return False
        return await asyncio.to_thread(self._send_udp_stream_sync, audio_data, sample_rate)

    def is_available(self) -> bool:
        return True


class CompositeAudioOutput(AudioOutput):
    """
    Composite audio output — plays audio on both laptop local speakers
    and streams to Rover ESP32 speaker concurrently.
    """

    def __init__(self, outputs: list[AudioOutput]):
        self.outputs = outputs
        log.info(f"CompositeAudioOutput initialized with {len(outputs)} target outputs.")

    async def play(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
        if not audio_data:
            return False
        results = await asyncio.gather(
            *[out.play(audio_data, sample_rate) for out in self.outputs],
            return_exceptions=True
        )
        return any(r is True for r in results)

    def is_available(self) -> bool:
        return any(out.is_available() for out in self.outputs)

    def stop(self) -> None:
        for out in self.outputs:
            out.stop()

