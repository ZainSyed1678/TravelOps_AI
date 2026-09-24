"""Providers package exports."""

from app.providers.amadeus.client import AmadeusClient
from app.providers.amadeus.flight_provider import AmadeusFlightProvider
from app.providers.base import BookingProvider, FlightProvider, HotelProvider
from app.providers.exceptions import (
    ProviderAuthenticationException,
    ProviderException,
    ProviderInventoryUnavailableException,
    ProviderRateLimitException,
    ProviderTimeoutException,
    ProviderValidationException,
)
from app.providers.factory import (
    get_booking_provider,
    get_flight_provider,
    get_hotel_provider,
)
from app.providers.mock.mock_booking_provider import MockBookingProvider
from app.providers.mock.mock_flight_provider import MockFlightProvider
from app.providers.mock.mock_hotel_provider import MockHotelProvider
from app.providers.schemas import (
    CancellationResponse,
    FlightPricingResponse,
    FlightSearchResponse,
    FlightStatusResponse,
    HotelDetailsResponse,
    HotelSearchResponse,
    ProviderBookingRequest,
    ProviderBookingResponse,
    ProviderFlightOffer,
    ProviderHotelOffer,
    RebookResponse,
)

__all__ = [
    "FlightProvider",
    "HotelProvider",
    "BookingProvider",
    "MockFlightProvider",
    "MockHotelProvider",
    "MockBookingProvider",
    "AmadeusClient",
    "AmadeusFlightProvider",
    "get_flight_provider",
    "get_hotel_provider",
    "get_booking_provider",
    "ProviderFlightOffer",
    "FlightSearchResponse",
    "FlightPricingResponse",
    "FlightStatusResponse",
    "ProviderHotelOffer",
    "HotelSearchResponse",
    "HotelDetailsResponse",
    "ProviderBookingRequest",
    "ProviderBookingResponse",
    "CancellationResponse",
    "RebookResponse",
    "ProviderException",
    "ProviderTimeoutException",
    "ProviderRateLimitException",
    "ProviderAuthenticationException",
    "ProviderInventoryUnavailableException",
    "ProviderValidationException",
]
