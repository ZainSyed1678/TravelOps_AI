"""Feature engineering pipeline for flight offer scoring and ranking."""

import numpy as np

from app.ml.schemas import UserPreferences
from app.providers.schemas import ProviderFlightOffer

# Historical reputation / quality index for airlines (0.0 to 1.0)
AIRLINE_QUALITY_INDEX: dict[str, float] = {
    "EK": 0.92,
    "QR": 0.93,
    "SQ": 0.94,
    "BA": 0.85,
    "AI": 0.78,
    "6E": 0.84,
    "LH": 0.86,
    "AF": 0.85,
}


class FlightFeatureExtractor:
    """Extracts normalized numerical features and explainability cues from flight offers."""

    FEATURE_NAMES = [
        "price_ratio",
        "duration_ratio",
        "stops_count",
        "departure_convenience",
        "arrival_convenience",
        "airline_reputation",
        "is_refundable",
        "preferred_airline_match",
    ]

    def extract_features(
        self,
        offer: ProviderFlightOffer,
        route_median_price: float,
        route_min_duration: int,
        preferences: UserPreferences | None = None,
    ) -> np.ndarray:
        """Extract a 1D vector of normalized numerical features for an offer."""
        price = offer.total_price
        price_ratio = price / max(1.0, route_median_price)

        duration_minutes = offer.duration_minutes
        stops = offer.stops

        dep_hour = offer.departure_time.hour + (offer.departure_time.minute / 60.0)
        arr_hour = offer.arrival_time.hour + (offer.arrival_time.minute / 60.0)

        duration_ratio = duration_minutes / max(1, route_min_duration)

        dep_convenience = self._compute_hour_convenience(dep_hour, is_departure=True)
        arr_convenience = self._compute_hour_convenience(arr_hour, is_departure=False)

        carrier = offer.airline_code.upper()
        reputation = AIRLINE_QUALITY_INDEX.get(carrier, 0.80)

        is_refundable = 1.0 if offer.is_refundable else 0.0

        pref_match = 0.0
        if preferences and preferences.preferred_airline:
            if carrier == preferences.preferred_airline.upper():
                pref_match = 1.0

        return np.array(
            [
                price_ratio,
                duration_ratio,
                float(stops),
                dep_convenience,
                arr_convenience,
                reputation,
                is_refundable,
                pref_match,
            ],
            dtype=np.float32,
        )

    def extract_batch_features(
        self,
        offers: list[ProviderFlightOffer],
        preferences: UserPreferences | None = None,
    ) -> np.ndarray:
        """Extract feature matrix (N, F) for a batch of offers on the same route."""
        if not offers:
            return np.empty((0, len(self.FEATURE_NAMES)), dtype=np.float32)

        prices = [o.total_price for o in offers]
        durations = [o.duration_minutes for o in offers]
        median_price = float(np.median(prices)) if prices else 10000.0
        min_duration = int(np.min(durations)) if durations else 180

        rows = []
        for off in offers:
            row = self.extract_features(
                offer=off,
                route_median_price=median_price,
                route_min_duration=min_duration,
                preferences=preferences,
            )
            rows.append(row)

        return np.vstack(rows)

    @staticmethod
    def _compute_hour_convenience(hour: float, is_departure: bool = True) -> float:
        """Compute convenience score (0.0 to 1.0) based on time of day."""
        if is_departure:
            # Morning peak (07:00 - 11:30): ideal for business/leisure
            if 7.0 <= hour <= 11.5:
                return 1.0
            # Evening peak (16:30 - 20:30): highly convenient
            elif 16.5 <= hour <= 20.5:
                return 0.90
            # Afternoon (11.5 - 16.5): good
            elif 11.5 < hour < 16.5:
                return 0.75
            # Late night (20.5 - 23.0): acceptable
            elif 20.5 < hour <= 23.0:
                return 0.60
            # Redeye hours (23:00 - 06:00): inconvenient
            else:
                return 0.30
        else:
            # Arrival convenience: daytime arrival is preferred
            if 8.0 <= hour <= 21.0:
                return 1.0
            elif 21.0 < hour <= 23.5:
                return 0.70
            elif 6.0 <= hour < 8.0:
                return 0.60
            else:  # Midnight to 06:00
                return 0.25


feature_extractor = FlightFeatureExtractor()
