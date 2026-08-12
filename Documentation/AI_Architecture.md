# CYNEXIS — AI Architecture

## Safety Principle

> **The LLM NEVER directly controls hardware.**

All hardware actions must pass through:
1. Intent classification
2. Safety validation
3. Action registry lookup
4. Handler execution

## Pipeline Architecture

```
┌─────────────┐    ┌──────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐
│ MICROPHONE  │───▶│ STT  │───▶│ INTENT  │───▶│ SAFETY   │───▶│ ACTION  │───▶│ ROBOT   │
│             │    │      │    │ ENGINE  │    │ VALIDATOR│    │ REGISTRY│    │ CONTROL │
└─────────────┘    └──────┘    └────┬────┘    └──────────┘    └─────────┘    └─────────┘
                                   │
                              No match?
                                   │
                              ┌────▼────┐    ┌──────┐
                              │  LLM    │───▶│ TTS  │───▶ SPEAKER
                              │ (chat)  │    │      │
                              └─────────┘    └──────┘
```

## Components

### Intent Engine (`AI/Intent/engine.py`)
- Pattern-based, no ML dependency
- Maps natural language → ActionName
- 50+ patterns covering all 18 actions
- Falls through to LLM for conversational queries

### Action Registry (`AI/Actions/registry.py`)
- Whitelist of all valid robot actions
- Each action has: name, handler, safety level, timeout
- No action can be invented at runtime
- No `eval()`, no `exec()`

### LLM Provider (`AI/LLM/provider.py`)
- Abstract interface → swap implementations without rewriting
- MockLLMProvider for development (no model download)
- Real provider TBD when onboard computer is confirmed
- LLM output is TEXT ONLY — never motor commands

### STT & Microphone Abstraction (`AI/STT/`)
- Abstract speech-to-text (`AI/STT/provider.py`)
- Microphone Input abstraction (`AI/STT/microphone.py`):
  - `MockMicrophone`: Headless, CI, and test audio generation.
  - `LocalMicrophone`: Asynchronous microphone capture from host computer default input via `sounddevice`.
- `MockSTTProvider`: Cycles through test phrases for offline deterministic testing.
- Local Whisper STT hook ready for Phase 4.

### TTS Provider (`AI/TTS/`)
- Abstract text-to-speech architecture (`AI/TTS/provider.py`)
- `MockTTSProvider`: Fast development & unit test provider (no model loading)
- `KokoroTTSProvider`: Production on-device neural synthesis engine (`Kokoro-82M` via `kokoro==0.9.4`)
- `VoiceManager` (`AI/TTS/voice_manager.py`): Dynamic voice profile selection and speed controls (`0.5x` - `2.0x`)
- Locked voices: `am_michael` (Michael), `af_bella` (Bella), `bm_lewis` (Lewis)
- Audio Output abstraction (`AI/TTS/audio_output.py`): Decoupled `LocalAudioOutput` via `sounddevice` (with `stop()` preemption) and `MockAudioOutput`
- Full documentation: see [Conversational Pipeline](file:///D:/Cynexis/Documentation/Conversational_Pipeline.md) and [Kokoro TTS](file:///D:/Cynexis/Documentation/Kokoro_TTS.md)


### Memory (`AI/Memory/provider.py`)
- Short-term: conversation history (50 messages, rolling)
- Long-term: key-value storage by category (system/user/robot)
- Future: SQLite-backed persistent memory

### Personality (`AI/personality.py`)
- Centralized tone and response templates
- System prompt for LLM context
- Not hardcoded throughout the app

## What the LLM CAN Do
- Answer questions about CYNEXIS
- Generate conversational responses
- Describe its capabilities
- Respond to greetings

## What the LLM CANNOT Do
- Send motor commands
- Set servo angles
- Control GPIO pins
- Execute arbitrary code
- Bypass the action whitelist
- Create new actions at runtime
