"""
CYNEXIS — Configuration
Loads settings from .env file using Pydantic Settings.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


# Project root: D:\Cynexis
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CynexisSettings(BaseSettings):
    """Central configuration loaded from .env file."""

    # Identity
    cynexis_name: str = Field(default="CYNEXIS")
    robot_id: str = Field(default="cynexis-001")
    environment: str = Field(default="development")

    # API Server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Feature toggles
    camera_enabled: bool = Field(default=True)
    voice_enabled: bool = Field(default=True)
    ai_enabled: bool = Field(default=True)
    mock_mode: bool = Field(default=True)

    # Paths (relative to project root)
    database_path: str = Field(default="./Database/cynexis.db")
    photo_path: str = Field(default="./Photos")
    video_path: str = Field(default="./Recordings")
    log_path: str = Field(default="./Logs")

    # Sync
    sync_enabled: bool = Field(default=False)
    sync_api_url: str = Field(default="")

    # Serial (ESP32)
    serial_port: str = Field(default="")
    serial_baud: int = Field(default=115200)

    # ESP32 Communication
    esp32_serial_port: str = Field(default="")          # e.g. COM5, /dev/ttyUSB0
    esp32_baud_rate: int = Field(default=115200)
    hardware_motors_enabled: bool = Field(default=False)  # Motor output default OFF
    heartbeat_interval_s: float = Field(default=1.0)
    heartbeat_timeout_s: float = Field(default=3.0)
    command_timeout_s: float = Field(default=2.0)
    max_retries: int = Field(default=3)

    # Glove / Hand Data Receiver (Read-Only Telemetry)
    glove_receiver_enabled: bool = Field(default=True)
    glove_receiver_port: str = Field(default="")          # e.g. COM8
    glove_receiver_baud: int = Field(default=115200)
    glove_receiver_reconnect_interval_s: float = Field(default=2.0)

    # TTS (Text-to-Speech)
    tts_provider: str = Field(default="kokoro")
    tts_voice: str = Field(default="am_michael")
    tts_speed: float = Field(default=1.0)              # 1.0x = natural human speech pacing
    tts_enabled: bool = Field(default=True)
    tts_play_local: bool = Field(default=True)
    tts_play_rover: bool = Field(default=False)         # Stream TTS audio to Rover ESP32 MAX98357A speaker
    tts_save_logs: bool = Field(default=False)
    tts_log_path: str = Field(default="./Logs/TTS")
    tts_onnx_intra_threads: int = Field(default=8)

    # Rover Audio (MAX98357A + 4Ω 3W Speaker)
    rover_audio_enabled: bool = Field(default=True)
    rover_audio_host: str = Field(default="255.255.255.255") # UDP broadcast or Rover IP
    rover_audio_port: int = Field(default=50006)
    rover_i2s_bclk: int = Field(default=19)
    rover_i2s_ws: int = Field(default=25)
    rover_i2s_din: int = Field(default=33)

    # STT (Speech-to-Text)
    stt_provider: str = Field(default="mock")
    stt_audio_input_source: str = Field(default="local")   # "local" | "network" | "mock"
    udp_audio_host: str = Field(default="0.0.0.0")
    udp_audio_port: int = Field(default=50005)
    udp_audio_buffer_seconds: float = Field(default=10.0)
    stt_whisper_model: str = Field(default="base.en")
    stt_whisper_device: str = Field(default="cpu")
    stt_whisper_compute_type: str = Field(default="float32")
    stt_whisper_cpu_threads: int = Field(default=8)
    stt_whisper_beam_size: int = Field(default=1)
    stt_whisper_vad_filter: bool = Field(default=False)

    # Camera & Vision
    camera_device_index: int = Field(default=0)
    camera_width: int = Field(default=640)
    camera_height: int = Field(default=480)
    camera_fps: int = Field(default=30)
    vision_provider: str = Field(default="mock")
    vlm_provider: str = Field(default="mock")
    vision_model_name: str = Field(default="vikhyatk/moondream2")
    vision_model_revision: str = Field(default="2024-08-26")
    vision_model_path: str = Field(default="./AI Models/VLM/moondream2")
    vision_device: str = Field(default="cpu")

    # LLM
    llm_provider: str = Field(default="mock")           # "mock" | "ollama"
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2:3b")
    ollama_temperature: float = Field(default=0.2)      # Lower = faster + more concise
    ollama_max_tokens: int = Field(default=100)          # 100 tokens max for short complete sentences
    ollama_timeout_s: float = Field(default=30.0)
    ollama_context_window: int = Field(default=8)       # conversation turns to include
    ollama_num_thread: int = Field(default=8)
    ollama_num_ctx: int = Field(default=512)

    # Intelligence Router & Live Information
    router_enabled: bool = Field(default=True)
    web_search_enabled: bool = Field(default=True)
    web_search_timeout_s: float = Field(default=3.0)
    web_search_max_results: int = Field(default=2)
    web_cache_ttl_s: int = Field(default=900)  # 15 minutes
    web_min_request_interval_s: float = Field(default=1.0)  # Throttling between web queries
    user_location: Optional[str] = Field(default=None)

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the project root."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return PROJECT_ROOT / p


# Singleton instance
settings = CynexisSettings()
