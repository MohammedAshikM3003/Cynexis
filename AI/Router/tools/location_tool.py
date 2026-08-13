"""
CYNEXIS — Safe Location Tool
Resolves GPS coordinates into descriptive location details using Nominatim.
"""

import httpx
from typing import Optional
from core.logger import get_logger

log = get_logger("location_tool")


class LocationTool:
    """Provides descriptive current location using geocoding."""

    @classmethod
    async def get_location(
        cls,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> str:
        """Resolve coordinates into descriptive address string."""
        if latitude is None or longitude is None:
            return "I cannot access your current location without GPS coordinates."

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                headers = {"User-Agent": "CynexisVoiceAssistant/1.0"}
                url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json&accept-language=en"
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    # Extract formatted address parts
                    address = data.get("address", {})
                    road = address.get("road")
                    suburb = address.get("suburb")
                    city = address.get("city") or address.get("town") or address.get("village")
                    state = address.get("state")
                    country = address.get("country")

                    parts = []
                    if road:
                        parts.append(road)
                    if suburb:
                        parts.append(suburb)
                    if city:
                        parts.append(city)
                    if state:
                        parts.append(state)
                    if country:
                        parts.append(country)

                    if parts:
                        address_str = ", ".join(parts[:3])  # Keep it short for TTS
                        return f"Your current location is {address_str}."
                    
                    display_name = data.get("display_name")
                    if display_name:
                        return f"Your current location is {display_name}."

            return f"Your current location coordinates are: latitude {latitude:.4f}, longitude {longitude:.4f}."
        except Exception as e:
            log.error(f"Reverse geocode failed for location query: {e}")
            return f"Your current location coordinates are: latitude {latitude:.4f}, longitude {longitude:.4f}."
