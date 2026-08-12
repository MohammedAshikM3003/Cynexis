# CYNEXIS Phase 8 — Intelligence Router Architecture & Documentation

## Overview

The **CYNEXIS Intelligence Router** is an intelligent decision and routing layer built directly above the conversational pipeline. It ensures that CYNEXIS operates in a **local-first** manner, executing deterministic calculations and robot state telemetry locally with zero LLM overhead, routing general knowledge to the local Llama 3.2:3B model, and accessing the internet only when live/temporal information is explicitly requested.

---

## Routing Categories

The Intelligence Router evaluates incoming natural language against a strict hierarchy of route categories:

| Category | Description | Execution Path | Network Access |
| :--- | :--- | :--- | :--- |
| **`ROBOT_COMMAND`** | Actuator or robot action commands ("move forward", "emergency stop", "wave") | `IntentEngine` -> `SafetyValidator` -> `ActionRegistry` -> `SerialBridge` -> ESP32 | **None** |
| **`TIME`** | Current time and timezone queries ("what time is it in India") | `DateTimeTool` (Local system clock & timezone math) | **None** |
| **`DATE`** | Current date, day of week, or year ("what date is today", "what day is it") | `DateTimeTool` (Local calendar) | **None** |
| **`ROBOT_STATUS`** | Robot connection, battery, ESP32 gateway telemetry, and motor status | `RobotStatusTool` (Reads singleton `robot_state`) | **None** |
| **`CALCULATOR`** | Arithmetic and math operations ("345 times 78", "17% of 500", "3.14 squared") | `SafeCalculatorTool` (AST-validated math evaluator) | **None** |
| **`VISION`** | Camera feeds and visual scene descriptions ("what do you see in front of you") | `LocalVLMProvider` (Moondream2 offline VLM) | **None** |
| **`PROJECT_KNOWLEDGE`** | System specs, sensors, architecture, communication protocols, phase status | `ProjectKnowledgeEngine` (Local CYNEXIS specification index) | **None** |
| **`LIVE_WEB`** | Current affairs, latest news, weather, match scores ("what happened today") | `LiveInformationProvider` (Rate-limited, cached `httpx` search) -> Local Llama 3.2:3B | **Controlled (Read-Only)** |
| **`LOCAL`** | General knowledge, creative writing, robotics concepts ("explain robotics") | Local Llama 3.2:3B (`OllamaLLMProvider`) | **None** |
| **`UNKNOWN`** | Ambiguous or low-confidence queries (< 0.50 confidence) | Safe fallback to Local Llama 3.2:3B | **None** |

---

## Safety Architecture & Untrusted Data Isolation

```
User Query
    │
Intelligence Router
    ├──> ROBOT_COMMAND ──> IntentEngine ──> SafetyValidator ──> ActionRegistry ──> SerialBridge ──> ESP32
    │
    ├──> DETERMINISTIC TOOLS ──> DateTimeTool / SafeCalculator / RobotStatus ──> Kokoro TTS
    │
    └──> LIVE_WEB ──> WebSearchProvider ──> Untrusted Data Sanitizer
                                                    │
                                                    ▼
                                            Isolated Prompt
                                                    │
                                                    ▼
                                            Local Llama 3.2:3B
                                                    │
                                                    ▼
                                                Kokoro TTS
```

### Critical Safety Invariants
1. **No Hardware Bypasses**: The Intelligence Router, Web Search Provider, and LLM have **zero authority** over `SerialBridge` or actuators. All robot movement strictly requires the `IntentEngine` -> `SafetyValidator` -> `ActionRegistry` pathway.
2. **Untrusted Data Sanitization**:
   - Web snippets are stripped of HTML, XML, script tags, and markdown code blocks.
   - Prompt injection tokens (`ignore previous instructions`, `SYSTEM:`, `[INST]`, `disable safety`) are actively neutralized.
   - Retrieved snippets are enclosed within explicit `--- BEGIN UNTRUSTED REFERENCE ---` and `--- END UNTRUSTED REFERENCE ---` delimiters.
3. **AST Calculator Sandbox**: `SafeCalculatorTool` evaluates expressions using Python's AST node whitelist (`BinOp`, `UnaryOp`, `Constant`, and whitelisted math functions). It completely disallows `eval()`, `exec()`, `__import__`, attributes, or arbitrary names.

---

## Caching & Rate Limiting

- **TTL Caching (`InformationCache`)**:
  - Live query results are cached in-memory with normalized keys.
  - Default TTL: 900 seconds (15 minutes).
  - Subsequent queries for identical or similar topics hit the cache with 0ms network latency.
- **Request Throttling**:
  - Minimum request interval between external web queries: 1.0 second.
  - Prevents rapid scraping loops or high outbound connection spikes.

---

## Offline Behavior & Fallback

If the system is offline, DNS is unreachable, or external web search times out:
1. CYNEXIS **does not crash** and **does not hallucinate**.
2. It returns a deterministic offline notice:
   > *"I cannot access live information right now. I can still answer general questions using my local knowledge."*
3. All local tools (`TIME`, `DATE`, `CALCULATOR`, `ROBOT_STATUS`, `PROJECT_KNOWLEDGE`, `VISION`, `LOCAL`) continue operating seamlessly.

---

## Latency Profile

- **Deterministic Tool Queries (`TIME`, `DATE`, `CALCULATOR`, `ROBOT_STATUS`, `PROJECT_KNOWLEDGE`)**:
  - Processing Latency: **< 1 ms**.
  - Bypasses LLM entirely; sends pre-computed speech text directly to Kokoro ONNX.
- **Standard Local Queries (`LOCAL`)**:
  - Unchanged low-latency streaming pipeline: Whisper -> Llama 3.2:3B -> Early Clause Chunker -> Kokoro ONNX.
- **Live Queries (`LIVE_WEB`)**:
  - Web Retrieval: Bounded by `web_search_timeout_s` (3.5s max).
  - Synthesis: Local Llama 3.2:3B streams concise 1-2 sentence response.

---

## Configuration Settings (`.env` & `core/config.py`)

```ini
# Intelligence Router & Live Information
ROUTER_ENABLED=true
WEB_SEARCH_ENABLED=true
WEB_SEARCH_TIMEOUT_S=3.5
WEB_SEARCH_MAX_RESULTS=3
WEB_CACHE_TTL_S=900
WEB_MIN_REQUEST_INTERVAL_S=1.0
```

---

## Manual Verification Procedure

To run unit tests manually from PowerShell:

```powershell
D:\Cynexis\.venv\Scripts\python.exe -m pytest Tests/Unit/test_intelligence_router.py -v
```

To run the full regression test suite:

```powershell
D:\Cynexis\.venv\Scripts\python.exe -m pytest Tests/ -q
```
