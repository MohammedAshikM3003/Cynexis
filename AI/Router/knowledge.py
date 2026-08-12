"""
CYNEXIS — Project Knowledge Engine
Local indexed knowledge base regarding the CYNEXIS robotic platform, hardware specs, sensors, and architecture.
Zero internet access.
"""

from typing import Optional
from core.logger import get_logger

log = get_logger("project_knowledge")


PROJECT_KNOWLEDGE_ENTRIES: list[dict] = [
    {
        "keywords": ["sensors", "sensor", "hardware sensor", "ultrasonic", "imu"],
        "topic": "Sensors",
        "answer": (
            "CYNEXIS uses an HC-SR04 ultrasonic sensor for obstacle distance measurement, "
            "an MPU6050 6-axis IMU for roll and pitch tracking, and five flex sensors on the control glove."
        ),
    },
    {
        "keywords": ["esp32", "microcontroller", "gateway", "firmware"],
        "topic": "ESP32",
        "answer": (
            "CYNEXIS utilizes dual ESP32 microcontrollers: one on the Control Glove transmitting teleoperation data via ESP-NOW, "
            "and an ESP32 Gateway on the rover connected to the host laptop over a 115,200 baud binary serial bridge."
        ),
    },
    {
        "keywords": ["architecture", "pipeline", "system design", "system architecture"],
        "topic": "Architecture",
        "answer": (
            "CYNEXIS features a decoupled local-first architecture: voice is captured with Faster-Whisper, "
            "routed via the Intelligence Router, processed by Llama 3.2:3B, synthesized by Kokoro ONNX, "
            "while robot hardware commands pass strictly through the IntentEngine, SafetyValidator, ActionRegistry, and SerialBridge."
        ),
    },
    {
        "keywords": ["llm", "language model", "llama", "ai model"],
        "topic": "LLM",
        "answer": (
            "CYNEXIS runs Llama 3.2:3B locally on CPU via Ollama with 6 threads, optimized for low time-to-first-token latency."
        ),
    },
    {
        "keywords": ["tts", "voice", "speech synthesizer", "kokoro"],
        "topic": "TTS",
        "answer": (
            "CYNEXIS uses Kokoro ONNX TTS with pre-warmed voices and multi-threaded intra-op ONNX inference for sub-second speech generation."
        ),
    },
    {
        "keywords": ["vlm", "vision model", "moondream", "camera"],
        "topic": "Vision",
        "answer": (
            "CYNEXIS employs Moondream2 running locally on CPU for offline camera image description and scene understanding."
        ),
    },
    {
        "keywords": ["communication protocol", "serial protocol", "framing", "checksum"],
        "topic": "Protocol",
        "answer": (
            "The CYNEXIS communication protocol is a packetized framing protocol with start bytes 0xAA 0x55, command IDs, payload length, and CRC checksum validation."
        ),
    },
    {
        "keywords": ["phase", "current phase", "phase status"],
        "topic": "Phase",
        "answer": (
            "CYNEXIS is currently in Phase 8, implementing the Intelligence Router for deterministic tool execution, local LLM routing, and live information retrieval."
        ),
    },
]


class ProjectKnowledgeEngine:
    """Retrieves local architectural and hardware facts about the CYNEXIS system."""

    @classmethod
    def find_match(cls, query: str) -> Optional[str]:
        """Search local knowledge entries for a matching topic."""
        q = query.lower()
        best_match = None
        max_score = 0

        for entry in PROJECT_KNOWLEDGE_ENTRIES:
            score = 0
            for kw in entry["keywords"]:
                if kw in q:
                    score += len(kw)
            if score > max_score and score >= 3:
                max_score = score
                best_match = entry["answer"]

        return best_match
