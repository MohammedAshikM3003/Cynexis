"""
CYNEXIS — Live Kokoro Voice & Speaker Playback Test
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AI.TTS.kokoro import KokoroTTSProvider
from AI.TTS.audio_output import LocalAudioOutput
from AI.TTS.voice_manager import voice_manager


async def main():
    print("=" * 60)
    print("CYNEXIS LOCAL KOKORO TTS TEST")
    print("=" * 60)

    audio_out = LocalAudioOutput()
    print(f"Audio output available: {audio_out.is_available()}")

    tts = KokoroTTSProvider(audio_output=audio_out)

    t0 = time.time()
    await tts.load()
    load_time = time.time() - t0
    print(f"Model load time: {load_time:.3f}s")

    test_cases = [
        ("am_michael", "Hello everyone. I am CYNEXIS."),
        ("af_bella", "CYNEXIS, introduce yourself. I am CYNEXIS, an autonomous robotic assistant."),
        ("bm_lewis", "I can monitor my systems, communicate with my sensors, and perform predefined robotic actions."),
    ]

    for voice_id, text in test_cases:
        print("-" * 50)
        print(f"Voice: {voice_id} ({voice_manager.set_voice(voice_id).name})")
        print(f"Text:  \"{text}\"")

        t_start = time.time()
        wav_bytes = await tts.synthesize(text, voice=voice_id, speed=1.0)
        synth_time = time.time() - t_start

        duration_s = (len(wav_bytes) / 48000.0) if wav_bytes else 0.0
        rtf = synth_time / duration_s if duration_s > 0 else 0.0

        print(f"WAV Bytes: {len(wav_bytes)}")
        print(f"Audio Duration: {duration_s:.2f}s")
        print(f"Synthesis Time: {synth_time:.3f}s (RTF: {rtf:.2f}x)")

        # Play through local speakers
        print("Playing audio via laptop speaker...")
        t_play = time.time()
        play_ok = await audio_out.play(wav_bytes)
        print(f"Playback result: {play_ok} in {time.time() - t_play:.2f}s")

    print("=" * 60)
    print("All voice tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
