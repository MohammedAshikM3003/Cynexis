"""
CYNEXIS — DateTime Tool
Deterministic date, time, day, and timezone queries without LLM guessing or external web calls.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import re
from core.logger import get_logger

log = get_logger("datetime_tool")


class DateTimeTool:
    """Provides deterministic real-time system clock and date responses."""

    # Timezone offsets for common requested regions and cities
    TIMEZONES: dict[str, tuple[timezone, str]] = {
        # India
        "india": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "ist": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "tamil nadu": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "tamilnadu": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "chennai": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "delhi": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "mumbai": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "bangalore": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "bengaluru": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "hyderabad": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        "kolkata": (timezone(timedelta(hours=5, minutes=30)), "IST"),
        # Middle East / Gulf
        "uae": (timezone(timedelta(hours=4)), "GST"),
        "dubai": (timezone(timedelta(hours=4)), "GST"),
        "abu dhabi": (timezone(timedelta(hours=4)), "GST"),
        "saudi": (timezone(timedelta(hours=3)), "AST"),
        "saudi arabia": (timezone(timedelta(hours=3)), "AST"),
        "riyadh": (timezone(timedelta(hours=3)), "AST"),
        "qatar": (timezone(timedelta(hours=3)), "AST"),
        "doha": (timezone(timedelta(hours=3)), "AST"),
        # Asia / Pacific
        "singapore": (timezone(timedelta(hours=8)), "SGT"),
        "malaysia": (timezone(timedelta(hours=8)), "MYT"),
        "china": (timezone(timedelta(hours=8)), "CST"),
        "beijing": (timezone(timedelta(hours=8)), "CST"),
        "hong kong": (timezone(timedelta(hours=8)), "HKT"),
        "tokyo": (timezone(timedelta(hours=9)), "JST"),
        "japan": (timezone(timedelta(hours=9)), "JST"),
        "sydney": (timezone(timedelta(hours=10)), "AEST"),
        "australia": (timezone(timedelta(hours=10)), "AEST"),
        # Europe / UK
        "utc": (timezone.utc, "UTC"),
        "gmt": (timezone.utc, "GMT"),
        "london": (timezone(timedelta(hours=0)), "GMT/BST"),
        "uk": (timezone(timedelta(hours=0)), "GMT/BST"),
        "germany": (timezone(timedelta(hours=1)), "CET"),
        "berlin": (timezone(timedelta(hours=1)), "CET"),
        "paris": (timezone(timedelta(hours=1)), "CET"),
        "france": (timezone(timedelta(hours=1)), "CET"),
        # Americas
        "us east": (timezone(timedelta(hours=-5)), "EST"),
        "est": (timezone(timedelta(hours=-5)), "EST"),
        "new york": (timezone(timedelta(hours=-5)), "EST"),
        "us west": (timezone(timedelta(hours=-8)), "PST"),
        "pst": (timezone(timedelta(hours=-8)), "PST"),
        "california": (timezone(timedelta(hours=-8)), "PST"),
        "los angeles": (timezone(timedelta(hours=-8)), "PST"),
        "san francisco": (timezone(timedelta(hours=-8)), "PST"),
    }

    @classmethod
    def get_time(cls, query: str = "") -> str:
        """Return formatted current time, respecting requested timezone/city if specified."""
        query_lower = query.lower()
        target_tz = None
        tz_label = ""

        for key, (tz, label) in cls.TIMEZONES.items():
            pattern = rf"\b(in|of|for|at)?\s*{re.escape(key)}\b"
            if re.search(pattern, query_lower):
                target_tz = tz
                tz_label = f" ({label})"
                break

        if target_tz:
            now = datetime.now(target_tz)
        else:
            now = datetime.now()

        # Format: "10:30 AM" or "2:15 PM"
        formatted_time = now.strftime("%I:%M %p").lstrip("0")
        return f"The current time is {formatted_time}{tz_label}."

    @classmethod
    def get_date(cls, query: str = "") -> str:
        """Return formatted current date, yesterday's date, or tomorrow's date."""
        q = query.lower()
        now = datetime.now()
        if "tomorrow" in q:
            target = now + timedelta(days=1)
            formatted_date = target.strftime("%A, %B %d, %Y")
            return f"Tomorrow is {formatted_date}."
        elif "yesterday" in q:
            target = now - timedelta(days=1)
            formatted_date = target.strftime("%A, %B %d, %Y")
            return f"Yesterday was {formatted_date}."
        else:
            formatted_date = now.strftime("%A, %B %d, %Y")
            return f"Today is {formatted_date}."

    @classmethod
    def get_day(cls, query: str = "") -> str:
        """Return the current day of the week, yesterday's day, or tomorrow's day."""
        q = query.lower()
        now = datetime.now()
        if "tomorrow" in q:
            target = now + timedelta(days=1)
            day_name = target.strftime("%A")
            return f"Tomorrow will be {day_name}."
        elif "yesterday" in q:
            target = now - timedelta(days=1)
            day_name = target.strftime("%A")
            return f"Yesterday was {day_name}."
        else:
            day_name = now.strftime("%A")
            return f"Today is {day_name}."

    @classmethod
    def get_month(cls, query: str = "") -> str:
        """Return the current month."""
        now = datetime.now()
        month_name = now.strftime("%B")
        return f"The current month is {month_name}."

    @classmethod
    def get_year(cls, query: str = "") -> str:
        """Return current year."""
        now = datetime.now()
        return f"The current year is {now.year}."

    @classmethod
    def process(cls, query: str) -> str:
        """Process any time/date natural language query deterministically."""
        q = query.lower()
        if any(w in q for w in ["what day", "which day", "day is today", "day is it", "day will it be", "day was yesterday", "day is tomorrow"]):
            return cls.get_day(query)
        if any(w in q for w in ["what month", "which month", "current month"]):
            return cls.get_month(query)
        if any(w in q for w in ["what year", "which year", "current year"]):
            return cls.get_year(query)
        if any(w in q for w in ["what date", "today's date", "date today", "date is today", "what's the date", "what is the date", "tomorrow's date", "yesterday's date"]):
            return cls.get_date(query)
        if any(w in q for w in ["what time", "current time", "time is it", "time now", "tell me the time", "time in", "time of"]):
            return cls.get_time(query)
        # Default fallback
        return cls.get_time(query)
