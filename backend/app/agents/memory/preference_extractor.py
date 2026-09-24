"""Extracts traveler preferences and behavioral facts from conversational turns."""

import re
from typing import Any


class PreferenceExtractor:
    """Heuristic and regex entity-preference extractor for personalized travel memory."""

    AIRLINE_MAPPING = {
        "emirates": ("preferred_airline", "Emirates"),
        "air india": ("preferred_airline", "Air India"),
        "indigo": ("preferred_airline", "IndiGo"),
        "qatar": ("preferred_airline", "Qatar Airways"),
        "british airways": ("preferred_airline", "British Airways"),
        "lufthansa": ("preferred_airline", "Lufthansa"),
        "vistara": ("preferred_airline", "Air India"),
    }

    SEAT_MAPPING = {
        "window": ("seat_preference", "WINDOW"),
        "aisle": ("seat_preference", "AISLE"),
        "middle": ("seat_preference", "MIDDLE"),
        "extra legroom": ("seat_preference", "EXTRA_LEGROOM"),
    }

    CABIN_MAPPING = {
        "business": ("cabin_class", "BUSINESS"),
        "first class": ("cabin_class", "FIRST"),
        "economy": ("cabin_class", "ECONOMY"),
        "premium economy": ("cabin_class", "PREMIUM_ECONOMY"),
    }

    def extract_preferences(self, text: str) -> list[dict[str, Any]]:
        """Identify explicit preferences asserted by traveler in conversation."""
        text_lower = text.lower()
        extracted: list[dict[str, Any]] = []

        # 1. Preferred airlines
        for keyword, (key, value) in self.AIRLINE_MAPPING.items():
            if re.search(rf"\b(prefer|fly|like|always take|with)\s+{keyword}\b", text_lower) or (
                f"favorite airline is {keyword}" in text_lower
            ):
                extracted.append({"key": key, "value": value, "confidence": 0.95})
            elif keyword in text_lower and "only" in text_lower:
                extracted.append({"key": key, "value": value, "confidence": 0.90})

        # 2. Seat preferences
        for keyword, (key, value) in self.SEAT_MAPPING.items():
            if f"{keyword} seat" in text_lower or f"prefer {keyword}" in text_lower:
                extracted.append({"key": key, "value": value, "confidence": 0.90})

        # 3. Cabin class preferences
        for keyword, (key, value) in self.CABIN_MAPPING.items():
            if f"{keyword} class" in text_lower or f"prefer {keyword}" in text_lower:
                extracted.append({"key": key, "value": value, "confidence": 0.85})

        # 4. Home / departure base airport
        home_match = re.search(r"\b(based in|live in|home airport is|flying out of)\s+([A-Za-z\s]+)", text_lower)
        if home_match:
            city = home_match.group(2).strip().title()
            city_airport_map = {
                "Mumbai": "BOM",
                "Bombay": "BOM",
                "Delhi": "DEL",
                "New Delhi": "DEL",
                "Dubai": "DXB",
                "London": "LHR",
            }
            airport = city_airport_map.get(city, city)
            extracted.append({"key": "home_airport", "value": airport, "confidence": 0.90})

        # 5. Non-stop flight preference
        if "non-stop" in text_lower or "non stop" in text_lower or "direct flights only" in text_lower:
            extracted.append({"key": "prefer_nonstop", "value": "true", "confidence": 0.90})

        # 6. Refundability preference
        if "refundable" in text_lower or "flexible tickets" in text_lower:
            extracted.append({"key": "prefer_refundable", "value": "true", "confidence": 0.85})

        return extracted


preference_extractor = PreferenceExtractor()
