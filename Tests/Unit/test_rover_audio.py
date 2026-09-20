"""
CYNEXIS — Unit Tests for Rover Audio Subsystem
Tests RoverAudioOutput UDP streaming, packet formatting, and composite audio output.
"""

import struct
import socket
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from core.config import settings
from AI.TTS.audio_output import RoverAudioOutput, CompositeAudioOutput, MockAudioOutput


@pytest.mark.asyncio
async def test_rover_audio_output_packetization():
    """Verify RoverAudioOutput header formatting and UDP packetization."""
    rover_out = RoverAudioOutput(host="127.0.0.1", port=50006)
    
    # Generate 1000 dummy PCM bytes (500 samples)
    dummy_pcm = bytes([i % 256 for i in range(1000)])
    
    sent_packets = []
    
    def mock_sendto(data, addr):
        sent_packets.append((data, addr))
        return len(data)

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = mock_sendto
        mock_sock_cls.return_value = mock_sock

        success = await rover_out.play(dummy_pcm, sample_rate=24000)
        assert success is True

        assert len(sent_packets) == 2  # 1000 bytes / 500 = 2 chunks
        
        # Verify first packet header
        header, payload = sent_packets[0][0][:8], sent_packets[0][0][8:]
        magic, seq, rate, payload_len = struct.unpack("<2sHHH", header)
        
        assert magic == b"CY"
        assert rate == 24000
        assert payload_len == 500
        assert len(payload) == 500
        assert sent_packets[0][1] == ("127.0.0.1", 50006)


@pytest.mark.asyncio
async def test_composite_audio_output():
    """Verify CompositeAudioOutput dispatches audio to multiple outputs concurrently."""
    mock1 = MockAudioOutput()
    mock2 = MockAudioOutput()
    composite = CompositeAudioOutput([mock1, mock2])
    
    assert composite.is_available() is True
    success = await composite.play(b"DUMMY_AUDIO", sample_rate=24000)
    assert success is True
