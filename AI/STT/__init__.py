"""
CYNEXIS — Speech-to-Text Subsystem
Exports STT providers and microphone input abstractions.
"""

from .provider import STTProvider, MockSTTProvider
from .whisper import WhisperSTTProvider
from .microphone import MicrophoneInput, MockMicrophone, LocalMicrophone

__all__ = [
    "STTProvider",
    "MockSTTProvider",
    "WhisperSTTProvider",
    "MicrophoneInput",
    "MockMicrophone",
    "LocalMicrophone",
]
