"""Entity extractor for identifying travel domain entities from natural language queries."""

import re

from app.graphrag.models import ExtractedEntity

# Known mappings for normalization
KNOWN_AIRLINES: dict[str, str] = {
    "emirates": "EK",
    "ek": "EK",
    "air india": "AI",
    "ai": "AI",
    "indigo": "6E",
    "6e": "6E",
    "british airways": "BA",
    "ba": "BA",
    "qatar airways": "QR",
    "qatar": "QR",
    "qr": "QR",
}

KNOWN_AIRPORTS: dict[str, str] = {
    "bom": "BOM",
    "mumbai": "BOM",
    "dxb": "DXB",
    "dubai": "DXB",
    "del": "DEL",
    "delhi": "DEL",
    "new delhi": "DEL",
    "lhr": "LHR",
    "london": "LHR",
    "heathrow": "LHR",
    "jfk": "JFK",
    "new york": "JFK",
    "sin": "SIN",
    "singapore": "SIN",
    "doh": "DOH",
    "doha": "DOH",
    "blr": "BLR",
    "bengaluru": "BLR",
    "bangalore": "BLR",
}

POLICY_KEYWORDS: dict[str, str] = {
    "cancellation": "CANCELLATION",
    "cancel": "CANCELLATION",
    "cancelling": "CANCELLATION",
    "refund": "CANCELLATION",
    "refundable": "CANCELLATION",
    "baggage": "BAGGAGE",
    "luggage": "BAGGAGE",
    "change": "FARE_RULES",
    "reschedule": "FARE_RULES",
    "fare rules": "FARE_RULES",
    "contract of carriage": "CONTRACT_OF_CARRIAGE",
    "carriage": "CONTRACT_OF_CARRIAGE",
    "ndc": "NDC_SPECIFICATION",
}


class TravelEntityExtractor:
    """Extracts and normalizes travel domain entities from query text."""

    def extract_entities(
        self,
        query: str,
        airline_hint: str | None = None,
        flight_hint: str | None = None,
        booking_hint: str | None = None,
        policy_hint: str | None = None,
    ) -> list[ExtractedEntity]:
        """Extract travel entities combining query string regex/keyword extraction and explicit hints."""
        entities: list[ExtractedEntity] = []
        seen = set()

        def add_entity(e_type: str, val: str, norm: str | None = None, conf: float = 1.0):
            key = (e_type, norm or val.upper())
            if key not in seen:
                seen.add(key)
                entities.append(
                    ExtractedEntity(
                        entity_type=e_type,
                        value=val,
                        normalized_id=norm or val.upper(),
                        confidence=conf,
                    )
                )

        # 1. Explicit hints take highest precedence
        if flight_hint:
            add_entity("FLIGHT", flight_hint.strip().upper(), flight_hint.strip().upper().replace(" ", ""))
        if airline_hint:
            norm_al = KNOWN_AIRLINES.get(airline_hint.lower().strip(), airline_hint.strip().upper())
            add_entity("AIRLINE", airline_hint.strip(), norm_al)
        if booking_hint:
            add_entity("BOOKING_REF", booking_hint.strip().upper(), booking_hint.strip().upper())
        if policy_hint:
            norm_pol = POLICY_KEYWORDS.get(policy_hint.lower().strip(), policy_hint.strip().upper())
            add_entity("POLICY_TYPE", policy_hint.strip(), norm_pol)

        # 2. Extract Booking Reference (only if not explicitly provided)
        if not booking_hint:
            booking_pattern = re.compile(r"\b(BK-[A-Z0-9]+-\d+|BK[A-Z0-9]{5,8})\b", re.IGNORECASE)
            for match in booking_pattern.finditer(query):
                b_ref = match.group(1).upper()
                add_entity("BOOKING_REF", b_ref, b_ref, 0.95)

        # 3. Extract Flight Number (only if not explicitly provided)
        if not flight_hint:
            flight_pattern = re.compile(r"\b(EK|AI|6E|BA|QR)\s?(\d{3,4})\b", re.IGNORECASE)
            for match in flight_pattern.finditer(query):
                carrier = match.group(1).upper()
                num = match.group(2)
                f_num = f"{carrier}{num}"
                add_entity("FLIGHT", f"{carrier}{num}", f_num, 0.95)
                # Implies airline entity as well if airline_hint not given
                if not airline_hint:
                    add_entity("AIRLINE", carrier, carrier, 0.9)

        # 4. Extract Airlines by Name or standalone IATA code (only if not explicitly provided)
        q_lower = query.lower()
        if not airline_hint:
            for phrase, code in sorted(KNOWN_AIRLINES.items(), key=lambda x: len(x[0]), reverse=True):
                pattern = rf"\b{re.escape(phrase)}\b"
                if re.search(pattern, q_lower):
                    add_entity("AIRLINE", phrase, code, 0.85)

        # 5. Extract Airports and Cities
        for loc_name, iata in sorted(KNOWN_AIRPORTS.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = rf"\b{re.escape(loc_name)}\b"
            if re.search(pattern, q_lower):
                add_entity("AIRPORT", loc_name, iata, 0.85)

        # 6. Extract Policy Types (only if not explicitly provided)
        if not policy_hint:
            for kw, p_type in sorted(POLICY_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, q_lower):
                    add_entity("POLICY_TYPE", kw, p_type, 0.8)

        return entities


entity_extractor = TravelEntityExtractor()
