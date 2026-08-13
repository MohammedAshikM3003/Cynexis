"""
CYNEXIS — Safe Weather Tool
Fetches real-time weather using Open-Meteo free API without keys or scrapers.
Supports HTML5 Geolocation coordinates, parallel geocoding, and forecast detection.
"""

import httpx
import re
import time
import asyncio
from typing import Optional
from core.logger import get_logger

log = get_logger("weather_tool")


class WeatherTool:
    """Provides real-time weather data with automatic location geolocation and geocoding."""

    @classmethod
    def extract_city(cls, query: str) -> Optional[str]:
        """Extract city name from query string, ignoring location-relative indicators."""
        m = re.search(r"\b(in|for|weather)\s+([a-zA-Z\s\-\,\.]+)", query, re.IGNORECASE)
        if m:
            city = m.group(2).strip()
            # Clean up leading prepositions
            city = re.sub(r"^(in|for|at)\s+", "", city, flags=re.IGNORECASE).strip()
            # Clean up trailing punctuation
            city = city.rstrip("?.!")
            # Clean up keywords
            city = re.sub(
                r"\b(today|tomorrow|now|yesterday|forecast|weather|currently|current|of)\b",
                "",
                city,
                flags=re.IGNORECASE
            ).strip()
            
            city_lower = city.lower()
            ignore_phrases = {"my location", "here", "outside", "today", "tomorrow", "tonight", "now", "at my location", "the weather"}
            if city_lower in ignore_phrases or any(p in city_lower for p in ["my location", "here", "outside"]):
                return None
                
            if city:
                return city
        return None

    @classmethod
    def _map_wmo_code(cls, code: int) -> str:
        """Map WMO weather code to standard condition description."""
        if code == 0:
            return "sunny"
        elif code in (1, 2, 3):
            return "partly cloudy"
        elif code in (45, 48):
            return "foggy"
        elif code in (51, 53, 55, 56, 57):
            return "drizzling"
        elif code in (61, 63, 65, 66, 67):
            return "raining"
        elif code in (71, 73, 75, 77):
            return "snowing"
        elif code in (80, 81, 82):
            return "showers"
        elif code in (85, 86):
            return "snow showers"
        elif code >= 95:
            return "thunderstorms"
        return "clear"

    @classmethod
    async def _fetch_weather(cls, lat: float, lon: float, query: str) -> str:
        """Fetch and format weather from Open-Meteo based on current or forecast queries."""
        query_lower = query.lower()
        
        # 1. TOMORROW FORECAST
        if "tomorrow" in query_lower:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=auto"
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    daily = data.get("daily", {})
                    if daily and len(daily.get("weather_code", [])) > 1:
                        temp_max = daily.get("temperature_2m_max")[1]
                        temp_min = daily.get("temperature_2m_min")[1]
                        weather_code = daily.get("weather_code")[1]
                        precip_sum = daily.get("precipitation_sum")[1]
                        condition = cls._map_wmo_code(weather_code)
                        
                        if "rain" in query_lower:
                            if precip_sum > 0.1:
                                return f"yes, rain is forecast for tomorrow, around {precip_sum:.1f} mm."
                            else:
                                return "no, no rain is forecast tomorrow."
                        else:
                            return f"tomorrow it will be {condition}, high of {int(round(temp_max))} and low of {int(round(temp_min))}."
                            
        # 2. TONIGHT FORECAST
        elif "tonight" in query_lower:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,apparent_temperature,precipitation,weather_code&timezone=auto"
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    hourly = data.get("hourly", {})
                    if hourly and len(hourly.get("temperature_2m", [])) > 20:
                        # Fetch values for 20:00 (index 20 represents 8pm today)
                        temp = hourly.get("temperature_2m")[20]
                        feels_like = hourly.get("apparent_temperature", hourly.get("temperature_2m"))[20]
                        weather_code = hourly.get("weather_code")[20]
                        condition = cls._map_wmo_code(weather_code)
                        
                        # Sum evening precipitation (hours 18 to 23)
                        precip_evening = sum(hourly.get("precipitation", [0.0]*24)[i] for i in range(18, 24))
                        
                        if "rain" in query_lower:
                            if precip_evening > 0.1:
                                return "yes, there is a chance of rain tonight."
                            else:
                                return "no, rain is not forecast for tonight."
                        else:
                            return f"tonight it will be {condition} and {int(round(temp))} degrees."
 
        # 3. CURRENT WEATHER & TODAY GENERAL
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&daily=precipitation_sum&timezone=auto"
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                current = data.get("current", {})
                temp = current.get("temperature_2m")
                feels_like = current.get("apparent_temperature", temp)
                weather_code = current.get("weather_code", 0)
                wind_speed = current.get("wind_speed_10m")
                condition = cls._map_wmo_code(weather_code)
                
                if "rain" in query_lower or "raining" in query_lower:
                    daily = data.get("daily", {})
                    precip_today = daily.get("precipitation_sum", [0.0])[0] if daily else 0.0
                    # Is it currently raining WMO code or precipitation registered today?
                    if weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82) or precip_today > 0.1:
                        return f"yes, it is raining and {int(round(temp))} degrees."
                    else:
                        return "no, it is not currently raining."
                else:
                    return f"it's currently {int(round(temp))} degrees and {condition}."
 
        raise httpx.HTTPStatusError("Open-Meteo API returned error status code", request=None, response=r)

    @classmethod
    async def _reverse_geocode(cls, lat: float, lon: float) -> str:
        """Reverse geocode coordinates using keyless Nominatim endpoint with 1.0s timeout."""
        async with httpx.AsyncClient(timeout=1.0) as client:
            headers = {"User-Agent": "CynexisVoiceAssistant/1.0"}
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                address = data.get("address", {})
                name = address.get("city") or address.get("town") or address.get("village") or address.get("suburb") or address.get("county") or address.get("state") or "your location"
                return name
        return "your location"

    @classmethod
    async def get_weather(
        cls,
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        accuracy: Optional[float] = None,
        timestamp: Optional[float] = None
    ) -> str:
        """Fetch weather resolving coordinate priority, parallel API requests, and print telemetry logs."""
        t_start = time.time()
        import os
        from core.config import settings

        # Parse priorities
        city = cls.extract_city(query)
        
        lat = None
        lon = None
        acc = accuracy
        gps_age = 0.0
        location_source = "NONE"
        location_name = ""

        # Priority 1: Explicit City overrides GPS
        if city:
            location_source = "EXPLICIT_QUERY"
            location_name = city
            # Geocode city using Open-Meteo
            async with httpx.AsyncClient(timeout=1.5) as client:
                try:
                    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
                    r = await client.get(url)
                    if r.status_code == 200:
                        data = r.json()
                        results = data.get("results", [])
                        if results:
                            lat = results[0]["latitude"]
                            lon = results[0]["longitude"]
                            location_name = results[0]["name"]
                            log.info(f"Geocoded explicit city '{city}' to ({lat}, {lon})")
                except Exception as e:
                    log.warning(f"Geocoding failed for city '{city}': {e}")
            if lat is None or lon is None:
                return f"I could not locate the city '{city}'."
        else:
            # Priority 2: Use browser GPS coordinates if available
            if latitude is not None and longitude is not None:
                lat = latitude
                lon = longitude
                location_source = "GPS"
                if timestamp is not None:
                    gps_age = max(0.0, time.time() - (timestamp / 1000.0))
            else:
                # Priority 3: Fall back to settings configurations
                config_loc = getattr(settings, "user_location", None) or os.environ.get("USER_LOCATION")
                if config_loc:
                    m = re.match(r"^\s*([\-\d\.]+)\s*,\s*([\-\d\.]+)\s*$", config_loc)
                    if m:
                        try:
                            lat = float(m.group(1))
                            lon = float(m.group(2))
                            location_source = "SETTINGS_COORDS"
                        except ValueError:
                            pass
                    else:
                        city = config_loc
                        location_source = "SETTINGS_CITY"
                        location_name = city
                
                # Geocode settings city if no coordinates
                if lat is None and lon is None and city:
                    async with httpx.AsyncClient(timeout=1.5) as client:
                        try:
                            url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
                            r = await client.get(url)
                            if r.status_code == 200:
                                data = r.json()
                                results = data.get("results", [])
                                if results:
                                    lat = results[0]["latitude"]
                                    lon = results[0]["longitude"]
                                    location_name = results[0]["name"]
                        except Exception as e:
                            log.warning(f"Geocoding settings city failed: {e}")
                
                # Priority 4: Fall back to default city
                if lat is None and lon is None:
                    default_city = getattr(settings, "default_city", None) or os.environ.get("DEFAULT_CITY")
                    if default_city:
                        city = default_city
                        location_source = "DEFAULT_CITY"
                        location_name = city
                        async with httpx.AsyncClient(timeout=1.5) as client:
                            try:
                                url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
                                r = await client.get(url)
                                if r.status_code == 200:
                                    data = r.json()
                                    results = data.get("results", [])
                                    if results:
                                        lat = results[0]["latitude"]
                                        lon = results[0]["longitude"]
                                        location_name = results[0]["name"]
                            except Exception as e:
                                log.warning(f"Geocoding default city failed: {e}")

        if lat is None or lon is None:
            # Print failure telemetry block
            print(f"\n============================================================\n"
                  f"[WEATHER TELEMETRY]\n"
                  f"source=none\n"
                  f"latitude=\n"
                  f"longitude=\n"
                  f"accuracy=\n"
                  f"location_age=0.0\n"
                  f"api_latency=0.000\n"
                  f"ollama=false\n"
                  f"web_search=false\n"
                  f"direct_response=true\n"
                  f"============================================================\n")
            return "I can't access your location. Please enable location access and try again."

        # Fetch Open-Meteo weather and reverse geocode in parallel to optimize latency
        weather_latency = 0.0
        geocode_latency = 0.0

        async def _fetch_weather_timed():
            nonlocal weather_latency
            t0 = time.time()
            res = await cls._fetch_weather(lat, lon, query)
            weather_latency = time.time() - t0
            return res

        async def _geocode_timed():
            nonlocal geocode_latency
            t0 = time.time()
            res = await cls._reverse_geocode(lat, lon)
            geocode_latency = time.time() - t0
            return res

        # Reverse geocoding Nominatim call is bypassed entirely to minimize network latency.
        if location_source in ("GPS", "SETTINGS_COORDS") and not location_name:
            location_name = "your location"
            
        t_w0 = time.time()
        weather_res = await cls._fetch_weather(lat, lon, query)
        weather_latency = time.time() - t_w0
        geocode_latency = 0.0

        total_weather_tool = time.time() - t_start

        # Prepare accuracy / age logging strings
        accuracy_str = f"{acc:.1f} m" if acc is not None else "UNKNOWN"
        gps_age_str = f"{gps_age:.1f} s" if location_source == "GPS" else "N/A"

        src_map = {
            "GPS": "gps",
            "EXPLICIT_QUERY": "explicit",
            "SETTINGS_COORDS": "config",
            "SETTINGS_CITY": "config",
            "DEFAULT_CITY": "config",
            "NONE": "none"
        }
        source_mapped = src_map.get(location_source, "none")
        print(f"\n============================================================\n"
              f"[WEATHER TELEMETRY]\n"
              f"source={source_mapped}\n"
              f"latitude={lat:.6f}\n"
              f"longitude={lon:.6f}\n"
              f"accuracy={acc if acc is not None else ''}\n"
              f"location_age={gps_age:.1f}\n"
              f"api_latency={weather_latency:.3f}\n"
              f"ollama=false\n"
              f"web_search=false\n"
              f"direct_response=false\n"
              f"============================================================\n")

        # Print Route Telemetry
        print(f"\n============================================================\n"
              f"[ROUTE TELEMETRY]\n"
              f"query=\"{query}\"\n"
              f"route=WEATHER\n"
              f"ollama=false\n"
              f"web_search=false\n"
              f"gps=true\n"
              f"weather_api=true\n"
              f"============================================================\n")

        if isinstance(weather_res, Exception):
            log.error(f"Weather fetch failed: {weather_res}")
            return "I cannot access real-time weather data right now."

        # Add the locality name prefix to the weather statement
        weather_desc = weather_res
        if weather_desc.startswith("It's currently") or weather_desc.startswith("it's currently"):
            weather_desc = "it's currently" + weather_desc[len("it's currently"):]
        elif weather_desc.startswith("Yes,") or weather_desc.startswith("yes,"):
            return weather_res
        elif weather_desc.startswith("No,") or weather_desc.startswith("no,"):
            return weather_res

        if location_name == "your location":
            return f"At your location, {weather_desc}"
        return f"In {location_name}, {weather_desc}"
