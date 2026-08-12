"""
CYNEXIS — TTS Voice Profiles
Defines verified Kokoro voice profiles and lookup registry.
Locked CYNEXIS Voices:
  1. am_michael (Michael - American Male)
  2. af_bella   (Bella   - American Female)
  3. bm_lewis   (Lewis   - British Male)
"""

from typing import Optional
from pydantic import BaseModel, Field


class VoiceProfile(BaseModel):
    """Metadata describing a voice option."""
    id: str = Field(..., description="Unique voice identifier in Kokoro runtime")
    name: str = Field(..., description="Human-readable display name")
    provider: str = Field(default="kokoro", description="Voice synthesis provider")
    language: str = Field(default="en-US", description="Language code")
    gender: str = Field(default="male", description="Voice gender")
    available: bool = Field(default=True, description="Whether voice is verified in runtime")
    description: str = Field(default="", description="Short description of the voice profile")


# Locked CYNEXIS Kokoro Voices — strictly verified in Kokoro 0.9.4 runtime
VOICE_PROFILES: dict[str, VoiceProfile] = {
    "am_michael": VoiceProfile(
        id="am_michael",
        name="Michael",
        provider="kokoro",
        language="en-US",
        gender="male",
        available=True,
        description="American English male voice — default CYNEXIS primary voice",
    ),
    "af_bella": VoiceProfile(
        id="af_bella",
        name="Bella",
        provider="kokoro",
        language="en-US",
        gender="female",
        available=True,
        description="American English female voice",
    ),
    "bm_lewis": VoiceProfile(
        id="bm_lewis",
        name="Lewis",
        provider="kokoro",
        language="en-GB",
        gender="male",
        available=True,
        description="British English male voice",
    ),
}

DEFAULT_VOICE_ID = "am_michael"


def get_voice_profile(voice_id: str) -> Optional[VoiceProfile]:
    """Retrieve voice profile by ID, or None if not found."""
    return VOICE_PROFILES.get(voice_id)


def is_valid_voice(voice_id: str) -> bool:
    """Check whether a given voice ID is a registered and available voice."""
    profile = VOICE_PROFILES.get(voice_id)
    return profile is not None and profile.available


def list_voice_profiles() -> list[VoiceProfile]:
    """Return list of all registered voice profiles."""
    return list(VOICE_PROFILES.values())
