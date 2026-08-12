# CYNEXIS Conversational AI Pipeline

**Status:** Completed (Phase 3C)  
**Version:** 1.0.0  
**Target:** Local Offline Conversational Voice & Command Pipeline  

---

## 1. Architecture Overview

The CYNEXIS Conversational Voice Pipeline creates a unified, safe, and decoupled loop connecting audio/text input to robot hardware actions or conversational AI responses, and synthesizes dynamic speech using local Kokoro TTS.

```
                                USER AUDIO / TEXT INPUT
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  MicrophoneInput      │
                             │  (Local / Mock)       │
                             └───────────┬───────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  STTProvider          │
                             │  (Mock / Local)       │
                             └───────────┬───────────┘
                                         │
                                  Recognized Text
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  IntentEngine         │
                             │  (Pattern-based NLU)  │
                             └───────────┬───────────┘
                                         │
                    ┌────────────────────┴───────────────────┐
                    │                                        │
           [Match: Robot Command]                   [No Match: Question]
                    │                                        │
                    ▼                                        ▼
         ┌─────────────────────┐                  ┌─────────────────────┐
         │   SafetyValidator   │                  │   LLMProvider       │
         │   (Whitelist/State) │                  │   + Personality     │
         └──────────┬──────────┘                  │   + Memory History  │
                    │                             └──────────┬──────────┘
                    ▼                                        │
         ┌─────────────────────┐                             │
         │   ActionRegistry    │                             │
         │   (Rover/Arm/Camera)│                             │
         └──────────┬──────────┘                             │
                    │                                        │
              Response Text                            Response Text
                    │                                        │
                    └────────────────────┬───────────────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  VoiceState Manager   │
                             │  (IDLE/LISTENING/     │
                             │   THINKING/SPEAKING)  │
                             └───────────┬───────────┘
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  KokoroTTSProvider    │
                             │  (Michael/Bella/Lewis)│
                             └───────────┬───────────┘
                                         │
                                     WAV Audio
                                         │
                                         ▼
                             ┌───────────────────────┐
                             │  AudioOutput          │
                             │  (Laptop Speaker)     │
                             └───────────────────────┘
```

---

## 2. Core Safety Decoupling

> [!IMPORTANT]
> - The LLM generates text and conversational reasoning ONLY.
> - The LLM is **NEVER** permitted to directly execute Python code, shell commands, GPIO pins, or raw ESP32 serial packets.
> - Hardware actions can only execute through the **Safety Validator** and **Action Registry** via predefined action handlers.
> - `DRIFT` is intentionally not supported on the 6-wheel rover and is absent from all action enums, registries, and intent patterns.

---

## 3. Subsystem Components

### 3.1 Speech-to-Text (STT) & Microphone Abstraction
- **`MicrophoneInput`** (`AI/STT/microphone.py`):
  - `MockMicrophone`: Generates deterministic silent or mock audio bytes for CI and headless testing without physical audio hardware.
  - `LocalMicrophone`: Records 16kHz mono audio from the host computer's default microphone using `sounddevice` and non-blocking worker threads (`asyncio.to_thread`).
- **`STTProvider`** (`AI/STT/provider.py`):
  - `MockSTTProvider`: Cycles or transcribes audio data.
  - Pluggable interface for future local Whisper / offline STT engine.

### 3.2 Intent Classification & Command Separation
- **`IntentEngine`** (`AI/Intent/engine.py`):
  - Classifies natural language utterances into predefined robot actions (e.g. `HELLO`, `INTRODUCE_SELF`, `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`, `PHOTO`, `GRIP_OPEN`, `GRIP_CLOSE`, `ARM_UP`, `ARM_DOWN`).
  - If a command is recognized, it routes to `SafetyValidator -> ActionRegistry`.
  - If no command is recognized, it routes to `LLMProvider` for conversational response.

### 3.3 Kokoro TTS & Voice Management
- **Locked Voice Profiles**:
  - `am_michael`: Default American English Male (confident, robotic assistant tone).
  - `af_bella`: American English Female (warm, energetic tone).
  - `bm_lewis`: British English Male (authoritative, precise tone).
- **`VoiceManager`** (`AI/TTS/voice_manager.py`): Singleton for live voice selection and speed adjustment (`0.5x` to `2.0x`).
- **`KokoroTTSProvider`** (`AI/TTS/kokoro.py`): 24kHz 16-bit mono WAV synthesis. Preempts active speech upon receiving new high-priority speech requests.
- **`AudioOutput`** (`AI/TTS/audio_output.py`): `LocalAudioOutput` (via `sounddevice` with `stop()` support) and `MockAudioOutput`.

---

## 4. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/conversation/text` | Full text loop: Intent ➔ Action/LLM ➔ Kokoro TTS ➔ Base64 audio + latency metrics |
| `POST` | `/api/conversation/audio` | Full audio loop: Audio bytes ➔ STT ➔ Intent ➔ Action/LLM ➔ Kokoro TTS |
| `POST` | `/api/conversation/stop` | Immediate speech interruption and playback termination |
| `GET` | `/api/conversation/history` | Returns recent conversation memory history |
| `GET` | `/api/voice/status` | Returns active TTS provider, current voice, speed, and loaded status |
| `POST` | `/api/voice/select` | Switches active voice profile live |

---

## 5. CLI Testing Modes

### Interactive Conversation REPL
```powershell
d:\Cynexis\.venv\Scripts\python.exe main.py --conversation-test
```
Features:
- Type natural questions or robot commands in terminal.
- Dynamic voice switching: `/voice michael`, `/voice bella`, `/voice lewis`.
- Speech interruption: `/stop`.
- Exit: `quit` or `exit`.

### Live Microphone Test
```powershell
d:\Cynexis\.venv\Scripts\python.exe main.py --voice-test
```

### Live Benchmark Script
```powershell
d:\Cynexis\.venv\Scripts\python.exe D:\Cynexis\Testing\test_live_conversation.py
```

---

## 6. Automated Testing Verification
All 235 unit and integration tests execute cleanly with `pytest`:
```powershell
d:\Cynexis\.venv\Scripts\python.exe -m pytest Tests/ -v
# Result: 235 passed, 0 failed
```
