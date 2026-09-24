"""Provider factory and dependency registry."""

from app.core.config import settings
from app.providers.amadeus.flight_provider import AmadeusFlightProvider
from app.providers.base import BookingProvider, FlightProvider, HotelProvider
from app.providers.mock.mock_booking_provider import MockBookingProvider
from app.providers.mock.mock_flight_provider import MockFlightProvider
from app.providers.mock.mock_hotel_provider import MockHotelProvider

# Singletons for mock providers to maintain in-memory state during tests and requests
_mock_flight_provider = MockFlightProvider()
_mock_hotel_provider = MockHotelProvider()
_mock_booking_provider = MockBookingProvider()


def get_flight_provider(provider_type: str | None = None) -> FlightProvider:
    """Resolve and return appropriate FlightProvider instance."""
    p_type = (provider_type or settings.FLIGHT_PROVIDER).lower().strip()
    if p_type == "amadeus":
        return AmadeusFlightProvider()
    return _mock_flight_provider


def get_hotel_provider(provider_type: str | None = None) -> HotelProvider:
    """Resolve and return appropriate HotelProvider instance."""
    return _mock_hotel_provider


def get_booking_provider(provider_type: str | None = None) -> BookingProvider:
    """Resolve and return appropriate BookingProvider instance."""
    return _mock_booking_provider
