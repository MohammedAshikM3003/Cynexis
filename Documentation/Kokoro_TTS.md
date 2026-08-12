# CYNEXIS — Kokoro Text-to-Speech (TTS) System

## 1. Overview & Architecture

CYNEXIS utilizes **Kokoro-82M** as its local, offline neural Text-to-Speech (TTS) synthesis engine. The architecture ensures 100% on-device synthesis without external cloud dependencies (e.g., ElevenLabs, Google Cloud, Azure, OpenAI).

```
MICROPHONE / TEXT
       ↓
Speech-to-Text (STT) / REST API
       ↓
Intent Engine / Action Layer / LLM
       ↓
Spoken Response Text
       ↓
TTSProvider Interface
   ├── MockTTSProvider (Unit testing & fast startup)
   └── KokoroTTSProvider (Production on-device neural synthesis)
       ↓
AudioOutput Interface
   ├── MockAudioOutput (Simulated output)
   └── LocalAudioOutput (Laptop / Robot amplifier speaker via sounddevice)
```

---

## 2. Locked CYNEXIS Voice Profiles

The CYNEXIS voice system provides three locked voice profiles:

| Voice ID | Display Name | Language | Gender | Description |
| :--- | :--- | :--- | :--- | :--- |
| `am_michael` | **Michael** | `en-US` | Male | Primary default CYNEXIS voice. Clear, authoritative American accent. |
| `af_bella` | **Bella** | `en-US` | Female | Expressive, warm American female voice. |
| `bm_lewis` | **Lewis** | `en-GB` | Male | British English male voice with crisp articulation. |

All voices are validated at runtime. Unknown voice IDs are rejected with a controlled `ValueError` and HTTP 400 Bad Request error.

---

## 3. Configuration

TTS parameters are defined in `.env` and managed via Pydantic settings in `core/config.py`:

```env
# ============================================================
# TEXT-TO-SPEECH (KOKORO TTS)
# ============================================================
CYNEXIS_TTS_PROVIDER=kokoro
CYNEXIS_TTS_VOICE=am_michael
CYNEXIS_TTS_SPEED=1.0
CYNEXIS_TTS_ENABLED=true
CYNEXIS_TTS_PLAY_LOCAL=true
CYNEXIS_TTS_SAVE_LOGS=false
CYNEXIS_TTS_LOG_PATH=./Logs/TTS
```

### Available Configuration Settings:
- `CYNEXIS_TTS_PROVIDER`: Active TTS provider (`kokoro` or `mock`).
- `CYNEXIS_TTS_VOICE`: Default voice ID (`am_michael`, `af_bella`, or `bm_lewis`).
- `CYNEXIS_TTS_SPEED`: Speech speed multiplier (safe bounds: `0.5` to `2.0`, default `1.0`).
- `CYNEXIS_TTS_ENABLED`: Global enable toggle for speech synthesis.
- `CYNEXIS_TTS_PLAY_LOCAL`: Play synthesized audio directly through the host audio output device.
- `CYNEXIS_TTS_SAVE_LOGS`: Whether to save debug WAV audio files to disk.
- `CYNEXIS_TTS_LOG_PATH`: Destination path for debug audio logs.

---

## 4. Voice Manager API

The `VoiceManager` singleton (`AI.TTS.voice_manager.voice_manager`) provides active voice and speed state management:

```python
from AI.TTS import voice_manager

# Switch active voice
voice_manager.set_voice("af_bella")

# Get active voice ID and profile
active_id = voice_manager.get_current_voice() # "af_bella"
profile = voice_manager.current_voice()        # VoiceProfile(id="af_bella", name="Bella", ...)

# List available voices
voices = voice_manager.list_available_voices()

# Configure speed factor
voice_manager.set_speed(1.1)
speed = voice_manager.get_speed()             # 1.1
```

---

## 5. Kokoro TTS Provider Usage

`KokoroTTSProvider` implements the abstract `TTSProvider` interface:

```python
from AI.TTS import KokoroTTSProvider, LocalAudioOutput

tts = KokoroTTSProvider(audio_output=LocalAudioOutput())

# Lazy load or explicit load
await tts.load()

# Synthesize audio to WAV bytes in memory without forced local playback
wav_bytes = await tts.synthesize("Hello everyone. I am CYNEXIS.", voice="am_michael", speed=1.0)

# Synthesize and play through laptop / robot speaker
await tts.speak("Hello everyone. I am CYNEXIS.")
```

---

## 6. REST API Endpoints

FastAPI server exposes endpoints under `/api/voice`:

### 1. `GET /api/voice/status`
Returns subsystem status:
```json
{
  "provider": "kokoro",
  "enabled": true,
  "current_voice": "am_michael",
  "current_voice_name": "Michael",
  "speed": 1.0,
  "available": true,
  "model_loaded": true,
  "is_speaking": false,
  "last_utterance": "",
  "last_response": ""
}
```

### 2. `GET /api/voice/list`
Lists all available Kokoro voices.

### 3. `POST /api/voice/select`
Switches active voice:
```json
{
  "voice": "af_bella"
}
```

### 4. `POST /api/voice/speed`
Sets speed factor:
```json
{
  "speed": 1.1
}
```

### 5. `POST /api/voice/speak`
Synthesizes speech:
```json
{
  "text": "Hello everyone. I am CYNEXIS.",
  "voice": "am_michael",
  "speed": 1.0,
  "play_local": true
}
```
Response contains execution metadata and base64-encoded WAV data for browser playback.

### 6. `GET /voice` or `GET /lab`
Serves the CYNEXIS Voice Pipeline Laboratory web dashboard.

---

## 7. Performance Benchmarks

Measured on Intel Core i7-10700 CPU (PyTorch CPU runtime):

| Voice Profile | Test Utterance | Generated Audio | Synthesis Time | Real-Time Factor (RTF) |
| :--- | :--- | :--- | :--- | :--- |
| `am_michael` | "Hello everyone. I am CYNEXIS." | 2.11s | 0.407s | **0.19x** (5.2x faster than real-time) |
| `af_bella` | "CYNEXIS, introduce yourself..." | 4.93s | 0.887s | **0.18x** (5.6x faster than real-time) |
| `bm_lewis` | "I can monitor my systems..." | 5.15s | 0.902s | **0.18x** (5.6x faster than real-time) |

---

## 8. Adding Additional Kokoro Voices in the Future

To add additional Kokoro voices:
1. Verify the voice ID in the Kokoro model repository (e.g. `hexgrad/Kokoro-82M`).
2. Add the definition to `VOICE_PROFILES` dictionary in `AI/TTS/voices.py`:
```python
VOICE_PROFILES["af_nicole"] = VoiceProfile(
    id="af_nicole",
    name="Nicole",
    provider="kokoro",
    language="en-US",
    gender="female",
    available=True,
    description="American English female voice",
)
```
3. Run tests to confirm registration:
```powershell
python -m pytest Tests/Unit/test_tts.py -v
```
